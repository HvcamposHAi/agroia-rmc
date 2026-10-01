"""No Render o modelo local de embeddings estoura os 512 MB: a busca em PDFs nunca o carrega lá."""
import sys

import pytest

from chat import tools


@pytest.fixture(autouse=True)
def _limpar(monkeypatch):
    monkeypatch.setattr(tools, "_st_model", None)
    tools._embed_cache.clear()
    monkeypatch.delenv("RAG_EMBED_LOCAL", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)


def test_render_sem_token_nao_carrega_modelo(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setattr(tools, "get_supabase_client", lambda: None)
    antes = "sentence_transformers" in sys.modules
    r = tools.buscar_chunks_rag("como me cadastrar como fornecedor")
    assert r and "indisponível" in r[0]["erro"]
    assert tools._st_model is None
    assert ("sentence_transformers" in sys.modules) == antes


def test_override_explicito(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RAG_EMBED_LOCAL", "true")
    assert tools.embed_local_permitido()
    monkeypatch.delenv("RENDER")
    monkeypatch.setenv("RAG_EMBED_LOCAL", "false")
    assert not tools.embed_local_permitido()


def test_hf_achata_resposta(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "x")

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return [[0.5] * 384]

    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **k: R())
    assert tools.vetorizar_pergunta("teste") == [0.5] * 384
