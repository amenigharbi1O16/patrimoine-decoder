"""
Database models — Heritage Decoder

Tables:
  manuscripts      : catalog of verified manuscripts (seeded at startup)
  analysis_history : pipeline results per user session (with RAG embeddings)
  users            : registered accounts (hashed password + JWT auth)
"""
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import json, os

os.makedirs("data", exist_ok=True)

Base = declarative_base()
engine = create_engine("sqlite:///data/catalogue.db", echo=False)
Session = sessionmaker(bind=engine)


# ─── Models ───────────────────────────────────────────────────────────────────

class User(Base):
    """Registered user account."""
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True)
    username        = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow)
    is_active       = Column(Boolean, default=True)


class Manuscript(Base):
    """Verified archival manuscript record (MCP catalog)."""
    __tablename__ = "manuscripts"
    id             = Column(Integer, primary_key=True)
    qdl_id         = Column(String, unique=True)
    title_arabic   = Column(String)
    title_english  = Column(String)
    date           = Column(String)
    author         = Column(String)
    institution    = Column(String)
    verified_facts = Column(Text)


class AnalysisHistory(Base):
    """Full pipeline result stored per user session."""
    __tablename__ = "analysis_history"
    id                     = Column(Integer, primary_key=True)
    session_id             = Column(String, default="default_user")
    manuscript_id          = Column(String)
    image_filename         = Column(String)
    target_language        = Column(String)
    claimed_author         = Column(String)
    verdict                = Column(String)
    confidence_score       = Column(Integer)
    ocr_transcription      = Column(Text)
    translation            = Column(Text)          # stored for RAG context
    hallucination_detected = Column(String)
    embedding              = Column(Text)          # JSON float[] for RAG
    historical_context     = Column(Text)
    explanation            = Column(Text)
    verified_facts         = Column(Text)          # JSON array
    language_detected      = Column(String)
    real_author            = Column(String)
    source                 = Column(String)
    created_at             = Column(DateTime, default=datetime.utcnow)


# ─── Seed data ────────────────────────────────────────────────────────────────

def init_db():
    Base.metadata.create_all(engine)

    # Add embedding column if DB was created before this version
    try:
        with engine.connect() as conn:
            conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE analysis_history ADD COLUMN embedding TEXT"
                )
            )
            conn.commit()
    except Exception:
        pass  # column already exists

    # Add translation column if missing
    try:
        with engine.connect() as conn:
            conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE analysis_history ADD COLUMN translation TEXT"
                )
            )
            conn.commit()
    except Exception:
        pass

    for col, col_type in [
        ("historical_context", "TEXT"),
        ("explanation", "TEXT"),
        ("verified_facts", "TEXT"),
        ("language_detected", "VARCHAR"),
        ("real_author", "VARCHAR"),
        ("source", "VARCHAR"),
    ]:
        try:
            with engine.connect() as conn:
                conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE analysis_history ADD COLUMN {col} {col_type}"
                    )
                )
                conn.commit()
        except Exception:
            pass

    session = Session()
    manuscripts = [
        Manuscript(
            qdl_id="add_ms_7474",
            title_arabic="كتاب المجسطي",
            title_english="Almagest (Arabic translation)",
            date="1287 CE",
            author="Claudius Ptolemy (translated by Ishaq ibn Hunayn)",
            institution="British Library",
            verified_facts=json.dumps([
                "Copied in 1287 CE",
                "Arabic translation of Ptolemy Almagest",
                "Translated by Ishaq ibn Hunayn",
                "Contains astronomical tables and geometric diagrams",
                "NOT authored by Ibn al-Haytham",
            ], ensure_ascii=False),
        ),
        Manuscript(
            qdl_id="or_9011",
            title_arabic="رسالة في علم النجوم",
            title_english="Astrological Treatise",
            date="18th century",
            author="Unknown",
            institution="British Library",
            verified_facts=json.dumps([
                "18th century astrological text",
                "Origin: Maghreb or Ottoman Empire",
                "Author identity: UNVERIFIED — do not attribute",
                "Contains horoscope charts",
            ], ensure_ascii=False),
        ),
    ]

    for m in manuscripts:
        if not session.query(Manuscript).filter_by(qdl_id=m.qdl_id).first():
            session.add(m)

    session.commit()
    session.close()
    print("Database initialized successfully")


if __name__ == "__main__":
    init_db()