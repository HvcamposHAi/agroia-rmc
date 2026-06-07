# Imagem com Chromium + dependências do Playwright já instaladas.
# A tag DEVE casar com playwright==1.40.0 (requirements.txt).
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Idempotente: a imagem base já traz os browsers; no-op se já presentes.
RUN python -m playwright install chromium

COPY . .

# Render injeta $PORT. WORKDIR=/app garante que
# subprocess.Popen(["python","etapa2_itens_v9.py",...]) e os arquivos
# relativos (coleta_status.json, coleta_config.json) resolvam.
ENV PORT=8000
CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT
