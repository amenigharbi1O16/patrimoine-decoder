from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

HISTORICAL_CONTEXT = {
    "almagest": "The Almagest was written by Ptolemy in the 2nd century CE and translated into Arabic by Ishaq ibn Hunayn in the 9th century. It remained the authoritative astronomical text until Copernicus.",
    "astrological": "18th century astrological manuscripts in the Maghreb often compiled earlier works. Authors were frequently anonymous or pseudonymously attributed to famous scholars.",
    "arabic_manuscripts": "The British Library holds over 14,000 Arabic manuscripts. Many were acquired from the Ottoman Empire and North Africa during the 19th century.",
    "ibn al-haytham": "Ibn al-Haytham was a pioneering Arab mathematician, astronomer, and physicist of the Islamic Golden Age. He is best known for his work in optics."
}

def get_historical_context(topic: str) -> dict:
    """
    Retourne du contexte historique vérifié pour un sujet donné.
    Simule ChromaDB RAG avec une base de textes vérifiés.
    """
    topic_lower = topic.lower()
    for key, context in HISTORICAL_CONTEXT.items():
        if key in topic_lower:
            return {
                "context": context,
                "source": "Academic Historical Corpus",
                "verified": True
            }
    return {
        "context": f"No verified context found for: {topic}",
        "source": "None",
        "verified": False
    }

def generate_context_with_groq(topic: str) -> dict:
    """
    Simule l'agent contextuel avec Groq pour extraire le contexte pertinent.
    """
    base_context = get_historical_context(topic)
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "votre_cle_groq_ici":
        return base_context  # Fallback gracefully
        
    try:
        client = Groq(api_key=api_key)
        prompt = f"Tu es un historien. Utilise ce contexte vérifié pour l'expliquer de manière concise: {base_context['context']}"
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_completion_tokens=500
        )
        return {
            "context": completion.choices[0].message.content.strip(),
            "source": base_context["source"],
            "verified": base_context["verified"]
        }
    except Exception as e:
        return base_context

