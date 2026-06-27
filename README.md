# 🏛️ Heritage Decoder
**Multi-Agent AI Pipeline for Historical Manuscript Analysis & Hallucination Detection**

> Kaggle AI Agents Intensive Vibe Coding Capstone 2026

**Live Demo:** https://heritage-decoder.vercel.app  
**Video:** [YouTube — à ajouter]  
**Author:** Ameni Gharbi | Horizon School of Digital Technologies, Tunisia

---

## The Problem

AI vision models can transcribe historical manuscripts — but they also **hallucinate**. They confidently invent authors, fabricate attributions, and assert false historical facts about irreplaceable cultural artifacts.

A system that lies about who wrote a 700-year-old manuscript is not a tool for cultural preservation — it is a threat to it.

---

## The Solution

Heritage Decoder is a multi-agent pipeline that validates every historical claim made by an AI against a verified archival catalog before returning results to the user.
Input (Image or Text)

↓

Agent 1 — OCR & Vision        Extract text from manuscript image

↓

Agent 2 — MCP Validation      Cross-check claims against archival catalog

↓

Agent 3 — Translation         Translate validated text only

↓

Agent 4 — Historical Context  Enrich with sourced context (RAG)

↓

Agent 5 — Orchestrator        Assemble report + confidence score

↓

Final Report: transcription · translation · context · verdict · confidence score

If the AI invents an author → **HALLUCINATION DETECTED** ❌  
If the author matches the catalog → **VERIFIED** ✅

---

## Key Concepts Demonstrated

| Concept | Implementation |
|---|---|
| Multi-agent system | Google ADK — 5 specialized agents |
| MCP Server | FastMCP archival catalog (ground truth) |
| Long-term memory | ChromaDB RAG — learns from past analyses |
| Session management | SQLite per-user analysis history |
| Context engineering | Past analyses injected into agent prompts |

---

## Tech Stack

**Frontend:** React 19 · Vite · Tailwind CSS  
**Backend:** FastAPI · Google ADK · Python  
**Agents:** Gemini 2.0 Flash (vision) · Groq llama-3.1 (translation) · Groq llama-3.3 (context)  
**Memory:** ChromaDB · FastMCP · SQLite  
**Deployment:** Render (backend) · Vercel (frontend)

---

## Run Locally

```bash
# Backend
pip install -r backend/requirements.txt
cp .env.example .env  # add your GOOGLE_API_KEY and GROQ_API_KEY
python -m uvicorn backend.main:app --port 8000

# Frontend
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```
