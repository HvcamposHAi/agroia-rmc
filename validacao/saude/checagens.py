"""Pré-requisitos e checagens de saúde executados no início de toda execução (seção 2).

Cada checagem devolve {nome, ok, mensagem, critico, afeta}. `afeta` lista as etapas que
não podem rodar se a checagem falhar. Nada aqui pede input humano.

Uso: python -m validacao.saude.checagens [--sem-chrome] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from validacao.comum import RAIZ_VALIDACAO, carimbo, carregar_config, carregar_env, versao_claude


def _r(nome, ok, msg, afeta, critico=False, extra=None):
    return {"nome": nome, "ok": bool(ok), "mensagem": msg, "afeta": afeta, "critico": critico,
            **({"extra": extra} if extra else {})}


def chk_supabase(cfg):
    try:
        from validacao.snapshot.congelar import cliente
        t = time.monotonic()
        sb = cliente()
        sb.table("licitacoes").select("id").limit(1).execute()
        return _r("Supabase acessível", True, f"select 1 em {time.monotonic() - t:.1f} s",
                  ["snapshot", "a1", "a2", "b"], critico=True)
    except Exception as e:  # noqa: BLE001
        return _r("Supabase acessível", False, str(e)[:300], ["snapshot", "a1", "a2", "b"], critico=True)


def chk_backend(cfg):
    import requests
    url = cfg["fontes"]["agroia_api_url"].rstrip("/") + "/health"
    ult = ""
    for n in range(3):
        try:
            t = time.monotonic()
            r = requests.get(url, timeout=70)
            if r.ok and r.json().get("status") == "ok":
                return _r("Backend AgroIA", True, f"/health ok em {time.monotonic() - t:.1f} s (tentativa {n + 1})",
                          ["a2", "b"])
            ult = f"HTTP {r.status_code}: {r.text[:120]}"
        except Exception as e:  # noqa: BLE001
            ult = str(e)[:200]
        time.sleep(5)
    return _r("Backend AgroIA", False, ult, ["a2", "b"])


def chk_backend_recursos(cfg):
    """Verifica se o backend aceita {motor, sem_cache, rastreio} em /chat/stream (Parte B)."""
    import requests
    carregar_env()
    chave = os.getenv("API_SECRET_KEY") or os.getenv("AGROIA_API_KEY")
    if not chave:
        return _r("Backend: seleção de motor por requisição", False,
                  "API_SECRET_KEY ausente em validacao/.env", ["b"])
    url = cfg["fontes"]["agroia_api_url"].rstrip("/") + "/config/motor"
    try:
        r = requests.get(url, timeout=70)
        motores = [m["motor"] for m in r.json().get("motores", []) if m.get("disponivel")]
        return _r("Backend: motores disponíveis", bool(motores), f"disponíveis: {motores}", ["b"],
                  extra={"motores": motores, "motor_ativo": r.json().get("motor_ativo")})
    except Exception as e:  # noqa: BLE001
        return _r("Backend: motores disponíveis", False, str(e)[:200], ["b"])


def chk_portal(cfg):
    import requests
    try:
        t = time.monotonic()
        r = requests.get(cfg["fontes"]["portal_url"], timeout=cfg["acesso"]["timeout_http_s"],
                         headers={"User-Agent": "Mozilla/5.0 " + cfg["acesso"]["user_agent"]})
        ok = r.ok and "ddlOrgao" in r.text and f'value="{cfg["fontes"]["portal_orgao"]}"' in r.text
        return _r("Portal da Prefeitura acessível", ok,
                  f"HTTP {r.status_code} em {time.monotonic() - t:.1f} s" + ("" if ok else "; órgão FAAC ausente do filtro"),
                  ["a1", "a2"])
    except Exception as e:  # noqa: BLE001
        return _r("Portal da Prefeitura acessível", False, str(e)[:200], ["a1", "a2"])


def chk_playwright(cfg):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            v = b.version
            b.close()
        return _r("Playwright Chromium", True, f"Chromium {v}", ["a1"])
    except Exception as e:  # noqa: BLE001
        return _r("Playwright Chromium", False, f"{str(e)[:200]} (rode: python -m playwright install chromium)", ["a1"])


def chk_claude(cfg):
    v = versao_claude()
    return _r("Claude Code instalado", bool(v), v or "comando 'claude' não encontrado", ["a1_chrome", "a2"])


def chk_flags(cfg):
    from validacao.claude_chrome import _exe
    try:
        ajuda = subprocess.run([_exe(), "--help"], capture_output=True, text=True, timeout=60,
                               encoding="utf-8", errors="replace").stdout
    except Exception as e:  # noqa: BLE001
        return _r("Flags do CLI", False, str(e)[:200], ["a1_chrome", "a2"])
    exigidas = ["--chrome", "--model", "--output-format", "--verbose", "--permission-mode",
                "--allowedTools", "--disallowedTools", "--tools", "--no-session-persistence"]
    faltam = [f for f in exigidas if f not in ajuda]
    # --max-turns não aparece no --help da 2.1.x, mas é aceito (verificado em 26/09/2026).
    return _r("Flags do CLI", not faltam, "todas presentes" if not faltam else f"ausentes: {faltam}",
              ["a1_chrome", "a2"], extra={"verificadas": exigidas})


def chk_chrome(cfg):
    from validacao.claude_chrome import sonda
    d = RAIZ_VALIDACAO / "execucoes" / "_sondas"
    r = sonda(cfg, d, timeout_s=120)
    return _r("Extensão Claude in Chrome conectada", r["ok"],
              f"sonda {r['status']} em {r['duracao_s']} s", ["a1_chrome", "a2"])


def chk_permissoes_sites(cfg):
    """A extensão precisa ter permissão nos pontos de partida das duas condições da A2."""
    from validacao.claude_chrome import sonda_sites
    f = cfg["fontes"]
    urls = [f["portal_url"], f["agroia_front_url"], f["ceasa_pr_url"]]
    # Um PDF real da plataforma no Google Drive (a condição AGROIA precisa abrir os editais).
    try:
        from validacao.snapshot.congelar import cliente
        d = (cliente().table("documentos_licitacao").select("url_publica")
             .ilike("url_publica", "%drive.google.com%").limit(1).execute().data)
        if d:
            urls.append(d[0]["url_publica"])
    except Exception:
        pass
    r = sonda_sites(cfg, RAIZ_VALIDACAO / "execucoes" / "_sondas", urls)
    negados = [u for u, ok in r.items() if ok is False]
    nao_testados = [u for u, ok in r.items() if ok is None]
    ok = not negados and not nao_testados
    msg = "todos os sites permitidos" if ok else (
        f"sem permissão na extensão: {negados}" if negados else f"não testados: {nao_testados}")
    return _r("Permissões de site da extensão", ok, msg, ["a2"], extra={"resultado": r})


def chk_env(cfg):
    carregar_env()
    faltam = [v for v in ("SUPABASE_URL", "SUPABASE_KEY") if not os.getenv(v)]
    opc = [v for v in ("API_SECRET_KEY",) if not os.getenv(v)]
    ok = not faltam
    msg = "ok" if ok else f"ausentes: {faltam}"
    if opc:
        msg += f"; opcionais ausentes: {opc} (necessária para a Parte B)"
    return _r("Variáveis de ambiente", ok, msg, ["snapshot", "a1", "a2", "b"], critico=True)


def rodar(cfg: dict | None = None, incluir_chrome: bool = True) -> dict:
    cfg = cfg or carregar_config()
    checks = [chk_env, chk_supabase, chk_portal, chk_backend, chk_backend_recursos, chk_playwright,
              chk_claude, chk_flags]
    if incluir_chrome:
        checks += [chk_chrome, chk_permissoes_sites]
    resultados = []
    for f in checks:
        try:
            resultados.append(f(cfg))
        except Exception as e:  # noqa: BLE001
            resultados.append(_r(f.__name__, False, f"falha na checagem: {e}", []))
    bloqueadas = sorted({e for r in resultados if not r["ok"] for e in r["afeta"]})
    return {"quando": carimbo(), "checagens": resultados, "etapas_bloqueadas": bloqueadas,
            "abortar": any(r["critico"] and not r["ok"] for r in resultados)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem-chrome", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = rodar(incluir_chrome=not a.sem_chrome)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    for c in r["checagens"]:
        print(f"[{'OK ' if c['ok'] else 'FALHA'}] {c['nome']}: {c['mensagem']}")
    print("Etapas bloqueadas:", r["etapas_bloqueadas"] or "nenhuma")


if __name__ == "__main__":
    main()
