# Patrimoine Decoder

**Multi-agent pipeline for Maghrebi manuscript validation**

## The Project
Patrimoine Decoder brings historical Maghrebi manuscripts to life. It uses a 5-agent pipeline (powered by Google ADK) to transcribe, validate, translate, and contextualize ancient Arabic texts, cross-checking claims against real archival data (QDL, BnT) via a custom MCP server.

### Architecture
1. **OCR Agent**: Extracts transcription from image (Gemini Vision).
2. **Validation Agent**: Cross-checks claims with real archival catalog via MCP.
3. **Translation Agent**: Translates the grounded/validated text.
4. **Context Agent**: Provides historical context (RAG).
5. **Orchestrator**: Assembles the output and assigns confidence scores.

### Tech Stack
- Frontend: React + Vite + Tailwind CSS
- Backend: FastAPI + Google ADK (Python)
- LLM: Gemini Flash (via Vertex AI)
- Deployment: Vercel (Frontend), Cloud Run (Backend)

## Local Development
Refer to the documentation for running the dev servers.
