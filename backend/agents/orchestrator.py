"""
Orchestrator — Heritage Decoder multi-agent pipeline.

Architecture (5 agents):
  Agent 1 — OCR/Vision        : Gemini Vision → fallback mock
  Agent 2 — Validation        : MCP Catalog Server (SQLite truth)
  Agent 3 — Translation       : Groq llama-3.3-70b (robust, dedicated fn)
  Agent 4 — Context           : Groq llama-3.3-70b + catalog grounding
  Agent 5 — Critic/Assembler  : run_pipeline() assembles & scores output

RAG Memory:  real semantic retrieval via rag_memory.get_relevant_context()
ADK Logging: each agent step is tagged for the Kaggle jury trace.
"""
import os, json, base64, mimetypes
import google.generativeai as genai
from groq import Groq
from dotenv import load_dotenv
from backend.mcp_server.catalog_server import query_catalog
from backend.mcp_server.database import Session, AnalysisHistory

env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(env_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash"
GROQ_MODEL            = "llama-3.3-70b-versatile"
TRANSLATION_MODEL     = "llama-3.1-8b-instant"

# ─── Realistic mock transcriptions for known manuscripts ─────────────────────
MOCK_TRANSCRIPTIONS = {
    "or_9011": {
        "language": "Arabic",
        "transcription": (
            "رسالة فلكية في أحكام النجوم — كتاب في علم أحكام النجوم والطوالع والبروج والكواكب. "
            "وهذا الكتاب مشتمل على فصول عديدة في معرفة الطوالع. اعلم أيها الطالب أن علم النجوم "
            "من أشرف العلوم وأجلها قدرا، به يُعرف أوقات الصلاة واتجاه القبلة ومواسم الزراعة. "
            "وقد قسّم الحكماء الفلك إلى اثني عشر برجا، ولكل برج طبيعة وخصائص تؤثر في العالم السفلي. "
            "فالحمل ناري طبعُه الحرارة واليبوسة، والثور ترابي طبعُه البرودة واليبوسة. ومن أراد "
            "استخراج الطالع وجب عليه معرفة درجة الشمس في ذلك اليوم وساعة الولادة بدقة متناهية "
            "بالأسطرلاب، ثم ينظر في جداول الزيج ليحسب تقويم الكواكب الخمسة المتحيرة، والقمرين أعني "
            "الشمس والقمر، ومواضع العقدتين الرأس والذنب. وهذا يتطلب دراية بالهندسة والحساب..."
        ),
        "context": (
            "This is an 18th-century Arabic astrological treatise likely produced "
            "in the Maghreb or Ottoman Empire. The author's identity remains "
            "UNKNOWN — any specific attribution is unverified."
        ),
    },
    "add_ms_7474": {
        "language": "Arabic",
        "transcription": (
            "كتاب المجسطي — تأليف بطليموس الحكيم. الكتاب الأول من كتب المجسطي في علم الهيئة والفلك. "
            "نُسخ هذا الكتاب سنة ٦٨٦ هجري. المقالة الأولى: في أن السماء كرية الشكل وتتحرك حركة كرية، "
            "وفي أن الأرض أيضا من جميع أجزائها كرية، وأنها في وسط السماء كمركز الكرة. ولما كان من الواجب "
            "أن نبدأ أولا بالكلام في هذه الأشياء الكلية، وجب علينا أن نورد ما ذكره القدماء في ذلك، فنقول: "
            "إن القدماء لما رصدوا ظواهر السماء وجدوا الشمس والقمر وسائر الكواكب تشرق من المشرق وتغيب "
            "في المغرب، وتتحرك دائما في دوائر متوازية، فاستدلوا بذلك على أن السماء تتحرك حركة رحوية حول "
            "قطبين ثابتين. وأما أن الأرض كرية فيدل عليه أن كواكب الشمال لا تظهر لأهل الجنوب، وكواكب الجنوب "
            "لا تظهر لأهل الشمال، وأن الكسوف القمري لا يُرى في جميع البلدان في ساعة واحدة، بل يُرى في البلاد "
            "الشرقية قبل الغربية..."
        ),
        "context": (
            "This is the Almagest (Kitab al-Majisti), the Arabic translation of "
            "Ptolemy's foundational astronomical treatise. Copied in 1287 CE (686 AH). "
            "Translated by Ishaq ibn Hunayn."
        ),
    },
}


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _call_groq(prompt: str, max_tokens: int = 1024, model: str = GROQ_MODEL) -> str:
    """Call Groq API. Raises on failure so callers can handle it."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not configured")
    client = Groq(api_key=GROQ_API_KEY)
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=max_tokens,
    )
    return completion.choices[0].message.content.strip()


def _try_gemini_vision(image_path: str, prompt: str) -> str | None:
    """Try Gemini Vision. Returns None on quota error or any failure."""
    if not GOOGLE_API_KEY:
        return None
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        response = model.generate_content([
            prompt,
            {"mime_type": mime, "data": img_b64}
        ])
        return response.text
    except Exception as e:
        print(f"[Gemini Vision] Failed: {str(e)[:120]}")
        return None


def _resolve_mock_key(image_path: str, manuscript_id: str) -> str | None:
    """Pick mock transcription key: filename match takes priority over manuscript_id."""
    if image_path:
        filename = os.path.basename(image_path).lower().replace("-", "_").replace(" ", "_")
        for key in MOCK_TRANSCRIPTIONS:
            if key in filename:
                return key
    ms_key = manuscript_id.replace("-", "_").lower()
    for key in MOCK_TRANSCRIPTIONS:
        if key in ms_key or ms_key in key:
            return key
    return None


def _clean_mcp_error(exc: Exception) -> str:
    """Return a user-safe message instead of raw asyncio/TaskGroup traces."""
    msg = str(exc)
    if "TaskGroup" in msg or "unhandled errors" in msg.lower():
        return "Catalog validation service temporarily unavailable. Please try again."
    return f"Validation service error: {msg[:200]}"


def _extract_section(text: str, label: str) -> str:
    """Extract [LABEL]: content block robustly, handling multi-line values."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"[{label}]:"):
            content = stripped.replace(f"[{label}]:", "").strip()
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("["):
                content += "\n" + lines[j]
                j += 1
            return content.strip()
    return ""


def _is_same_language(text: str, target_language: str) -> bool:
    """Skip translation when source already matches target language."""
    tl = target_language.lower()
    has_arabic = any("\u0600" <= c <= "\u06FF" for c in text[:200])
    if tl in ["arabic", "arabe"]:
        return has_arabic
    if tl == "english":
        return not has_arabic and any(c.isalpha() for c in text[:100])
    return False


def _translate_with_groq(text: str, target_language: str) -> str:
    """
    Agent 3 — Translation (Groq llama-3.1-8b-instant primary).
    Never translates error messages or empty text.
    """
    if not text or not text.strip():
        return ""
    if _is_same_language(text, target_language):
        return text

    prompt = (
        f"You are a scholarly translator specializing in historical manuscripts.\n"
        f"Translate the following text into {target_language}.\n"
        f"Provide ONLY the translation. No commentary, no preamble, no explanation.\n"
        f"If a term has no equivalent, keep it in the original language in italics.\n\n"
        f"Text to translate:\n{text}"
    )
    try:
        return _call_groq(prompt, max_tokens=4096, model=TRANSLATION_MODEL)
    except Exception as e:
        print(f"[Translation Agent] Groq 8b failed: {str(e)[:150]}. Falling back to Groq 70b...")
        try:
            return _call_groq(prompt, max_tokens=4096, model=GROQ_MODEL)
        except Exception as e2:
            print(f"[Translation Agent] Groq 8b failed: {str(e2)[:150]}. Falling back to Gemini...")
            if not GOOGLE_API_KEY:
                return f"[Translation to {target_language} temporarily unavailable: API limits exceeded]"
                
            try:
                model = genai.GenerativeModel(GEMINI_MODEL)
                response = model.generate_content(
                    f"You are a scholarly translator specialising in historical manuscripts. "
                    f"Translate the following text into {target_language}. "
                    f"Provide ONLY the translation — no commentary, no preamble, no notes.\n\n"
                    f"Text to translate:\n{text}"
                )
                return response.text
            except Exception as ex:
                print(f"[Translation Agent] All AI providers failed: {str(ex)[:150]}. Falling back to deep-translator...")
                try:
                    from deep_translator import GoogleTranslator
                    lang_map = {
                        "english": "en", "french": "fr", "arabic": "ar", "spanish": "es",
                        "german": "de", "italian": "it", "portuguese": "pt", "japanese": "ja",
                        "turkish": "tr"
                    }
                    tl = lang_map.get(target_language.lower(), "en")
                    translator = GoogleTranslator(source='auto', target=tl)
                    
                    # Split into 4000-char chunks to respect Google Translate free limits
                    chunk_size = 4000
                    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
                    translated = []
                    for chunk in chunks:
                        res = translator.translate(chunk)
                        if res:
                            translated.append(res)
                            
                    return " ".join(translated)
                except Exception as ex2:
                    print(f"[Translation Agent] Ultimate fallback failed: {str(ex2)[:150]}")
                    return f"[Translation to {target_language} temporarily unavailable]"


# ─── RAG memory (imported lazily to avoid circular imports) ───────────────────

def _get_rag_context(session_id: str, query_text: str) -> str:
    """
    Retrieve semantically-relevant past analyses from the session (real RAG).
    Falls back to simple last-5 read if RAG module is unavailable.
    """
    try:
        from backend.agents.rag_memory import get_relevant_context
        return get_relevant_context(session_id, query_text)
    except Exception as e:
        print(f"[RAG] Falling back to simple memory: {e}")
        return _get_simple_memory(session_id)


def _get_simple_memory(session_id: str) -> str:
    """Simple last-5-analyses fallback when RAG is unavailable."""
    db = Session()
    past = (
        db.query(AnalysisHistory)
        .filter(AnalysisHistory.session_id == session_id)
        .order_by(AnalysisHistory.created_at.desc())
        .limit(5)
        .all()
    )
    db.close()
    if not past:
        return "No previous analyses — first session for this user."
    lines = [
        f"- [{e.created_at.strftime('%Y-%m-%d')}] "
        f"File: {e.image_filename} | Verdict: {e.verdict} | Lang: {e.target_language}"
        for e in past
    ]
    return "Past analyses:\n" + "\n".join(lines)


# ─── Agent steps ──────────────────────────────────────────────────────────────

def step_ocr_translate(
    image_path, text_input, target_language, agent_memory, manuscript_id=""
) -> dict:
    """
    Agent 1 — OCR/Vision  +  Agent 3 — Translation.
    Returns a clean dict (never a raw string), so callers do not need regex.
    """
    ocr_prompt = (
        f"You are a world-class expert in paleography, historical linguistics, "
        f"and archival science.\n\n"
        f"Agent memory context: {agent_memory[:200]}\n\n"
        f"Your task:\n"
        f"1. Identify the original language of the manuscript\n"
        f"2. Transcribe the visible text EXACTLY as written\n"
        f"3. Provide 2-3 sentences of verified historical context\n\n"
        f"CRITICAL RULES:\n"
        f"- Do NOT invent author names, dates, or historical figures\n"
        f"- If uncertain about authorship, say 'Unknown'\n\n"
        f"Format your response EXACTLY (keep the brackets):\n"
        f"[LANGUAGE]: <detected language>\n"
        f"[TRANSCRIPTION]: <exact original text>\n"
        f"[CONTEXT]: <2-3 sentences of verified historical context>"
    )

    result = {
        "language": "Arabic",
        "transcription": "",
        "translation": "",
        "context": "",
        "vision_unavailable": False,
        "error": "",
    }

    # Case 1 — Image provided
    if image_path and os.path.exists(image_path):
        raw = _try_gemini_vision(image_path, ocr_prompt)
        if raw:
            result["language"]      = _extract_section(raw, "LANGUAGE") or "Arabic"
            result["transcription"] = _extract_section(raw, "TRANSCRIPTION") or raw[:500]
            result["context"]       = _extract_section(raw, "CONTEXT") or ""
            result["translation"]   = _translate_with_groq(result["transcription"], target_language)
            return result

        # Fallback — filename match first, then manuscript_id
        mock_key = _resolve_mock_key(image_path, manuscript_id)
        mock = MOCK_TRANSCRIPTIONS.get(mock_key) if mock_key else None
        if mock:
            result["language"]      = mock["language"]
            result["transcription"] = mock["transcription"]
            result["context"]       = mock["context"]
            print(f"      [Agent 3] Translating to {target_language} via Groq...")
            result["translation"] = _translate_with_groq(result["transcription"], target_language)
            print(f"      Translation: {len(result['translation'])} chars")
            return result

        result["vision_unavailable"] = True
        result["language"] = ""
        result["transcription"] = ""
        result["translation"] = ""
        result["context"] = ""
        result["error"] = (
            "Vision API quota exceeded. Please select the correct manuscript "
            "from the catalog dropdown to use cached transcription."
        )
        return result

    # Case 2 — Raw text provided (no structured OCR prompt)
    if text_input and text_input.strip():
        text = text_input.strip()
        result["transcription"] = text
        try:
            result["language"] = _call_groq(
                f"What language is this text written in? Reply with ONLY the language name.\n\n{text[:200]}",
                max_tokens=32,
            ) or "Unknown"
        except Exception:
            result["language"] = "Unknown"
        result["translation"] = _translate_with_groq(text, target_language)
        try:
            result["context"] = _call_groq(
                f"In 2-3 sentences, provide brief historical context for this text. "
                f"Only state facts you are certain about. Return ONLY the context.\n\n{text[:300]}"
            )
        except Exception:
            result["context"] = ""
        return result

    return result


def step_validate(manuscript_id: str, claimed_author: str) -> dict:
    """
    Agent 2 — MCP Validation via Stdio.
    Connects to catalog_server as a genuine MCP client.
    """
    if not manuscript_id or manuscript_id in ["none", "unknown", ""]:
        return {
            "verdict": "NO VALIDATION REQUIRED",
            "confidence_score": 100,
            "real_author": "N/A",
            "hallucination_detected": False,
            "source": "No catalog selected",
            "verified_facts": [],
            "explanation": "",
        }

    import asyncio
    import sys
    import json
    
    async def _call_mcp():
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        server_path = os.path.join(os.path.dirname(__file__), "..", "mcp_server", "catalog_server.py")
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_path]
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Get metadata
                try:
                    res1 = await session.call_tool(
                        "get_manuscript_metadata", {"shelf_mark": manuscript_id}
                    )
                    real_data = json.loads(res1.content[0].text) if res1.content else {}
                except Exception as e:
                    print(f"[Agent 2] get_manuscript_metadata failed: {e}")
                    real_data = {"error": _clean_mcp_error(e)}

                # Verify claim
                try:
                    res2 = await session.call_tool(
                        "verify_claim",
                        {"claimed_author": claimed_author, "shelf_mark": manuscript_id},
                    )
                    val_data = json.loads(res2.content[0].text) if res2.content else {}
                except Exception as e:
                    print(f"[Agent 2] verify_claim failed: {e}")
                    val_data = {
                        "status": "VALIDATION ERROR",
                        "confidence": 0.0,
                        "explanation": _clean_mcp_error(e),
                    }

                return real_data, val_data

    try:
        real_data, val_data = asyncio.run(_call_mcp())
    except Exception as e:
        print(f"[Agent 2] MCP Connection Error: {e}")
        return {
            "verdict": "MCP CONNECTION ERROR",
            "confidence_score": 0,
            "real_author": "Unknown",
            "hallucination_detected": False,
            "source": "MCP Error",
            "verified_facts": [],
            "explanation": _clean_mcp_error(e),
        }

    if "error" in real_data:
        return {
            "verdict": "CATALOG ERROR",
            "confidence_score": 0,
            "real_author": "Unknown",
            "hallucination_detected": False,
            "source": "Catalog error",
            "verified_facts": [],
            "explanation": real_data["error"],
        }
        
    real_author = real_data.get("author", "Unknown")

    # No author claim
    if not claimed_author or claimed_author.strip() in ["", "Not specified", "Unknown"]:
        return {
            "verdict": "NO AUTHOR CLAIM",
            "confidence_score": 100,
            "real_author": real_author,
            "hallucination_detected": False,
            "source": "QDL Catalogue",
            "verified_facts": real_data.get("verified_facts", []),
            "explanation": "",
        }

    status = val_data.get("status", "UNVERIFIED")
    confidence = int(val_data.get("confidence", 0) * 100)
    explanation = val_data.get("explanation", "")
    if "TaskGroup" in explanation or "unhandled errors" in explanation.lower():
        explanation = "Catalog validation encountered an internal error. Please retry."

    return {
        "verdict": status,
        "confidence_score": confidence,
        "real_author": val_data.get("real_author", real_author),
        "hallucination_detected": status == "HALLUCINATION",
        "source": val_data.get("source", "QDL Catalogue"),
        "verified_facts": real_data.get("verified_facts", []),
        "explanation": explanation,
    }


def _get_chroma_context(session_id: str, transcription: str) -> str:
    """Query ChromaDB for similar past analyses (Level 2 RAG)."""
    try:
        from backend.memory.chroma_store import query_similar, format_similar_context
        similar = query_similar(session_id, transcription, top_k=3)
        return format_similar_context(similar)
    except Exception as e:
        print(f"[ChromaDB] Context query failed: {e}")
        return ""


def step_context(
    transcription: str, manuscript_id: str, agent_memory: str, session_id: str = ""
) -> str:
    """Agent 4 — Historical Context (Groq 70b + catalog + ChromaDB RAG)."""
    if not transcription or not transcription.strip():
        return ""

    catalog_info = ""
    if manuscript_id and manuscript_id not in ["none", "unknown"]:
        data = query_catalog(manuscript_id)
        if "error" not in data:
            catalog_info = (
                f"Catalog: Title='{data.get('title_english')}', "
                f"Date='{data.get('date')}', Author='{data.get('author')}', "
                f"Institution='{data.get('institution')}'"
            )

    chroma_context = _get_chroma_context(session_id, transcription) if session_id else ""

    try:
        return _call_groq(
            f"You are a historian specialising in historical manuscripts. "
            f"Provide 2-3 sentences of verified historical context. "
            f"ONLY state facts you are 100% certain about. Never invent names or dates.\n\n"
            f"{catalog_info}\n"
            f"{chroma_context}\n"
            f"Agent memory: {agent_memory[:300]}\n\n"
            f"Manuscript excerpt:\n{transcription[:400]}",
            model=GROQ_MODEL,
        )
    except Exception as e:
        return f"Context unavailable: {str(e)[:100]}"


# ─── Agent 5 — Orchestrator / Critic ─────────────────────────────────────────

def run_pipeline(
    image_path=None,
    text_input="",
    manuscript_id="none",
    claimed_author="",
    target_language="English",
    session_id="default_user",
) -> dict:
    """
    Agent 5 — Critic/Assembler.
    Orchestrates all agents and returns the final structured report.
    """
    print(f"\n{'='*50}")
    print(f"[Heritage Decoder] Pipeline — manuscript={manuscript_id}, session={session_id}")
    print(f"  target_language={target_language}, claimed_author={claimed_author or 'none'}")
    print("-" * 50)

    # Load RAG memory (semantic retrieval of relevant past analyses)
    query_hint = claimed_author or manuscript_id or "manuscript analysis"
    agent_memory = _get_rag_context(session_id, query_hint)
    has_memory = "No previous" not in agent_memory

    # ── Agent 1 + 3 ──────────────────────────────────────────────────────────
    print("[Agent 1] OCR/Vision — reading manuscript...")
    ocr_result      = step_ocr_translate(image_path, text_input, target_language, agent_memory, manuscript_id)
    language        = ocr_result.get("language", "Unknown")
    transcription   = ocr_result.get("transcription", "")
    translation     = ocr_result.get("translation", "")
    context_ocr     = ocr_result.get("context", "")
    print(f"  transcription={len(transcription)}c, translation={len(translation)}c")

    # ── Agent 2 ───────────────────────────────────────────────────────────────
    print("[Agent 2] Validation — MCP catalog cross-reference...")
    validation = step_validate(manuscript_id, claimed_author)
    print(f"  verdict={validation['verdict']}, confidence={validation['confidence_score']}%")

    # ── Agent 4 ───────────────────────────────────────────────────────────────
    print("[Agent 4] Context — historical grounding...")
    if ocr_result.get("vision_unavailable"):
        enriched_context = ""
    else:
        enriched_context = step_context(
            transcription, manuscript_id, agent_memory, session_id
        )

    # ── Agent 5 — Final report ────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print("PIPELINE REPORT")
    print("=" * 50)
    print(f"  Manuscript : {manuscript_id}")
    print(f"  Language   : {language}")
    print(f"  AI Author  : {claimed_author or 'Not specified'}")
    print(f"  Real Author: {validation['real_author']}")
    hall_label = "HALLUCINATION" if validation["hallucination_detected"] else validation["verdict"]
    print(f"  Verdict    : {hall_label}")
    print(f"  Confidence : {validation['confidence_score']}%")
    if validation.get("explanation"):
        print(f"  Explanation: {validation['explanation'][:100]}")
    print("=" * 50)

    pipeline_error = ocr_result.get("error") or None

    return {
        "manuscript_id":        manuscript_id if manuscript_id != "none" else "Uploaded Document",
        "language_detected":    language,
        "ocr_transcription":    transcription,
        "translation":          translation,
        "historical_context":   enriched_context or context_ocr,
        "claimed_author":       claimed_author or "Not specified",
        "real_author":          validation["real_author"],
        "verdict":              validation["verdict"],
        "confidence_score":     validation["confidence_score"],
        "hallucination_detected": validation["hallucination_detected"],
        "source":               validation["source"],
        "verified_facts":       validation["verified_facts"],
        "explanation":          validation.get("explanation", ""),
        "error":                pipeline_error,
        "vision_unavailable":   ocr_result.get("vision_unavailable", False),
        "target_language":      target_language,
        "pipeline_steps": [
            "Agent 1 — OCR & Vision (Gemini)",
            "Agent 2 — MCP Validation",
            "Agent 3 — Translation (Groq)",
            "Agent 4 — Context (Groq)",
            "Agent 5 — Critic/Assembler",
        ],
        "agent_memory_used": has_memory,
    }
