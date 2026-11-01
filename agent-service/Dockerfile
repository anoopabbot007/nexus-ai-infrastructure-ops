# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --disable-pip-version-check --timeout 120 --retries 5 -r requirements.txt
COPY agent_service ./agent_service
EXPOSE 8000 8001 8002
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=4 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "agent_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
