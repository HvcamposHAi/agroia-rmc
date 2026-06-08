"""Router isolado: switch global de motor + comparador de motores ao vivo.

Incluído em api/main.py com duas linhas (import + include_router). Não altera
nenhum endpoint existente. Reusa benchmark.agentic_loop + providers REST.
verify_api_key é replicado localmente (mesma API_SECRET_KEY) para evitar import
circular com api.main.
"""

from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from chat.motor_router import MOTORES, MOTOR_PADRAO, get_motor_ativo, set_motor_ativo
from benchmark.providers.factory import ROTULOS
from benchmark.providers.rest_providers import get_live_provider
from benchmark.agentic_loop import rodar_loop
from benchmark.precos_modelos import custo_usd

router = APIRouter(tags=["benchmark"])

_API_SECRET_KEY = os.getenv("API_SECRET_KEY")
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Mapa motor -> env da chave (para checar disponibilidade sem instanciar).
ENV_POR_MOTOR = {
    "claude": "ANTHROPIC_API_KEY",
    "groq_llama": "GROQ_API_KEY",
    "maritaca": "MARITACA_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


def _verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    if not api_key or api_key != _API_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key


class MotorRequest(BaseModel):
    motor: str


class CompararRequest(BaseModel):
    pergunta: str
    motores: list[str] = []


def _lista_motores() -> list[dict]:
    return [{
        "motor": m,
        "rotulo": ROTULOS.get(m, m),
        "disponivel": bool(os.getenv(ENV_POR_MOTOR.get(m, ""))),
        "baseline": m == MOTOR_PADRAO,
    } for m in MOTORES]


@router.get("/config/motor")
def get_config_motor():
    """Motor ativo global + lista de motores com disponibilidade (leitura pública)."""
    return {"motor_ativo": get_motor_ativo(), "motores": _lista_motores()}


@router.post("/config/motor")
def post_config_motor(req: MotorRequest, _: str = Depends(_verify_api_key)):
    """Troca o motor ativo global de TODOS os agentes."""
    if req.motor not in MOTORES:
        raise HTTPException(status_code=400, detail=f"Motor inválido. Use um de {list(MOTORES)}.")
    try:
        salvo = set_motor_ativo(req.motor)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Falha ao salvar motor: {e}")
    return {"motor_ativo": salvo, "motores": _lista_motores()}


@router.get("/benchmark/motores")
def get_benchmark_motores():
    return _lista_motores()


@router.post("/benchmark/comparar/stream")
def comparar_stream(req: CompararRequest, _: str = Depends(_verify_api_key)):
    """Roda a mesma pergunta por motor (sequencial) e transmite cada resultado (SSE)."""
    motores = [m for m in req.motores if m in MOTORES] or [MOTOR_PADRAO]

    def generate():
        yield f"data: {json.dumps({'tipo': 'inicio', 'motores': motores, 'pergunta': req.pergunta}, ensure_ascii=False)}\n\n"
        for motor in motores:
            try:
                provider = get_live_provider(motor)
                res = rodar_loop(provider, req.pergunta)
                ev = {
                    "tipo": "motor", "motor": motor, "rotulo": ROTULOS.get(motor, motor),
                    "resposta": res.resposta, "latencia_ms": res.latencia_total_ms,
                    "tokens_entrada": res.tokens_entrada, "tokens_saida": res.tokens_saida,
                    "custo_usd": custo_usd(motor, res.tokens_entrada, res.tokens_saida),
                    "tools_usadas": res.tools_usadas, "iteracoes": res.iteracoes,
                    "erro": res.erro,
                }
            except Exception as e:  # noqa: BLE001 — falha de um motor não derruba os outros
                ev = {
                    "tipo": "motor", "motor": motor, "rotulo": ROTULOS.get(motor, motor),
                    "resposta": "", "latencia_ms": 0, "tokens_entrada": 0, "tokens_saida": 0,
                    "custo_usd": 0.0, "tools_usadas": [], "iteracoes": 0, "erro": str(e),
                }
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
