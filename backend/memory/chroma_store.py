"""
ChromaDB vector store — Heritage Decoder agent memory (Level 2 RAG).
Uses ChromaDB's default embedding function (no torch required).
Global shared knowledge base + personal session memory.
"""
import os
import hashlib
from datetime import datetime

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "chroma")
COLLECTION_NAME = "heritage_analyses"

_collection = None


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection
    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    os.makedirs(CHROMA_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = DefaultEmbeddingFunction()
    _collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def init_store() -> None:
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
    """
    Sauvegarde dans ChromaDB avec deux IDs :
    1. ID personnel (session_id + analysis_id) → mémoire personnelle
    2. ID global basé sur le contenu (hash) → base partagée entre tous les users
       Si deux users analysent le même manuscrit, le hash est identique
       → ChromaDB upsert silencieux, pas de doublon.
    """
    if not transcription or not transcription.strip():
        return
    try:
        collection = _get_collection()
        content_hash = hashlib.md5(transcription[:4000].encode()).hexdigest()
        now = datetime.utcnow().strftime("%Y-%m-%d")

        # Entrée personnelle — filtrée par session_id
        personal_id = f"{session_id}_{analysis_id}"
        collection.upsert(
            documents=[transcription[:4000]],
            metadatas=[{
                "session_id": session_id,
                "analysis_id": str(analysis_id),
                "manuscript_id": manuscript_id or "unknown",
                "verdict": verdict or "unknown",
                "language": language or "unknown",
                "date": now,
                "shared": "false",
                "content_hash": content_hash,
            }],
            ids=[personal_id],
        )

        # Entrée globale — visible par tous les users
        # Même manuscrit = même hash = même ID = pas de doublon ChromaDB
        global_id = f"global_{content_hash}"
        collection.upsert(
            documents=[transcription[:4000]],
            metadatas=[{
                "session_id": "global",
                "analysis_id": str(analysis_id),
                "manuscript_id": manuscript_id or "unknown",
                "verdict": verdict or "unknown",
                "language": language or "unknown",
                "date": now,
                "shared": "true",
                "content_hash": content_hash,
            }],
            ids=[global_id],
        )

        print(f"[ChromaDB] Saved personal + global embedding for analysis {analysis_id}")
    except Exception as e:
        print(f"[ChromaDB] save_analysis failed: {e}")


def query_similar(session_id: str, query_text: str, top_k: int = 3) -> list[dict]:
    """
    Cherche en deux étapes :
    1. Base globale partagée → manuscrits déjà analysés par n'importe quel user
    2. Mémoire personnelle → analyses du même user
    Déduplique par content_hash pour éviter les doublons dans les résultats.
    """
    if not query_text or not query_text.strip():
        return []
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return []

        seen_hashes = set()
        similar = []

        # Étape 1 — base globale
        try:
            global_results = collection.query(
                query_texts=[query_text[:2000]],
                n_results=top_k,
                where={"session_id": "global"},
            )
            docs = global_results.get("documents", [[]])[0]
            metas = global_results.get("metadatas", [[]])[0]
            distances = global_results.get("distances", [[]])[0]

            for doc, meta, dist in zip(docs, metas, distances):
                if not meta:
                    continue
                content_hash = meta.get("content_hash", "")
                if content_hash in seen_hashes:
                    continue
                seen_hashes.add(content_hash)
                similar.append({
                    "manuscript_id": meta.get("manuscript_id", "unknown"),
                    "verdict": meta.get("verdict", "unknown"),
                    "language": meta.get("language", "unknown"),
                    "date": meta.get("date", ""),
                    "snippet": (doc or "")[:120].replace("\n", " "),
                    "similarity": round(1 - dist, 3) if dist is not None else 0,
                    "source": "global",
                })
        except Exception as e:
            print(f"[ChromaDB] global query failed: {e}")

        # Étape 2 — mémoire personnelle
        try:
            personal_results = collection.query(
                query_texts=[query_text[:2000]],
                n_results=top_k,
                where={"session_id": session_id},
            )
            docs = personal_results.get("documents", [[]])[0]
            metas = personal_results.get("metadatas", [[]])[0]
            distances = personal_results.get("distances", [[]])[0]

            for doc, meta, dist in zip(docs, metas, distances):
                if not meta:
                    continue
                content_hash = meta.get("content_hash", "")
                if content_hash in seen_hashes:
                    continue
                seen_hashes.add(content_hash)
                similar.append({
                    "manuscript_id": meta.get("manuscript_id", "unknown"),
                    "verdict": meta.get("verdict", "unknown"),
                    "language": meta.get("language", "unknown"),
                    "date": meta.get("date", ""),
                    "snippet": (doc or "")[:120].replace("\n", " "),
                    "similarity": round(1 - dist, 3) if dist is not None else 0,
                    "source": "personal",
                })
        except Exception as e:
            print(f"[ChromaDB] personal query failed: {e}")

        # Tri par similarité décroissante
        similar.sort(key=lambda x: x["similarity"], reverse=True)
        return similar[:top_k]

    except Exception as e:
        print(f"[ChromaDB] query_similar failed: {e}")
        return []


def format_similar_context(similar: list[dict]) -> str:
    if not similar:
        return ""
    lines = [f"Similar manuscripts from global knowledge base ({len(similar)} matches):"]
    for s in similar:
        source_label = "🌐 global" if s.get("source") == "global" else "👤 personal"
        lines.append(
            f"• [{s['date']}] {s['manuscript_id']} | {s['language']} | "
            f"Verdict: {s['verdict']} | {source_label} | \"{s['snippet']}...\""
        )
    return "\n".join(lines)


def count_entries(session_id: str) -> int:
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return 0
        results = collection.get(where={"session_id": session_id})
        return len(results.get("ids", []))
    except Exception:
        return 0


def count_global_entries() -> int:
    """Nombre total de manuscrits uniques dans la base globale partagée."""
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return 0
        results = collection.get(where={"session_id": "global"})
        return len(results.get("ids", []))
    except Exception:
        return 0