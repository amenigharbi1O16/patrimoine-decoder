"""
ChromaDB vector store — Heritage Decoder agent memory (Level 2 RAG).

Stores transcription embeddings per session so Agent 4 can retrieve
similar past analyses and enrich historical context.
"""
import os
from datetime import datetime

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "chroma")
COLLECTION_NAME = "heritage_analyses"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_collection = None


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection
    import chromadb
    from chromadb.utils import embedding_functions

    os.makedirs(CHROMA_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    _collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def init_store() -> None:
    """Initialize ChromaDB collection (call before Docker build)."""
    _get_collection()
    print(f"[ChromaDB] Store ready at {CHROMA_PATH}")


def save_analysis(
    analysis_id: int,
    session_id: str,
    transcription: str,
    manuscript_id: str = "",
    verdict: str = "",
    language: str = "",
) -> None:
    """Save a transcription embedding after each completed analysis."""
    if not transcription or not transcription.strip():
        return
    try:
        collection = _get_collection()
        doc_id = f"{session_id}_{analysis_id}"
        collection.upsert(
            documents=[transcription[:4000]],
            metadatas=[{
                "session_id": session_id,
                "analysis_id": str(analysis_id),
                "manuscript_id": manuscript_id or "unknown",
                "verdict": verdict or "unknown",
                "language": language or "unknown",
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
            }],
            ids=[doc_id],
        )
        print(f"[ChromaDB] Saved embedding for analysis {analysis_id}")
    except Exception as e:
        print(f"[ChromaDB] save_analysis failed: {e}")


def query_similar(session_id: str, query_text: str, top_k: int = 3) -> list[dict]:
    """Return top-K similar past analyses for this session."""
    if not query_text or not query_text.strip():
        return []
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return []

        results = collection.query(
            query_texts=[query_text[:2000]],
            n_results=top_k,
            where={"session_id": session_id},
        )
        similar = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            if not meta:
                continue
            similar.append({
                "manuscript_id": meta.get("manuscript_id", "unknown"),
                "verdict": meta.get("verdict", "unknown"),
                "language": meta.get("language", "unknown"),
                "date": meta.get("date", ""),
                "snippet": (doc or "")[:120].replace("\n", " "),
                "similarity": round(1 - dist, 3) if dist is not None else 0,
            })
        return similar
    except Exception as e:
        print(f"[ChromaDB] query_similar failed: {e}")
        return []


def format_similar_context(similar: list[dict]) -> str:
    """Format ChromaDB hits as prompt text for Agent 4."""
    if not similar:
        return ""
    lines = [f"Similar manuscripts you analyzed before ({len(similar)} matches):"]
    for s in similar:
        lines.append(
            f"• [{s['date']}] {s['manuscript_id']} | {s['language']} | "
            f"Verdict: {s['verdict']} | \"{s['snippet']}...\""
        )
    return "\n".join(lines)


def count_entries(session_id: str) -> int:
    """Count ChromaDB entries for a session."""
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return 0
        results = collection.get(where={"session_id": session_id})
        return len(results.get("ids", []))
    except Exception:
        return 0
