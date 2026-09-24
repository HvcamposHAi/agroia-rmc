# Dockerfile da API para Hugging Face Spaces.
#
# Esta branch (huggingface) existe SÓ para o deploy no HF Spaces — por isso
# sobrescreve o Dockerfile de coleta (que traz Chromium) e o README.
#
# Imagem enxuta: instala apenas o que api/main.py importa de verdade.
# Verificado bloqueando os imports: api.main sobe sem sentence-transformers,
# torch, playwright, pandas, numpy, openai, google e scipy — todos são lazy.

FROM python:3.11.9-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# O HF Spaces roda como usuário não-root (uid 1000) e espera escrita em /home/user
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY --chown=user . .

# O HF Spaces expõe a porta 7860 (declarada em app_port no README.md)
ENV PORT=7860
EXPOSE 7860

CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT
