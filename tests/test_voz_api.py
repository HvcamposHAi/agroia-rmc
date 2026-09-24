"""Testes do router de voz neural (api/voz_api.py) — sem chamar o Azure de verdade."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.voz_api as voz_api

CHAVE_API = "chave-teste"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(voz_api, "_API_SECRET_KEY", CHAVE_API)
    voz_api._cache.clear()
    app = FastAPI()
    app.include_router(voz_api.router)
    return TestClient(app)


def _com_azure(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "k")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "brazilsouth")


def test_status_sem_azure(client, monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    r = client.get("/voz/status")
    assert r.status_code == 200
    assert r.json()["neural"] is False
    assert r.json()["vozes"]["pt"][0]["id"] == "pt-BR-FranciscaNeural"


def test_tts_exige_api_key(client, monkeypatch):
    _com_azure(monkeypatch)
    assert client.post("/voz/tts", json={"texto": "oi"}).status_code == 403


def test_tts_sem_azure_responde_503(client, monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    r = client.post("/voz/tts", json={"texto": "oi"}, headers={"X-API-Key": CHAVE_API})
    assert r.status_code == 503


def test_tts_envia_ssml_e_usa_cache(client, monkeypatch):
    _com_azure(monkeypatch)
    resposta = MagicMock(status_code=200, content=b"MP3")
    with patch.object(voz_api.requests, "post", return_value=resposta) as post:
        corpo = {"texto": "Tomate & alface <3", "voz": "pt-BR-AntonioNeural", "velocidade": 1.1}
        r1 = client.post("/voz/tts", json=corpo, headers={"X-API-Key": CHAVE_API})
        r2 = client.post("/voz/tts", json=corpo, headers={"X-API-Key": CHAVE_API})

    assert r1.status_code == r2.status_code == 200
    assert r1.content == b"MP3" and r1.headers["content-type"] == "audio/mpeg"
    assert post.call_count == 1  # a segunda veio do cache
    url = post.call_args.args[0]
    ssml = post.call_args.kwargs["data"].decode()
    assert url == "https://brazilsouth.tts.speech.microsoft.com/cognitiveservices/v1"
    assert "name='pt-BR-AntonioNeural'" in ssml
    assert "rate='+10%'" in ssml
    assert "Tomate &amp; alface &lt;3" in ssml  # texto escapado no XML


def test_tts_voz_desconhecida_usa_padrao_do_idioma(client, monkeypatch):
    _com_azure(monkeypatch)
    resposta = MagicMock(status_code=200, content=b"MP3")
    with patch.object(voz_api.requests, "post", return_value=resposta) as post:
        client.post("/voz/tts", json={"texto": "hola", "voz": "x'/><evil", "idioma": "es"},
                    headers={"X-API-Key": CHAVE_API})
    assert "name='es-ES-ElviraNeural'" in post.call_args.kwargs["data"].decode()


def test_tts_falha_no_azure_vira_503(client, monkeypatch):
    _com_azure(monkeypatch)
    resposta = MagicMock(status_code=429, content=b"", text="quota")
    with patch.object(voz_api.requests, "post", return_value=resposta):
        r = client.post("/voz/tts", json={"texto": "oi"}, headers={"X-API-Key": CHAVE_API})
    assert r.status_code == 503
