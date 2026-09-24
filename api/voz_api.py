"""Router isolado: voz neural (texto → fala) para os chats, via Azure Speech.

As vozes do navegador (Web Speech API) soam robóticas no Chrome/Windows; as
vozes neurais do Azure (Francisca, Antônio, Thalita…) soam humanas e iguais em
qualquer navegador ou celular. O frontend tenta este endpoint primeiro e, se
ele responder 503 (Azure não configurado, cota esgotada, fora do ar), volta
sozinho para a voz do navegador.

Configuração (Render/HF Spaces): AZURE_SPEECH_KEY e AZURE_SPEECH_REGION
(ex.: brazilsouth). O plano gratuito F0 do Azure Speech cobre vozes neurais.

Incluído em api/main.py com duas linhas (import + include_router).
verify_api_key é replicado localmente (mesma API_SECRET_KEY) para evitar
import circular com api.main — igual a api/benchmark_api.py.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections import OrderedDict
from xml.sax.saxutils import escape

import requests
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.responses import Response
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voz"])

_API_SECRET_KEY = os.getenv("API_SECRET_KEY")
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Vozes neurais oferecidas por idioma da interface. A primeira é o padrão.
# (id Azure, rótulo exibido no seletor)
VOZES: dict[str, list[tuple[str, str]]] = {
    "pt": [
        ("pt-BR-FranciscaNeural", "Francisca"),
        ("pt-BR-AntonioNeural", "Antônio"),
        ("pt-BR-ThalitaMultilingualNeural", "Thalita"),
    ],
    "en": [
        ("en-US-AvaMultilingualNeural", "Ava"),
        ("en-US-AndrewMultilingualNeural", "Andrew"),
        ("en-US-JennyNeural", "Jenny"),
    ],
    "es": [
        ("es-ES-ElviraNeural", "Elvira"),
        ("es-ES-AlvaroNeural", "Álvaro"),
        ("es-MX-DaliaNeural", "Dalia (México)"),
    ],
}
_VOZES_VALIDAS = {vid for lista in VOZES.values() for vid, _ in lista}

MAX_CARACTERES = 1500          # por requisição; o frontend manda a resposta em partes
_CACHE_MAX = 200               # respostas repetidas não gastam cota de novo
_cache: OrderedDict[str, bytes] = OrderedDict()


def _verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    if not api_key or api_key != _API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key


def _config() -> tuple[str, str] | None:
    key = os.getenv("AZURE_SPEECH_KEY", "").strip()
    region = os.getenv("AZURE_SPEECH_REGION", "").strip()
    return (key, region) if key and region else None


def _ssml(texto: str, voz: str, velocidade: float) -> str:
    lang = "-".join(voz.split("-")[:2])
    pct = round((velocidade - 1.0) * 100)
    return (
        f"<speak version='1.0' xml:lang='{lang}'>"
        f"<voice name='{voz}'><prosody rate='{pct:+d}%'>{escape(texto)}</prosody></voice>"
        "</speak>"
    )


class TtsRequest(BaseModel):
    texto: str = Field(..., min_length=1)
    voz: str | None = None
    idioma: str | None = "pt"
    velocidade: float = Field(1.0, ge=0.7, le=1.4)


@router.get("/voz/status")
def voz_status():
    """Diz ao frontend se a voz neural está disponível e quais vozes oferecer."""
    return {
        "neural": _config() is not None,
        "vozes": {
            idioma: [{"id": vid, "nome": nome} for vid, nome in lista]
            for idioma, lista in VOZES.items()
        },
    }


@router.post("/voz/tts", dependencies=[Depends(_verify_api_key)])
def voz_tts(req: TtsRequest):
    """Sintetiza um trecho em MP3. 503 ⇒ o frontend usa a voz do navegador."""
    cfg = _config()
    if cfg is None:
        raise HTTPException(status_code=503, detail="Voz neural não configurada")

    idioma = (req.idioma or "pt")[:2]
    voz = req.voz if req.voz in _VOZES_VALIDAS else VOZES.get(idioma, VOZES["pt"])[0][0]
    texto = req.texto.strip()[:MAX_CARACTERES]

    chave = hashlib.sha256(f"{voz}|{req.velocidade:.2f}|{texto}".encode()).hexdigest()
    if chave in _cache:
        _cache.move_to_end(chave)
        return Response(content=_cache[chave], media_type="audio/mpeg")

    key, region = cfg
    try:
        r = requests.post(
            f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
            headers={
                "Ocp-Apim-Subscription-Key": key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
                "User-Agent": "agroia-rmc",
            },
            data=_ssml(texto, voz, req.velocidade).encode("utf-8"),
            timeout=20,
        )
    except requests.RequestException as e:
        logger.warning("Azure TTS indisponível: %s", e)
        raise HTTPException(status_code=503, detail="Voz neural indisponível")

    if r.status_code != 200 or not r.content:
        # 401 chave errada, 429 cota/limite — em todos os casos o navegador assume.
        logger.warning("Azure TTS falhou: HTTP %s %s", r.status_code, r.text[:200])
        raise HTTPException(status_code=503, detail="Voz neural indisponível")

    _cache[chave] = r.content
    if len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return Response(content=r.content, media_type="audio/mpeg")
