from groq import Groq
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

def get_historical_context_with_search(topic: str, transcription: str = "") -> dict:
    """
    Utilise Gemini 2.0 Flash avec Google Search Grounding
    pour trouver du contexte historique vérifié sur n'importe quel manuscrit.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "context": f"No context found for: {topic}",
            "source": "None",
            "verified": False
        }

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            tools="google_search_retrieval"
        )

        query = f"""
        You are an expert archivist and historian.
        Search for verified historical information about this manuscript topic: {topic}
        Transcription excerpt: {transcription[:300] if transcription else "not available"}
        
        Find:
        - The real author if known
        - The historical period and region
        - The academic significance
        - Any verified attribution from libraries or academic sources
        
        Only state what you find in real sources. If author is unknown, say so explicitly.
        Cite your sources with URLs when available.
        """

        response = model.generate_content(query)
        
        sources = []
        grounding_metadata = getattr(response.candidates[0], 'grounding_metadata', None)
        if grounding_metadata:
            chunks = getattr(grounding_metadata, 'grounding_chunks', [])
            for chunk in chunks:
                web = getattr(chunk, 'web', None)
                if web:
                    sources.append({
                        "title": getattr(web, 'title', ''),
                        "url": getattr(web, 'uri', '')
                    })

        return {
            "context": response.text,
            "source": sources if sources else "Google Search Grounding",
            "verified": True,
            "search_grounded": True
        }

    except Exception as e:
        return {
            "context": f"Search unavailable: {str(e)}",
            "source": "None",
            "verified": False,
            "search_grounded": False
        }


def generate_context_with_groq(topic: str, transcription: str = "") -> dict:
    """
    Flow complet :
    1. Gemini 2.0 Flash + Google Search Grounding → contexte sourcé depuis le web
    2. Groq llama-3.3-70b → reformule le contexte trouvé de manière concise
    """
    # Étape 1 — Google Search Grounding via Gemini
    search_result = get_historical_context_with_search(topic, transcription)

    # Étape 2 — Groq reformule si le contexte a été trouvé
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key or not search_result["verified"]:
        return search_result

    try:
        client = Groq(api_key=groq_api_key)
        prompt = f"""You are a historian. Based on this verified search result, 
provide a concise and accurate historical context. 
Do NOT invent any facts not present in the source.
If the author is unknown, state that explicitly.

Verified source content:
{search_result['context']}

Topic: {topic}
"""
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_completion_tokens=500
        )

        return {
            "context": completion.choices[0].message.content.strip(),
            "source": search_result["source"],
            "verified": True,
            "search_grounded": True
        }

    except Exception as e:
        # Fallback sur le résultat brut de Gemini si Groq échoue
        return search_result