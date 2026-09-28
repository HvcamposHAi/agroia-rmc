"""Execução do Claude Code com Claude in Chrome por subprocesso (A1 extrator Chrome e A2).

Nada aqui espera por humano: todo subprocesso tem timeout; falha de conexão com a
extensão é classificada (ERRO_INFRA_CHROME) e a execução segue.

Adaptações em relação ao comando do plano (seção 4.4.1), verificadas no `claude --help`
da versão instalada e registradas em docs/API.md:
  - `--permission-mode dontAsk` + `--allowedTools mcp__claude-in-chrome__*`: nega qualquer
    ferramenta fora do servidor do Chrome (bypassPermissions liberaria todas);
  - sem `--tools` e com ENABLE_TOOL_SEARCH=false: com `--tools ""` o servidor do Chrome
    não é carregado, e com a busca sob demanda a 1ª busca ocorre antes da conexão com a
    extensão; as ferramentas internas ficam em `--disallowedTools`;
  - `--no-session-persistence`: nenhuma sessão fica gravada entre tarefas.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from validacao.comum import carimbo, salvar_json

PREFIXO_CHROME = "mcp__claude-in-chrome__"


def _exe() -> str:
    return shutil.which("claude") or shutil.which("claude.cmd") or "claude"


def montar_comando(prompt: str, cfg: dict, modelo: str | None = None, max_turns: int | None = None) -> list[str]:
    a2 = cfg["a2"]
    # O prompt vai pela entrada padrão (ver executar): no Windows o `claude` é um .cmd e o
    # cmd.exe corta argumentos na primeira quebra de linha, descartando as flags seguintes.
    cmd = [_exe(), "-p", "--chrome",
           "--output-format", "stream-json", "--verbose",
           "--no-session-persistence",
           "--permission-mode", a2.get("permission_mode", "dontAsk")]
    if a2.get("tools_internas"):
        cmd += ["--tools", a2["tools_internas"]]
    if modelo or a2.get("modelo_agente"):
        cmd += ["--model", modelo or a2["modelo_agente"]]
    if max_turns or a2.get("max_turns"):
        cmd += ["--max-turns", str(max_turns or a2["max_turns"])]
    if a2.get("allowed_tools"):
        cmd += ["--allowedTools", ",".join(a2["allowed_tools"])]
    if a2.get("disallowed_tools"):
        cmd += ["--disallowedTools", ",".join(a2["disallowed_tools"])]
    return cmd


def executar(prompt: str, cfg: dict, cwd: Path, saida_jsonl: Path, timeout_s: int,
             modelo: str | None = None, max_turns: int | None = None) -> dict:
    """Roda o agente. Devolve {status, rc, duracao_s, inicio, fim, comando}.

    status: OK | TIMEOUT | ERRO_INFRA (processo não iniciou ou saiu sem resultado) |
            ERRO_INFRA_CHROME (extensão não conectou e o navegador não foi usado)."""
    cwd.mkdir(parents=True, exist_ok=True)
    saida_jsonl.parent.mkdir(parents=True, exist_ok=True)
    cmd = montar_comando(prompt, cfg, modelo, max_turns)
    inicio = carimbo()
    t0 = time.monotonic()
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    # Ferramentas do Chrome carregadas desde o início (ver docstring do módulo).
    env["ENABLE_TOOL_SEARCH"] = "false"
    # Espera a conexão MCP antes do 1º turno: sem isto o servidor do Chrome não estava conectado
    # na inicialização em 4 de 4 testes (27/09/2026); com isto, em 4 de 4.
    env["MCP_CONNECTION_NONBLOCKING"] = "false"
    env.setdefault("MCP_TIMEOUT", "30000")
    status, rc = "OK", None
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    arq_prompt = saida_jsonl.with_suffix(".prompt.txt")
    arq_prompt.write_text(prompt, encoding="utf-8")
    try:
        with open(saida_jsonl, "w", encoding="utf-8") as out, open(saida_jsonl.with_suffix(".err"), "w",
                                                                      encoding="utf-8") as err,                 open(arq_prompt, "rb") as entrada:
            proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=out, stderr=err, stdin=entrada,
                                    env=env, creationflags=flags, start_new_session=(os.name != "nt"))
            try:
                rc = proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                status = "TIMEOUT"
                _matar(proc)
    except FileNotFoundError as e:
        status = "ERRO_INFRA"
        saida_jsonl.with_suffix(".err").write_text(str(e), encoding="utf-8")
    dur = time.monotonic() - t0
    if status == "OK" and not _tem_resultado(saida_jsonl):
        status = "ERRO_INFRA"
    if status == "OK" and not any(e.get("type") == "system" for e in ler_eventos(saida_jsonl)):
        status = "ERRO_INFRA"          # saída fora do formato stream-json: flags não aplicadas
    if status == "OK":
        ev = ler_eventos(saida_jsonl)
        # A conexão com a extensão é assíncrona: se o agente terminou sem usar o navegador e
        # o servidor não estava conectado na inicialização, a execução não mediu nada.
        if not usou_chrome(ev) and not chrome_conectado_no_inicio(ev):
            status = "ERRO_INFRA_CHROME"
    meta = {"status": status, "rc": rc, "duracao_s": round(dur, 2), "inicio": inicio, "fim": carimbo(),
            "comando": cmd, "prompt_arquivo": arq_prompt.name}
    salvar_json(saida_jsonl.with_suffix(".meta.json"), meta)
    return meta


def _matar(proc):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _tem_resultado(p: Path) -> bool:
    try:
        for linha in p.read_text(encoding="utf-8").splitlines():
            if '"type":"result"' in linha.replace(" ", ""):
                return True
    except Exception:
        pass
    return False


def ler_eventos(p: Path) -> list[dict]:
    out = []
    if not p.exists():
        return out
    for linha in p.read_text(encoding="utf-8", errors="replace").splitlines():
        linha = linha.strip()
        if not linha.startswith("{"):
            continue
        try:
            out.append(json.loads(linha))
        except Exception:
            continue
    return out


def resultado_final(eventos: list[dict]) -> dict | None:
    return next((e for e in reversed(eventos) if e.get("type") == "result"), None)


def chrome_conectado_no_inicio(eventos: list[dict]) -> bool:
    ini = next((e for e in eventos if e.get("type") == "system" and e.get("subtype") == "init"), {})
    return any(m.get("name") == "claude-in-chrome" and m.get("status") == "connected"
               for m in ini.get("mcp_servers") or [])


def usou_chrome(eventos: list[dict]) -> bool:
    for e in eventos:
        if e.get("type") == "assistant":
            for c in e.get("message", {}).get("content", []):
                if c.get("type") == "tool_use" and c.get("name", "").startswith(PREFIXO_CHROME):
                    return True
    return False


# ─── Sonda e recuperação da conexão com a extensão (seção 2.1) ──────────────
PROMPT_SONDA = ("Use a ferramenta tabs_context_mcp do navegador com createIfEmpty true e depois "
                "responda somente OK. Não faça mais nada.")


def sonda(cfg: dict, dir_trabalho: Path, timeout_s: int = 90) -> dict:
    saida = dir_trabalho / f"sonda_{int(time.time())}.jsonl"
    meta = executar(PROMPT_SONDA, cfg, dir_trabalho, saida, timeout_s, max_turns=8)
    ev = ler_eventos(saida)
    ok = meta["status"] == "OK" and usou_chrome(ev) and _sem_erro_ferramenta(ev)
    return {"ok": ok, "status": meta["status"], "duracao_s": meta["duracao_s"], "arquivo": str(saida)}


def _sem_erro_ferramenta(eventos: list[dict]) -> bool:
    for e in eventos:
        if e.get("type") == "user":
            for c in e.get("message", {}).get("content", []) or []:
                if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error"):
                    txt = json.dumps(c.get("content"), ensure_ascii=False).lower()
                    if "not connected" in txt or "extension" in txt:
                        return False
    return True


def reabrir_chrome(cfg: dict) -> None:
    """Encerra o Chrome e reabre com o perfil dedicado (Windows)."""
    perfil = cfg["a2"].get("chrome_perfil", "agroia-validacao")
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True, timeout=60)
        time.sleep(3)
        for base in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""),
                     os.environ.get("LOCALAPPDATA", "")):
            exe = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if exe.exists():
                subprocess.Popen([str(exe), f"--profile-directory={perfil}"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                break
    else:
        subprocess.run(["pkill", "-f", "chrome"], capture_output=True, timeout=60)
        subprocess.Popen(["google-chrome", f"--profile-directory={perfil}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(20)


def garantir_conexao(cfg: dict, dir_trabalho: Path, registrar=None, tentativas: int = 3) -> bool:
    """Sonda; se falhar, reabre o Chrome e tenta de novo (até `tentativas`)."""
    for n in range(1, tentativas + 1):
        r = sonda(cfg, dir_trabalho)
        if registrar:
            registrar(f"sonda Chrome {n}/{tentativas}: {'ok' if r['ok'] else r['status']} ({r['duracao_s']} s)")
        if r["ok"]:
            return True
        if n < tentativas:
            reabrir_chrome(cfg)
    return False
