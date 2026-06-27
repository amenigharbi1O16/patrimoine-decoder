"""
RAG Memory — Heritage Decoder
Real semantic retrieval of past analyses to ground agent prompts.

Strategy:
  - Embed transcriptions + verdicts using Google text-embedding-004 (free tier)
  - Store embeddings as JSON in AnalysisHistory.embedding column
  - On retrieval: cosine similarity to find the K most-relevant past analyses
  - Returns a formatted context string injected into agent prompts

Fallback: if embedding API is unavailable, use simple recency-based last-5 read.
"""
import os, json, math
from typing import Optional
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(env_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
EMBEDDING_MODEL = "models/text-embedding-004"
TOP_K = 3  # how many past analyses to retrieve


# ─── Embedding helpers ────────────────────────────────────────────────────────

def _get_embedding(text: str) -> Optional[list[float]]:
    """Generate an embedding vector via Google text-embedding-004."""
    if not GOOGLE_API_KEY or not text.strip():
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]
    except Exception as e:
        print(f"[RAG] Embedding failed: {e}")
        return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity (no numpy needed)."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ─── Public API ───────────────────────────────────────────────────────────────

def store_embedding(analysis_id: int, text: str) -> None:
    """
    Compute and store the embedding for a completed analysis.
    Called from main.py after saving to DB.
    """
    vec = _get_embedding(text)
    if vec is None:
        return
    try:
        from backend.mcp_server.database import Session, AnalysisHistory
        db = Session()
        entry = db.query(AnalysisHistory).filter(AnalysisHistory.id == analysis_id).first()
        if entry:
            entry.embedding = json.dumps(vec)
            db.commit()
        db.close()
    except Exception as e:
        print(f"[RAG] Failed to store embedding: {e}")


def get_relevant_context(session_id: str, query_text: str, top_k: int = TOP_K) -> str:
    """
    Retrieve the top-K most semantically-relevant past analyses for this session.

    Returns a formatted string ready to inject into an agent prompt.
    If embedding is unavailable, falls back to recency-based last-5.
    """
    try:
        from backend.mcp_server.database import Session, AnalysisHistory

        db = Session()
        all_entries = (
            db.query(AnalysisHistory)
            .filter(AnalysisHistory.session_id == session_id)
            .order_by(AnalysisHistory.created_at.desc())
            .limit(50)  # cap to avoid scanning full history
            .all()
        )
        db.close()

        if not all_entries:
            return "No previous analyses — first session for this user."

        # Try semantic retrieval
        query_vec = _get_embedding(query_text)
        if query_vec:
            scored = []
            for entry in all_entries:
                if entry.embedding:
                    try:
                        entry_vec = json.loads(entry.embedding)
                        score = _cosine_similarity(query_vec, entry_vec)
                        scored.append((score, entry))
                    except Exception:
                        pass

            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                top = [e for _, e in scored[:top_k]]
                return _format_context(top, mode="semantic")

        # Fallback — most recent
        return _format_context(all_entries[:5], mode="recency")

    except Exception as e:
        print(f"[RAG] Context retrieval error: {e}")
        return "Agent memory temporarily unavailable."


def _format_context(entries, mode: str) -> str:
    """Format retrieved entries as a concise agent memory block."""
    header = (
        f"[Agent RAG Memory — {mode} retrieval, {len(entries)} relevant analyses]\n"
    )
    lines = []
    for e in entries:
        verdict_label = "⚠️ HALLUCINATION" if e.hallucination_detected == "True" else e.verdict
        lines.append(
            f"• [{e.created_at.strftime('%Y-%m-%d')}] "
            f"{e.image_filename} | {e.target_language} | "
            f"Verdict: {verdict_label} ({e.confidence_score}%)"
        )
        if e.ocr_transcription:
            snippet = e.ocr_transcription[:80].replace("\n", " ")
            lines.append(f"  Transcription snippet: {snippet}...")
    return header + "\n".join(lines)
