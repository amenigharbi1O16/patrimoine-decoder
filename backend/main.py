import os, shutil, uuid, json
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.mcp_server.database import Session, Manuscript, AnalysisHistory, User, init_db
from backend.agents.orchestrator import run_pipeline
from backend.agents.rag_memory import store_embedding
from backend.memory.chroma_store import save_analysis, count_entries
from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from datetime import datetime

load_dotenv()
init_db()

app = FastAPI(title="Universal Heritage Decoder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

PIPELINE_STEPS = [
    "Agent 1 — OCR & Vision (Gemini)",
    "Agent 2 — MCP Validation",
    "Agent 3 — Translation (Groq)",
    "Agent 4 — Context (Groq)",
    "Agent 5 — Critic/Assembler",
]


def _parse_verified_facts(raw: str | None) -> list:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def _analysis_to_dict(entry: AnalysisHistory, include_full: bool = True) -> dict:
    verified_facts = _parse_verified_facts(entry.verified_facts)
    base = {
        "id": entry.id,
        "manuscript_id": entry.manuscript_id,
        "image_filename": entry.image_filename,
        "target_language": entry.target_language,
        "claimed_author": entry.claimed_author or "",
        "verdict": entry.verdict,
        "confidence_score": entry.confidence_score,
        "hallucination_detected": entry.hallucination_detected == "True",
        "created_at": entry.created_at.isoformat(),
    }
    if include_full:
        base.update({
            "ocr_transcription": entry.ocr_transcription or "",
            "translation": entry.translation or "",
            "historical_context": entry.historical_context or "",
            "language_detected": entry.language_detected or "",
            "real_author": entry.real_author or "",
            "explanation": entry.explanation or "",
            "verified_facts": verified_facts,
            "source": entry.source or "",
            "pipeline_steps": PIPELINE_STEPS,
            "agent_memory_used": bool(entry.embedding),
            "preview": (entry.ocr_transcription or "")[:200],
        })
    else:
        base["preview"] = (entry.ocr_transcription or "")[:200]
    return base


# ─── Auth routes ──────────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    username: str
    password: str


@app.post("/api/register")
def register(req: AuthRequest):
    db = Session()
    if db.query(User).filter(User.username == req.username).first():
        db.close()
        raise HTTPException(
            status_code=400, detail="Username already registered"
        )

    new_user = User(
        username=req.username,
        hashed_password=hash_password(req.password),
    )
    db.add(new_user)
    db.commit()
    db.close()

    token = create_access_token(req.username)
    return {"access_token": token, "token_type": "bearer", "username": req.username}


@app.post("/api/login")
def login(req: AuthRequest):
    db = Session()
    user = db.query(User).filter(User.username == req.username).first()
    db.close()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(req.username)
    return {"access_token": token, "token_type": "bearer", "username": req.username}


# ─── Public routes ────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/manuscripts")
def get_manuscripts():
    db = Session()
    items = db.query(Manuscript).all()
    db.close()
    return [
        {
            "id": m.qdl_id,
            "title": m.title_english,
            "date": m.date,
            "author": m.author,
            "institution": m.institution,
        }
        for m in items
    ]


# ─── Protected routes (require JWT) ───────────────────────────────────────────

@app.post("/api/analyze")
def analyze(
    file: UploadFile = File(None),
    text_input: str = Form(""),
    manuscript_id: str = Form("none"),
    claimed_author: str = Form(""),
    target_language: str = Form("English"),
    current_user: str = Depends(get_current_user),
):
    image_path = None

    if file and file.filename:
        os.makedirs("data/temp", exist_ok=True)
        image_path = f"data/temp/{uuid.uuid4()}_{file.filename}"
        with open(image_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    try:
        result = run_pipeline(
            image_path=image_path,
            text_input=text_input,
            manuscript_id=manuscript_id,
            claimed_author=claimed_author,
            target_language=target_language,
            session_id=current_user,
        )

        db = Session()
        entry = AnalysisHistory(
            session_id=current_user,
            manuscript_id=result.get("manuscript_id", "unknown"),
            image_filename=file.filename if file and file.filename else "text_input",
            target_language=target_language,
            claimed_author=claimed_author,
            verdict=result.get("verdict", "NO VALIDATION"),
            confidence_score=result.get("confidence_score", 0),
            ocr_transcription=result.get("ocr_transcription", ""),
            translation=result.get("translation", ""),
            historical_context=result.get("historical_context", ""),
            language_detected=result.get("language_detected", ""),
            real_author=result.get("real_author", ""),
            explanation=result.get("explanation", ""),
            verified_facts=json.dumps(result.get("verified_facts", []), ensure_ascii=False),
            source=result.get("source", ""),
            hallucination_detected=str(result.get("hallucination_detected", False)),
            created_at=datetime.utcnow(),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        entry_id = entry.id
        db.close()

        transcription = result.get("ocr_transcription", "")
        if transcription and transcription.strip():
            try:
                embed_text = (
                    f"Manuscript: {result.get('manuscript_id')}\n"
                    f"Verdict: {result.get('verdict')}\n"
                    f"Transcription: {transcription[:500]}"
                )
                store_embedding(entry_id, embed_text)
            except Exception as e:
                print(f"[RAG] Failed to store embedding: {e}")

            try:
                save_analysis(
                    analysis_id=entry_id,
                    session_id=current_user,
                    transcription=transcription,
                    manuscript_id=result.get("manuscript_id", ""),
                    verdict=result.get("verdict", ""),
                    language=result.get("language_detected", ""),
                )
            except Exception as e:
                print(f"[ChromaDB] Failed to save analysis: {e}")

        return result
    finally:
        if image_path and os.path.exists(image_path):
            os.remove(image_path)


@app.get("/api/history")
def get_history(current_user: str = Depends(get_current_user)):
    db = Session()
    entries = (
        db.query(AnalysisHistory)
        .filter(AnalysisHistory.session_id == current_user)
        .order_by(AnalysisHistory.created_at.desc())
        .limit(50)
        .all()
    )
    db.close()
    return [_analysis_to_dict(e, include_full=True) for e in entries]


@app.get("/api/analysis/{analysis_id}")
def get_analysis(analysis_id: int, current_user: str = Depends(get_current_user)):
    db = Session()
    entry = (
        db.query(AnalysisHistory)
        .filter(
            AnalysisHistory.id == analysis_id,
            AnalysisHistory.session_id == current_user,
        )
        .first()
    )
    db.close()
    if not entry:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return _analysis_to_dict(entry, include_full=True)


@app.get("/api/stats")
def get_stats(current_user: str = Depends(get_current_user)):
    db = Session()
    all_e = (
        db.query(AnalysisHistory)
        .filter(AnalysisHistory.session_id == current_user)
        .all()
    )
    db.close()

    total = len(all_e)
    hall = sum(1 for e in all_e if e.hallucination_detected == "True")
    langs = list(set(e.target_language for e in all_e if e.target_language))
    memory_count = count_entries(current_user)
    has_embeddings = sum(1 for e in all_e if e.embedding) > 0

    if memory_count > 0 or has_embeddings:
        memory_status = f"Active (learned from {max(memory_count, total)} analyses)"
    elif total > 2:
        memory_status = "Active"
    else:
        memory_status = "Learning..."

    return {
        "total_analyses": total,
        "hallucinations_caught": hall,
        "hallucination_rate": f"{round(hall / total * 100)}%" if total else "0%",
        "languages_used": langs,
        "agent_memory": memory_status,
        "memory_entries_count": memory_count,
    }
