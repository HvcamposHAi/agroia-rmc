"""Fonte única do motor LLM ativo (switch global).

Lê/escreve a linha singleton de `app_config.motor_ativo` no Supabase, com cache
curto em memória. Degrada SEMPRE para "claude" em qualquer erro, garantindo que
falha de leitura nunca desvie do caminho de produção atual.

`resolver_provider` devolve None para "claude" (sinal: use o código existente em
chat/agent.py) ou um provider REST para os demais motores.
"""

from __future__ import annotations

import time

MOTORES = ("claude", "groq_llama", "maritaca", "gemini")
MOTOR_PADRAO = "claude"
_TTL_CACHE_S = 20.0

_cache_motor: str | None = None
_cache_ts: float = 0.0


def get_motor_ativo() -> str:
    """Retorna o motor ativo (cacheado ~20s). Default 'claude' em qualquer erro."""
    global _cache_motor, _cache_ts
    agora = time.time()
    if _cache_motor is not None and (agora - _cache_ts) < _TTL_CACHE_S:
        return _cache_motor
    motor = MOTOR_PADRAO
    try:
        from chat.db import get_supabase_client
        resp = (get_supabase_client().table("app_config")
                .select("motor_ativo").eq("id", 1).limit(1).execute())
        if resp.data:
            valor = (resp.data[0].get("motor_ativo") or "").strip().lower()
            if valor in MOTORES:
                motor = valor
    except Exception:
        motor = MOTOR_PADRAO  # degrada seguro p/ produção
    _cache_motor = motor
    _cache_ts = agora
    return motor


def set_motor_ativo(motor: str) -> str:
    """Persiste o motor ativo (upsert id=1) e invalida o cache. Retorna o motor salvo."""
    global _cache_motor, _cache_ts
    motor = (motor or "").strip().lower()
    if motor not in MOTORES:
        raise ValueError(f"Motor inválido: {motor!r}. Use um de {MOTORES}.")
    from chat.db import get_supabase_client
    get_supabase_client().table("app_config").upsert(
        {"id": 1, "motor_ativo": motor}, on_conflict="id"
    ).execute()
    _cache_motor = motor
    _cache_ts = time.time()
    return motor


def resolver_provider(motor: str | None = None):
    """None se o motor (ou o ativo) for 'claude'; senão um provider REST ao vivo."""
    motor = (motor or get_motor_ativo() or MOTOR_PADRAO).strip().lower()
    if motor == "claude":
        return None
    from benchmark.providers.rest_providers import get_live_provider
    return get_live_provider(motor)


def completar_texto_motor(prompt: str, system: str = "", max_tokens: int = 2048) -> str | None:
    """Completa um prompt único (sem tools) pelo motor ativo.

    Retorna o texto, ou None quando o motor ativo é 'claude' OU quando o provider
    falha — sinalizando ao chamador para usar o caminho Claude (fallback). Usado
    pelos analisadores de saída estruturada (alertas/auditoria).
    """
    try:
        provider = resolver_provider()
        if provider is None:
            return None
        res = provider.gerar(system_prompt=system, tools_schema=[],
                             messages=[{"role": "user", "content": prompt}],
                             max_tokens=max_tokens)
        if res.stop_reason == "erro" or not (res.texto or "").strip():
            return None
        return res.texto
    except Exception:
        return None
