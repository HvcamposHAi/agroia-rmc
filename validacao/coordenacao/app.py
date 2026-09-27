"""Página de coordenação local da validação (seção 7). Só coordena: a execução autônoma
não depende dela.

  python -m validacao.coordenacao.app [--porta 8765]   → http://127.0.0.1:8765
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from validacao import estado
from validacao.comum import EXECUCOES, RAIZ_REPO, RAIZ_VALIDACAO, novo_run_id

app = FastAPI(title="AgroIA-RMC: coordenação da validação")
STATIC = Path(__file__).with_name("static")
ETAPAS = ["snapshot", "a1", "a2", "b", "relatorios"]


class Pedido(BaseModel):
    etapas: list[str]
    opcoes: dict = {}


def _disparar(args: list[str]) -> None:
    log = EXECUCOES / "_coordenacao.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    with open(log, "a", encoding="utf-8") as f:
        subprocess.Popen([sys.executable, "-m", "validacao.run_all", *args], cwd=str(RAIZ_REPO), stdout=f,
                         stderr=subprocess.STDOUT, creationflags=flags, start_new_session=sys.platform != "win32")


@app.get("/", response_class=HTMLResponse)
def pagina():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/saude")
def saude():
    from validacao.saude.checagens import rodar
    return rodar()


@app.post("/api/executar")
def executar(p: Pedido):
    etapas = [e for e in p.etapas if e in ETAPAS]
    if not etapas:
        raise HTTPException(400, "nenhuma etapa válida")
    run_id = novo_run_id()
    args = ["--run-id", run_id, "--etapas", ",".join(etapas)]
    o = p.opcoes or {}
    if o.get("reusar"):
        args += ["--reusar", str(o["reusar"])]
    for chave, flag in (("a2_instancias", "--a2-instancias"), ("b_reps", "--b-reps"), ("a1_limite", "--a1-limite")):
        if o.get(chave):
            args += [flag, str(int(o[chave]))]
    for chave, flag in (("a2_piloto", "--a2-piloto"), ("b_piloto", "--b-piloto"), ("sem_chrome", "--sem-chrome")):
        if o.get(chave):
            args.append(flag)
    _disparar(args)
    return {"run_id": run_id}


@app.post("/api/retomar/{run_id}")
def retomar(run_id: str):
    if not estado.obter_execucao(run_id):
        raise HTTPException(404, "execução desconhecida")
    _disparar(["--retomar", run_id])
    return {"run_id": run_id}


@app.post("/api/auditoria/{run_id}")
def auditoria(run_id: str):
    subprocess.Popen([sys.executable, "-m", "validacao.b_benchmark.analise", "--run-id", run_id, "--auditoria"],
                     cwd=str(RAIZ_REPO))
    return {"ok": True}


@app.get("/api/execucoes")
def execucoes():
    out = []
    for e in estado.listar_execucoes():
        d = EXECUCOES / e["run_id"]
        rel = sorted(p.name for p in (d / "relatorios").glob("*.html")) if (d / "relatorios").exists() else []
        aud = [p.name for p in (d / "b").glob("auditoria*.csv")] if (d / "b").exists() else []
        out.append({**e, "relatorios": rel, "auditoria": aud, "progresso": estado.progresso(e["run_id"])})
    return out


@app.get("/api/eventos/{run_id}")
async def eventos(run_id: str):
    async def gerar():
        ultimo = 0
        for ev in estado.ultimos_eventos(run_id, 50):
            ultimo = ev["id"]
            yield f"data: {json.dumps({'tipo': 'evento', **ev}, ensure_ascii=False)}\n\n"
        while True:
            novos = estado.eventos_desde(run_id, ultimo)
            for ev in novos:
                ultimo = ev["id"]
                yield f"data: {json.dumps({'tipo': 'evento', **ev}, ensure_ascii=False)}\n\n"
            ex = estado.obter_execucao(run_id) or {}
            yield f"data: {json.dumps({'tipo': 'progresso', 'progresso': estado.progresso(run_id), 'status': ex.get('status'), 'etapas_concluidas': ex.get('etapas_concluidas')}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(gerar(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/relatorios/{run_id}/{caminho:path}")
def arquivo(run_id: str, caminho: str):
    base = (EXECUCOES / run_id).resolve()
    alvo = (base / ("relatorios/" + caminho if caminho.endswith(".html") and "/" not in caminho else caminho)).resolve()
    if base not in alvo.parents or not alvo.is_file():
        raise HTTPException(404, "arquivo não encontrado")
    return FileResponse(alvo)


def main():
    import argparse
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=8765)
    uvicorn.run(app, host="127.0.0.1", port=ap.parse_args().porta)


if __name__ == "__main__":
    main()
