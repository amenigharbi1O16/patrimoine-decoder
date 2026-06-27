# Build from project root:
#   docker build -f backend/Dockerfile -t heritage-backend .
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY data/ ./data/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

RUN python -c "from backend.mcp_server.database import init_db; init_db()"
RUN python -c "from backend.memory.chroma_store import init_store; init_store()"

EXPOSE 8080

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
