"""
MCP Catalog Server — Heritage Decoder
CORRECTIONS:
- validate_claim: bug fixé pour auteurs "Unknown" → HALLUCINATION correctement détectée
- Matching plus strict (évite les faux VERIFIED)
"""
from fastmcp import FastMCP
import json, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.mcp_server.database import Session, Manuscript, init_db

init_db()
mcp = FastMCP("Heritage Catalog")


def query_catalog(manuscript_id: str) -> dict:
    """Retourne les métadonnées vérifiées d'un manuscrit."""
    session = Session()
    m = session.query(Manuscript).filter_by(qdl_id=manuscript_id).first()
    session.close()
    if not m:
        return {"error": f"Manuscrit '{manuscript_id}' introuvable"}
    return {
        "qdl_id": m.qdl_id,
        "title_english": m.title_english,
        "date": m.date,
        "author": m.author,
        "institution": m.institution,
        "verified_facts": json.loads(m.verified_facts or "[]")
    }


def validate_claim(manuscript_id: str, claimed_author: str) -> dict:
    """
    Compare l'auteur affirmé avec l'auteur réel du catalogue.
    
    CORRECTION PRINCIPALE:
    - Si real_author == "Unknown" ET claimed_author est spécifié → HALLUCINATION
    - Si real_author est connu → matching strict par mots-clés significatifs
    - Évite les faux VERIFIED
    """
    session = Session()
    m = session.query(Manuscript).filter_by(qdl_id=manuscript_id).first()
    session.close()

    if not m:
        return {
            "status": "UNVERIFIED (Not in catalog)",
            "confidence": 0.0,
            "source": f"Manuscrit '{manuscript_id}' absent du catalogue",
            "real_author": "Unknown"
        }

    real_author_raw = m.author.strip()
    real_author = real_author_raw.lower()
    claimed = claimed_author.lower().strip()

    # Cas spécial : pas de claim ou claim vide
    if not claimed or claimed in ["unknown", "", "not specified", "n/a"]:
        return {
            "status": "NO AUTHOR CLAIM",
            "confidence": 1.0,
            "source": f"QDL Catalogue — {m.institution}",
            "real_author": real_author_raw
        }

    # Unknown author in catalog — any specific claim is a hallucination
    if real_author.lower().strip() in ["unknown", ""]:
        if claimed and claimed not in ["unknown", "", "not specified", "n/a"]:
            return {
                "status": "HALLUCINATION",
                "confidence": 0.05,
                "source": f"QDL Catalogue — {m.institution}",
                "real_author": real_author_raw,
                "explanation": (
                    f"This manuscript has no verified author. "
                    f"Claiming '{claimed_author}' is a hallucination."
                ),
            }

    # ✅ CAS 2 : auteur réel connu → matching strict
    # On garde les mots de 4+ chars ET on vérifie si un mot de la claim
    # est vraiment dans l'auteur réel (pas juste une sous-chaîne partielle)
    real_words = [w for w in real_author.split() if len(w) >= 4]
    claimed_words = [w for w in claimed.split() if len(w) >= 4]

    # Matching : un mot claimed doit apparaître comme mot complet dans real_author
    def word_matches(claimed_word: str, real_text: str) -> bool:
        """Vérifie si claimed_word apparaît comme mot entier dans real_text."""
        import re
        pattern = r'\b' + re.escape(claimed_word) + r'\b'
        return bool(re.search(pattern, real_text))

    match = any(word_matches(cw, real_author) for cw in claimed_words)

    if match:
        return {
            "status": "VERIFIED",
            "confidence": 0.95,
            "source": f"QDL Catalogue — {m.institution}",
            "real_author": real_author_raw
        }
    else:
        return {
            "status": "HALLUCINATION",
            "confidence": 0.05,
            "source": f"QDL Catalogue — {m.institution}",
            "real_author": real_author_raw,
            "explanation": (
                f"Real author: '{real_author_raw}'. "
                f"Claimed: '{claimed_author}'. "
                f"No match found — this is a hallucination."
            )
        }


@mcp.tool()
def get_manuscript_metadata(shelf_mark: str) -> dict:
    """MCP Tool: Get verified metadata for a manuscript by its catalog ID."""
    return query_catalog(shelf_mark)


@mcp.tool()
def search_catalog(query: str) -> list:
    """MCP Tool: Search manuscripts by keyword."""
    session = Session()
    all_m = session.query(Manuscript).all()
    session.close()
    q = query.lower()
    results = []
    for m in all_m:
        searchable = f"{m.qdl_id} {m.title_english} {m.author} {m.date}".lower()
        if q in searchable:
            results.append({"qdl_id": m.qdl_id, "title": m.title_english, "author": m.author})
    return results or [{"message": f"No results for: {query}"}]


@mcp.tool()
def verify_claim(claimed_author: str, shelf_mark: str) -> dict:
    """MCP Tool: Verify if a claimed author attribution is accurate."""
    return validate_claim(shelf_mark, claimed_author)


if __name__ == "__main__":
    print("Starting MCP Catalog Server...", file=sys.stderr)
    mcp.run(transport="stdio")