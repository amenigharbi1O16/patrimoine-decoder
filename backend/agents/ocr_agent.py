"""
Agent 1 — OCR Agent (standalone module)

This module exposes a clean `transcribe_manuscript()` function used by tests
and by the orchestrator's step_ocr_translate() when Gemini Vision is available.

Vision strategy:
  1. Try Gemini Vision (real OCR via google-generativeai)
  2. Fallback to known-manuscript mock data keyed by manuscript_id
  3. Return structured dict with language, transcription, context
"""
import os, base64, mimetypes
import google.generativeai as genai
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(env_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

GEMINI_MODEL = "gemini-2.0-flash"

# Known manuscript mock data (for demo / quota-exceeded fallback)
KNOWN_MANUSCRIPTS = {
    "or_9011": {
        "language": "Arabic",
        "transcription": (
            "رسالة فلكية في أحكام النجوم — كتاب في علم أحكام النجوم والطوالع "
            "والبروج والكواكب. وهذا الكتاب مشتمل على فصول عديدة في معرفة الطوالع."
        ),
        "context": (
            "18th-century Arabic astrological treatise, Maghreb or Ottoman Empire. "
            "Author: UNKNOWN — do not attribute to any named figure."
        ),
    },
    "add_ms_7474": {
        "language": "Arabic",
        "transcription": (
            "كتاب المجسطي — تأليف بطليموس الحكيم. الكتاب الأول من كتب المجسطي "
            "في علم الهيئة والفلك. نُسخ هذا الكتاب سنة ٦٨٦ هجري."
        ),
        "context": (
            "Kitab al-Majisti — Arabic translation of Ptolemy's Almagest. "
            "Copied 1287 CE (686 AH). Translated by Ishaq ibn Hunayn."
        ),
    },
}


def transcribe_manuscript(image_path: str, manuscript_id: str = "") -> dict:
    """
    Transcribe a manuscript image.

    Returns:
        {
            "agent": "ocr_agent",
            "language": str,
            "transcription": str,
            "context": str,
            "method": "gemini_vision" | "mock" | "unknown",
            "error": str | None
        }
    """
    if not os.path.exists(image_path):
        return {
            "agent": "ocr_agent",
            "error": f"Image not found: {image_path}",
            "language": "Unknown",
            "transcription": "",
            "context": "",
            "method": "error",
        }

    # Attempt real Gemini Vision OCR
    if GOOGLE_API_KEY:
        try:
            model = genai.GenerativeModel(GEMINI_MODEL)
            mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
            with open(image_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()

            prompt = (
                "You are a world-class paleographer. Transcribe the text in this "
                "manuscript image exactly as written. Identify the language. "
                "Format:\n[LANGUAGE]: <lang>\n[TRANSCRIPTION]: <text>"
            )
            response = model.generate_content([
                prompt,
                {"mime_type": mime, "data": img_data},
            ])
            raw = response.text
            # Parse response
            lang = _extract(raw, "LANGUAGE") or "Arabic"
            trans = _extract(raw, "TRANSCRIPTION") or raw[:600]
            return {
                "agent": "ocr_agent",
                "language": lang,
                "transcription": trans,
                "context": "",
                "method": "gemini_vision",
                "error": None,
            }
        except Exception as e:
            print(f"[OCR Agent] Gemini Vision failed: {e}")

    # Fallback — known manuscript mock
    ms_key = manuscript_id.replace("-", "_").lower()
    for k, v in KNOWN_MANUSCRIPTS.items():
        if k in ms_key or ms_key in k:
            return {
                "agent": "ocr_agent",
                "language": v["language"],
                "transcription": v["transcription"],
                "context": v["context"],
                "method": "mock",
                "error": None,
            }

    return {
        "agent": "ocr_agent",
        "language": "Arabic",
        "transcription": (
            "نص عربي — تعذّر التعرف على النص تلقائياً. "
            "يرجى استخدام وضع إدخال النص."
        ),
        "context": "OCR unavailable — Vision API quota exceeded or key missing.",
        "method": "fallback",
        "error": None,
    }


def _extract(text: str, label: str) -> str:
    """Extract [LABEL]: value from structured model output."""
    for line in text.split("\n"):
        if line.strip().startswith(f"[{label}]:"):
            return line.split(":", 1)[1].strip()
    return ""


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/manuscripts/add_ms_7474.jpg"
    result = transcribe_manuscript(path, manuscript_id="add_ms_7474")
    print(f"=== OCR Agent ===")
    print(f"Method      : {result['method']}")
    print(f"Language    : {result['language']}")
    print(f"Transcription: {result['transcription'][:200]}...")