"""Parte B: benchmark de motores LLM pelo caminho de produção (/chat/stream).

- Mesmo prompt de sistema, ferramentas e Query Agent para todos os motores (é o backend).
- Motor escolhido por requisição (`motor` no corpo; backend com suporte) ou pelo switch
  global (/config/motor), restaurado ao final.
- `sem_cache=true` (o cache de respostas é por pergunta, não por motor) e `rastreio=true`
  (eventos com nome, argumentos e resultado de cada ferramenta).
- k repetições por pergunta e motor; ordem aleatorizada com semente, motores intercalados;
  espaçamento por provedor e backoff exponencial em 429.
- Base congelada: modo "pausar_coleta" compara a assinatura da base antes e depois.

Uso: python -m validacao.b_benchmark.executar --run-id RUN [--piloto]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
import uuid

import requests
import yaml

from validacao import estado
from validacao.comum import RAIZ_VALIDACAO, carimbo, carregar_config, carregar_env, dir_execucao, salvar_json
from validacao.dados import Snapshot

GABARITOS = RAIZ_VALIDACAO / "b_benchmark" / "gabaritos.yaml"


def carregar_perguntas() -> list[dict]:
    from benchmark.dataset import carregar_dataset
    return carregar_dataset()["perguntas"]


# ─── gabaritos por SQL sobre o snapshot ──────────────────────────────────────
def calcular_gabaritos(run_id: str, snap) -> dict:
    import pandas as pd
    spec = yaml.safe_load(GABARITOS.read_text(encoding="utf-8"))
    lic = snap.licitacoes.copy()
    lic["dt_abertura"] = pd.to_datetime(lic["dt_abertura"], errors="coerce").dt.date
    lic["ano"] = lic["ano"].astype("float").astype("Int64")
    snap.sql("SELECT 1")
    con = snap._duck
    con.register("lic", lic)
    # Itens pela view oficial vw_itens_agro (CLAUDE.md: fonte única das métricas de item, a
    # mesma que as ferramentas do assistente consultam), com o ano do número do processo.
    con.execute("""CREATE OR REPLACE VIEW itag AS
        SELECT v.* EXCLUDE (dt_abertura), TRY_CAST(v.dt_abertura AS DATE) AS dt_abertura,
               lower(strip_accents(coalesce(v.cultura, ''))) AS cultura_n, lic.ano, lic.chave
        FROM vw_itens_agro v JOIN lic ON lic.id = v.licitacao_id WHERE v.relevante_agro""")
    out = {}
    for q in carregar_perguntas():
        s = spec.get(q["id"])
        if q["conjunto"] == "B":
            out[q["id"]] = {"tipo": "abstencao"}
            continue
        if not s or s.get("tipo") == "sem_gabarito":
            out[q["id"]] = {"tipo": "sem_gabarito"}
            continue
        if "produto" in s:
            prod = s["produto"]
            df = con.execute("""
                WITH p AS (SELECT *, CAST(data_coleta AS DATE) AS d FROM prohort_precos
                           WHERE upper(ceasa) = 'CURITIBA'
                             AND lower(strip_accents(produto_norm)) LIKE '%' || $prod || '%'),
                     u AS (SELECT max(d) AS dmax FROM p)
                SELECT p.preco_min, p.preco_medio, p.preco_max, p.produto_norm, p.d FROM p, u WHERE p.d = u.dmax
                UNION ALL
                SELECT NULL, avg(p.preco_medio), NULL, 'media_30d', max(p.d) FROM p, u WHERE p.d > u.dmax - 30
            """, {"prod": prod}).df()
            vals = sorted({round(float(v), 4) for c in ("preco_min", "preco_medio", "preco_max")
                           for v in df[c].dropna()} - {0.0})
            out[q["id"]] = {"tipo": "numero", "valores": vals, "data_ref": str(df["d"].max()) if len(df) else None,
                            "produtos": sorted(set(df["produto_norm"].dropna()) - {"media_30d"})}
        else:
            df = con.execute(s["consulta"]).df()
            if s["tipo"] == "numero":
                # Zero não entra: qualquer "0" na resposta casaria com ele (falso acerto).
                vals = sorted({round(float(v), 4) for c in df.columns for v in df[c].dropna()} - {0.0})
                out[q["id"]] = {"tipo": "numero", "valores": vals}
            else:
                out[q["id"]] = {"tipo": "entidades", "nomes": list(df["nome"]), "limiar": s.get("limiar", 0.67)}
        out[q["id"]]["consulta"] = s.get("consulta") or f"prohort CURITIBA, produto ~ {s.get('produto')}"
        if out[q["id"]]["tipo"] == "numero" and not out[q["id"]]["valores"]:
            out[q["id"]] = {"tipo": "sem_gabarito", "motivo": "consulta vazia no snapshot"}
    salvar_json(dir_execucao(run_id) / "b" / "gabarito.json", out)
    return out


# ─── chamada ao backend ──────────────────────────────────────────────────────
class Cliente:
    def __init__(self, cfg: dict):
        carregar_env()
        self.url = cfg["fontes"]["agroia_api_url"].rstrip("/")
        self.chave = os.getenv("API_SECRET_KEY") or os.getenv("AGROIA_API_KEY") or ""
        self.cfg = cfg
        self.modo = cfg["b"]["modo_motor"]

    def trocar_motor_global(self, motor: str) -> None:
        r = requests.post(f"{self.url}/config/motor", json={"motor": motor},
                          headers={"X-API-Key": self.chave}, timeout=60)
        r.raise_for_status()

    def motor_ativo(self) -> str | None:
        try:
            return requests.get(f"{self.url}/config/motor", timeout=60).json().get("motor_ativo")
        except Exception:
            return None

    def perguntar(self, pergunta: str, motor: str) -> dict:
        corpo = {"pergunta": pergunta, "historico": [], "session_id": f"validacao-{uuid.uuid4()}",
                 "idioma": "pt", "sem_cache": True, "rastreio": True}
        if self.modo == "requisicao":
            corpo["motor"] = motor
        else:
            self.trocar_motor_global(motor)
        t0 = time.monotonic()
        ttft, texto, tools, fim, erro_http = None, "", [], {}, None
        try:
            with requests.post(f"{self.url}/chat/stream", json=corpo, stream=True,
                               headers={"X-API-Key": self.chave, "Accept": "text/event-stream"},
                               timeout=int(self.cfg["b"]["timeout_s"])) as r:
                if r.status_code != 200:
                    erro_http = r.status_code
                else:
                    for linha in r.iter_lines(decode_unicode=True):
                        if time.monotonic() - t0 > int(self.cfg["b"]["timeout_s"]):
                            erro_http = "TIMEOUT"
                            break
                        if not linha or not linha.startswith("data:"):
                            continue
                        dado = linha[5:].strip()
                        if dado == "[DONE]":
                            break
                        try:
                            ev = json.loads(dado)
                        except Exception:
                            continue
                        if ev.get("tipo") == "token":
                            if ttft is None:
                                ttft = time.monotonic() - t0
                            texto += ev.get("texto", "")
                        elif ev.get("tipo") == "tool":
                            tools.append({"nome": ev.get("nome"), "inputs": ev.get("inputs"),
                                          "resultado": (ev.get("resultado") or "")[:20000]})
                        elif ev.get("tipo") == "fim":
                            fim = ev
        except requests.Timeout:
            erro_http = "TIMEOUT"
        except Exception as e:  # noqa: BLE001
            erro_http = f"EXC {str(e)[:200]}"
        return {"texto": texto, "tools": tools, "fim": fim, "ttft_s": ttft,
                "latencia_s": round(time.monotonic() - t0, 3), "erro_http": erro_http}


def classificar_erro(chamada: dict) -> str | None:
    e = str(chamada.get("erro_http") or "") + " " + str((chamada.get("fim") or {}).get("erro") or "")
    baixo = e.lower()
    if "413" in e:
        return "ERRO_INFRA_413"
    # "rate" sozinho casava com "generateContent" na URL do Gemini: exige termos completos.
    if "429" in e or "rate limit" in baixo or "rate_limit" in baixo or "ratelimit" in baixo or "quota" in baixo:
        return "ERRO_INFRA_429"
    if "404" in e or "not found" in baixo or "model_not_found" in baixo:
        return "ERRO_INFRA_404"        # modelo inexistente/aposentado no provedor
    if "TIMEOUT" in e:
        return "ERRO_INFRA_TIMEOUT"
    if chamada.get("erro_http") or (chamada.get("fim") or {}).get("erro"):
        return "ERRO_INFRA"
    if not chamada.get("fim"):
        return "ERRO_INFRA"
    return None


def executar(run_id: str, cfg: dict | None = None, piloto: bool = False) -> dict:
    cfg = cfg or carregar_config()
    d = dir_execucao(run_id) / "b"
    d.mkdir(parents=True, exist_ok=True)
    snap = Snapshot(run_id)
    gab = calcular_gabaritos(run_id, snap)
    perguntas = carregar_perguntas()
    motores = list(cfg["b"]["motores"])
    reps = int(cfg["b"]["repeticoes"])
    if piloto:
        ids = ("P01", "L04", "G01")
        perguntas = [q for q in perguntas if q["id"] in ids]
        reps = 2
    etapa = "b_piloto" if piloto else "b"
    rng = random.Random(int(cfg["execucao"]["seed"]) + 2)
    plano = [{"q": q, "motor": m, "rep": r} for q in perguntas for r in range(1, reps + 1) for m in motores]
    rng.shuffle(plano)
    por_motor = {m: [u for u in plano if u["motor"] == m] for m in motores}
    plano = []
    while any(por_motor.values()):
        for m in motores:
            if por_motor[m]:
                plano.append(por_motor[m].pop(0))
    chave = lambda u: f"{u['q']['id']}|{u['motor']}|{u['rep']}"  # noqa: E731
    estado.registrar_unidades(run_id, etapa, [chave(u) for u in plano])
    feitas = {u["chave"] for u in estado.unidades(run_id, etapa, "concluida")}

    from validacao.snapshot.congelar import assinatura_rapida
    from validacao.comum import aquecer_backend
    # A instância gratuita do Render dorme sem uso: acordar antes do lote (tempo registrado à parte).
    aquec = aquecer_backend(cfg["fontes"]["agroia_api_url"], int(cfg["a2"].get("aquecimento_timeout_s", 300)))
    estado.evento(run_id, "b", f"aquecimento do backend: {aquec} s")
    cli = Cliente(cfg)
    ctx = {"inicio": carimbo(), "aquecimento_s": aquec,
           "modo_motor": cfg["b"]["modo_motor"], "modo_dados": cfg["b"]["modo_dados"],
           "assinatura_antes": assinatura_rapida(), "motor_global_antes": cli.motor_ativo(),
           "hash_snapshot": json.loads((snap.dir / "snapshot.json").read_text(encoding="utf-8"))["hash_agregado"]}
    ultimo_por_motor: dict[str, float] = {}
    arq = open(d / f"chamadas{'_piloto' if piloto else ''}.jsonl", "a", encoding="utf-8")
    try:
        for pos, u in enumerate(plano, 1):
            k = chave(u)
            if k in feitas:
                continue
            m = u["motor"]
            espera = float(cfg["b"]["intervalo_por_motor_s"].get(m, 1)) - (time.monotonic() - ultimo_por_motor.get(m, 0))
            if espera > 0:
                time.sleep(espera)
            tent, c, erro = 0, None, None
            while True:
                c = cli.perguntar(u["q"]["pergunta"], m)
                ultimo_por_motor[m] = time.monotonic()
                erro = classificar_erro(c)
                if erro == "ERRO_INFRA_429" and tent < int(cfg["b"]["max_backoff_tentativas"]):
                    # Espera o tempo indicado pelo provedor ("try again in 28.9s"), senão backoff exponencial.
                    m = re.search(r"try again in ([\d.]+)\s*s", str((c.get("fim") or {}).get("erro") or ""), re.I)
                    espera = min(90.0, float(m.group(1)) + 2) if m else float(2 ** (tent + 2))
                    estado.evento(run_id, "b", f"{k}: 429, espera {espera:.0f} s", "aviso")
                    time.sleep(espera)
                    tent += 1
                    continue
                break
            if cfg["b"]["modo_motor"] == "requisicao" and c.get("fim") and c["fim"].get("motor") not in (m, None):
                erro = "ERRO_MOTOR_DIVERGENTE"
            if cfg["b"]["modo_motor"] == "requisicao" and c.get("fim") and "motor" not in c["fim"]:
                raise RuntimeError("O backend não devolveu o motor no evento 'fim': faça o deploy da versão com "
                                   "suporte a {motor, sem_cache, rastreio} ou use b.modo_motor = switch_global.")
            reg = {"chave": k, "pergunta_id": u["q"]["id"], "categoria": u["q"]["categoria"],
                   "conjunto": u["q"]["conjunto"], "motor": m, "rep": u["rep"], "quando": carimbo(),
                   "tentativas_429": tent, "erro": erro, **c}
            arq.write(json.dumps(reg, ensure_ascii=False, default=str) + "\n")
            arq.flush()
            estado.marcar(run_id, etapa, k, "concluida", erro or "ok", incrementar=True)
            estado.evento(run_id, "b", f"[{pos}/{len(plano)}] {k}: {erro or 'ok'} ({c['latencia_s']} s)")
    finally:
        arq.close()
        if cfg["b"]["modo_motor"] == "switch_global" and ctx["motor_global_antes"]:
            try:
                cli.trocar_motor_global(ctx["motor_global_antes"])
            except Exception:
                pass
    ctx["assinatura_depois"] = assinatura_rapida()
    ctx["base_inalterada"] = ctx["assinatura_antes"]["hash"] == ctx["assinatura_depois"]["hash"]
    ctx["fim"] = carimbo()
    salvar_json(d / f"contexto{'_piloto' if piloto else ''}.json", ctx)
    from validacao.b_benchmark.analise import analisar
    return analisar(run_id, cfg, piloto=piloto)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--piloto", action="store_true")
    a = ap.parse_args()
    r = executar(a.run_id, piloto=a.piloto)
    print(json.dumps({k: r.get(k) for k in ("n_chamadas", "acuracia_principal")}, ensure_ascii=False, default=str)[:2000])


if __name__ == "__main__":
    main()
