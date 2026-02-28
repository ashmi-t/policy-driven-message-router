FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/

# Default: run API (override in docker-compose for worker)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
