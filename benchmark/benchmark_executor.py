"""Orquestrador CLI do benchmark de motores LLM.

Roda N repetições × motores × perguntas, mede latência/tokens/tools/resposta,
calcula AF@k, custo, consistência e significância, e persiste em metrics/
(CSV por run + JSON de resumo) com espelho opcional no Supabase. Pode exportar
um JSON consolidado para o front (--export-frontend).

Exemplos (PowerShell):
    python -m benchmark.benchmark_executor --motores claude --reps 1 --perguntas L02
    python -m benchmark.benchmark_executor --motores claude,groq_llama,maritaca,gemini --reps 3
    python -m benchmark.benchmark_executor --export-frontend
"""

from __future__ import annotations

import argparse
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from benchmark.dataset import selecionar_perguntas, carregar_dataset
from benchmark.providers.factory import (
    get_provider, ROTULOS, MOTOR_BASELINE, MOTORES_DISPONIVEIS,
)
from benchmark.agentic_loop import rodar_loop
from benchmark import metricas, stats, persistencia, precos_modelos

load_dotenv()

# Motores de janela curta → truncar tool_result (Sabiá-3 ~8k tokens).
_MAX_TOOL_RESULT = {"maritaca": int(__import__("os").getenv("BENCHMARK_MAX_TOOL_RESULT_CHARS", "4000"))}


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rodar_com_retry(provider, pergunta, max_tentativas=3, **kw):
    """Roda o loop com backoff exponencial em caso de erro (rate-limit 429 etc.)."""
    ult = None
    for tentativa in range(1, max_tentativas + 1):
        res = rodar_loop(provider, pergunta, **kw)
        if not res.erro:
            return res
        ult = res
        if tentativa < max_tentativas:
            time.sleep(2 ** tentativa)  # 2s, 4s
    return ult


def executar(motores: list[str], reps: int, seletor: str, out_dir: str,
             sleep_s: float, run_id: str | None = None) -> dict:
    perguntas = selecionar_perguntas(seletor)
    run_id = run_id or str(uuid.uuid4())
    metrics_dir = persistencia.garantir_dir(out_dir)
    csv_path = persistencia.caminho_csv(metrics_dir, run_id)

    print(f"\n{'='*64}\nBENCHMARK run_id={run_id}")
    print(f"motores={motores} reps={reps} perguntas={len(perguntas)} → {csv_path}\n{'='*64}\n")

    persistencia.sync_execucao({
        "run_id": run_id, "dt_inicio": _agora_iso(), "motores": motores,
        "n_repeticoes": reps, "n_perguntas": len(perguntas), "versao_dataset": "1.0",
    })

    rows: list[dict] = []
    for motor in motores:
        try:
            provider = get_provider(motor)
        except Exception as e:  # noqa: BLE001 — chave ausente: pula o motor
            print(f"[pulado] motor {motor}: {e}")
            continue
        max_tr = _MAX_TOOL_RESULT.get(motor)
        for q in perguntas:
            for rep in range(1, reps + 1):
                res = _rodar_com_retry(
                    provider, q["pergunta"],
                    max_tool_result_chars=max_tr,
                )
                af = metricas.nivel_af(res, q)
                row = {
                    "run_id": run_id, "motor": motor, "modelo": provider.modelo,
                    "questao_id": q["id"], "categoria": q["categoria"],
                    "conjunto": q["conjunto"], "repeticao": rep,
                    "dt_execucao": _agora_iso(),
                    "latencia_ms": res.latencia_total_ms, "iteracoes": res.iteracoes,
                    "tokens_entrada": res.tokens_entrada, "tokens_saida": res.tokens_saida,
                    "tokens_estimados": res.tokens_estimados,
                    "custo_usd": precos_modelos.custo_usd(motor, res.tokens_entrada, res.tokens_saida),
                    "tool_esperada": q["tool_esperada"], "tools_usadas": res.tools_usadas,
                    "tool_calls_detalhe": res.tool_calls_detalhe, "af_nivel": af,
                    "af_param_strict": metricas.af_param_strict(res, q),
                    "abstencao_correta": metricas.abstencao_correta(res, q),
                    "resultado_vazio": not bool((res.resposta or "").strip()),
                    "tool_result_truncado": res.tool_result_truncado,
                    "status": "erro" if res.erro else "ok", "erro": res.erro or "",
                    "resposta": (res.resposta or "")[:1000],
                }
                rows.append(row)
                persistencia.append_row(csv_path, row)
                persistencia.sync_resultado(row)
                print(f"  {motor:11s} {q['id']} rep{rep}  AF@{af or '-'}  "
                      f"{res.latencia_total_ms:>6}ms  tools={res.tools_usadas}")
                if sleep_s:
                    time.sleep(sleep_s)

    persistencia.sync_execucao({
        "run_id": run_id, "dt_fim": _agora_iso(), "motores": motores,
        "n_repeticoes": reps, "n_perguntas": len(perguntas), "versao_dataset": "1.0",
    })

    consolidado = consolidar(rows, run_id, reps, len(perguntas))
    resumo_path = metrics_dir / f"benchmark_resumo_{run_id}.json"
    persistencia.escrever_json(resumo_path, consolidado)
    print(f"\nResumo salvo em {resumo_path}")
    return consolidado


# ---------------------------------------------------------------------------
# Consolidação (formato consumido pelo front)
# ---------------------------------------------------------------------------
def consolidar(rows: list[dict], run_id: str, reps: int, n_perguntas: int) -> dict:
    motores = _ordem_motores(rows)
    dataset = {q["id"]: q for q in carregar_dataset()["perguntas"]}

    por_motor = []
    for motor in motores:
        rm = [r for r in rows if r["motor"] == motor]
        if not rm:
            continue
        lat = metricas.percentis([r["latencia_ms"] for r in rm])
        n = len(rm)
        af1 = sum(1 for r in rm if r["af_nivel"] == 1)
        af2 = sum(1 for r in rm if r["af_nivel"] in (1, 2))
        af3 = sum(1 for r in rm if r["af_nivel"] in (1, 2, 3))
        erros = sum(1 for r in rm if r["status"] == "erro")
        custo_med = sum(float(r["custo_usd"] or 0) for r in rm) / n
        por_motor.append({
            "motor": motor, "rotulo": ROTULOS.get(motor, motor),
            "baseline": motor == MOTOR_BASELINE,
            "n": n,
            "latencia_p50_ms": lat["p50_ms"], "latencia_p95_ms": lat["p95_ms"],
            "latencia_media_ms": lat["media_ms"],
            "custo_usd_1k": round(custo_med * 1000, 4),
            "af1_pct": round(100 * af1 / n, 1), "af2_pct": round(100 * af2 / n, 1),
            "af3_pct": round(100 * af3 / n, 1),
            "taxa_erro_pct": round(100 * erros / n, 1),
            "af1_conjunto_A": _af1_conjunto(rm, "A"),
            "af1_conjunto_B": _af1_conjunto(rm, "B"),
            "consistencia": _consistencia_motor(rm),
            "significancia": {},  # preenchido abaixo
        })

    _preencher_significancia(por_motor, rows, motores)

    return {
        "versao": "1.0", "run_id": run_id, "gerado_em": _agora_iso(),
        "n_repeticoes": reps, "n_perguntas": n_perguntas,
        "motores": por_motor,
        "por_categoria": _por_categoria(rows, motores),
        "exemplos_qualitativos": _exemplos(rows, dataset),
    }


def _ordem_motores(rows) -> list[str]:
    vistos = []
    for r in rows:
        if r["motor"] not in vistos:
            vistos.append(r["motor"])
    # baseline primeiro
    return sorted(vistos, key=lambda m: (m != MOTOR_BASELINE, m))


def _af1_conjunto(rm, conjunto) -> float:
    sub = [r for r in rm if r["conjunto"] == conjunto]
    if not sub:
        return 0.0
    return round(100 * sum(1 for r in sub if r["af_nivel"] == 1) / len(sub), 1)


def _consistencia_motor(rm) -> float:
    grupos = defaultdict(list)
    for r in rm:
        grupos[r["questao_id"]].append(r.get("resposta", ""))
    vals = []
    try:
        for respostas in grupos.values():
            if len(respostas) >= 2:
                vals.append(metricas.consistencia(respostas))
    except Exception as e:  # noqa: BLE001 — embeddings indisponíveis: não quebrar
        print(f"[aviso] consistência indisponível: {e}")
        return None
    return round(sum(vals) / len(vals), 4) if vals else None


def _por_categoria(rows, motores) -> list[dict]:
    out = []
    cats = ["preco", "licitacao", "edital", "geral"]
    for motor in motores:
        for cat in cats:
            sub = [r for r in rows if r["motor"] == motor and r["categoria"] == cat]
            if not sub:
                continue
            lat = metricas.percentis([r["latencia_ms"] for r in sub])
            af1 = sum(1 for r in sub if r["af_nivel"] == 1)
            out.append({
                "motor": motor, "categoria": cat,
                "af1_pct": round(100 * af1 / len(sub), 1),
                "latencia_p50_ms": lat["p50_ms"],
            })
    return out


def _exemplos(rows, dataset, max_q=6) -> list[dict]:
    """Seleciona perguntas onde os motores DIVERGEM (analiticamente mais ricas)."""
    por_q = defaultdict(list)
    for r in rows:
        por_q[r["questao_id"]].append(r)
    # ordena por divergência de AF entre motores
    def divergencia(qid):
        afs = {r["motor"]: r["af_nivel"] for r in por_q[qid]}
        return len(set(afs.values()))
    qids = sorted(por_q, key=divergencia, reverse=True)[:max_q]
    exemplos = []
    for qid in qids:
        q = dataset.get(qid, {})
        for r in por_q[qid]:
            if r["repeticao"] != 1:
                continue
            detalhe = r.get("tool_calls_detalhe") or []
            primeira = detalhe[0] if detalhe else {}
            exemplos.append({
                "questao_id": qid, "pergunta": q.get("pergunta", ""),
                "motor": r["motor"], "rotulo": ROTULOS.get(r["motor"], r["motor"]),
                "tool_chamada": primeira.get("nome"),
                "parametros": primeira.get("inputs", {}),
                "classificacao": _classificar(r, q),
                "trecho": (r.get("resposta") or "")[:240],
            })
    return exemplos


def _classificar(r, q) -> str:
    if r["status"] == "erro":
        return "INCORRETO"
    if q.get("tool_esperada") is None:
        return "RECUSA" if not r["tools_usadas"] else "PARCIAL"
    if r["af_nivel"] == 1:
        return "CORRETO"
    if r["af_param_strict"]:
        return "PARCIAL"
    return "INCORRETO"


def _preencher_significancia(por_motor, rows, motores):
    """t-test pareado + Bonferroni, pairwise entre motores, p/ latência e AF@1."""
    idx = {m: i for i, m in enumerate(motores)}
    # vetores por motor, chaveados por (questao,rep)
    def vetor(motor, chave):
        d = {}
        for r in rows:
            if r["motor"] == motor:
                d[(r["questao_id"], r["repeticao"])] = (
                    r["latencia_ms"] if chave == "lat" else (1.0 if r["af_nivel"] == 1 else 0.0)
                )
        return d

    for metric, melhor in (("lat", "menor"), ("af", "maior")):
        # coleta p-values pairwise
        for a in motores:
            sup = ""
            va = vetor(a, metric)
            for b in motores:
                if a == b:
                    continue
                vb = vetor(b, metric)
                comuns = sorted(set(va) & set(vb))
                if len(comuns) < 2:
                    continue
                xa = [va[k] for k in comuns]
                xb = [vb[k] for k in comuns]
                try:
                    teste = stats.comparar_pareado(xa, xb)
                except Exception:  # noqa: BLE001
                    continue
                corr = stats.bonferroni({"x": teste["p_value"]},
                                        n_testes=len(motores) * (len(motores) - 1))["x"]
                if not corr["significativo"]:
                    continue
                media_a = sum(xa) / len(xa)
                media_b = sum(xb) / len(xb)
                melhor_que_b = (media_a < media_b) if melhor == "menor" else (media_a > media_b)
                if melhor_que_b:
                    sup += stats.SUPERESCRITOS.get(idx[b], "")
            # grava no por_motor
            for pm in por_motor:
                if pm["motor"] == a:
                    pm["significancia"]["latencia" if metric == "lat" else "af1"] = sup


# ---------------------------------------------------------------------------
# Export p/ front a partir do resumo mais recente
# ---------------------------------------------------------------------------
def exportar_frontend_de_metrics(out_dir: str) -> Path | None:
    resumos = sorted(Path(out_dir).glob("benchmark_resumo_*.json"))
    if not resumos:
        print("[export] Nenhum benchmark_resumo_*.json em metrics/. Rode o benchmark primeiro.")
        return None
    import json
    consolidado = json.loads(resumos[-1].read_text(encoding="utf-8"))
    destino = persistencia.export_frontend(consolidado)
    print(f"[export] {resumos[-1].name} → {destino}")
    return destino


def main():
    ap = argparse.ArgumentParser(description="Benchmark de motores LLM (AgroIA-RMC)")
    ap.add_argument("--motores", default="claude",
                    help=f"CSV de motores ({', '.join(MOTORES_DISPONIVEIS)}) ou 'all'")
    ap.add_argument("--reps", type=int, default=1, help="repetições por pergunta")
    ap.add_argument("--perguntas", default="all",
                    help="all | A | B | preco|licitacao|edital|geral | P01,L02,...")
    ap.add_argument("--out", default="metrics", help="diretório de saída")
    ap.add_argument("--sleep", type=float, default=1.0, help="segundos entre runs (rate-limit)")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--export-frontend", action="store_true",
                    help="apenas consolida o resumo mais recente p/ o front e sai")
    args = ap.parse_args()

    if args.export_frontend:
        exportar_frontend_de_metrics(args.out)
        return

    motores = list(MOTORES_DISPONIVEIS) if args.motores == "all" else [
        m.strip() for m in args.motores.split(",") if m.strip()
    ]
    consolidado = executar(motores, args.reps, args.perguntas, args.out, args.sleep, args.run_id)
    # exporta automaticamente ao final
    persistencia.export_frontend(consolidado)
    print("[export] resultados.json atualizado para o front.")


if __name__ == "__main__":
    main()
