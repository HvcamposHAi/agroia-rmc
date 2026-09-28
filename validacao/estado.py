"""Estado persistente das execuções (SQLite local): checkpoint, retomada e eventos.

Cada unidade de trabalho (processo da A1, execução da A2, chamada da B) tem uma
linha em `unidades` com status pendente | executando | concluida | falhou.
Rodar de novo com --retomar só executa o que não está concluída.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from validacao.comum import RAIZ_VALIDACAO, agora_utc

ARQUIVO = RAIZ_VALIDACAO / "estado.db"
_lock = threading.Lock()

_DDL = """
CREATE TABLE IF NOT EXISTS execucoes (
    run_id TEXT PRIMARY KEY, criado_em TEXT, atualizado_em TEXT,
    etapas TEXT, opcoes TEXT, status TEXT, etapas_concluidas TEXT DEFAULT '[]', pid INTEGER
);
CREATE TABLE IF NOT EXISTS unidades (
    run_id TEXT, etapa TEXT, chave TEXT, status TEXT, tentativas INTEGER DEFAULT 0,
    mensagem TEXT, dados TEXT, atualizado_em TEXT,
    PRIMARY KEY (run_id, etapa, chave)
);
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, ts TEXT, etapa TEXT,
    nivel TEXT, mensagem TEXT
);
CREATE INDEX IF NOT EXISTS idx_eventos_run ON eventos(run_id, id);
"""


@contextmanager
def _con(arquivo: Path | None = None):
    with _lock:
        con = sqlite3.connect(arquivo or ARQUIVO, timeout=30)
        con.row_factory = sqlite3.Row
        try:
            con.executescript(_DDL)
            yield con
            con.commit()
        finally:
            con.close()


def _agora() -> str:
    return agora_utc().isoformat()


# ─── Execuções ───────────────────────────────────────────────────────────────
def criar_execucao(run_id: str, etapas: list[str], opcoes: dict, pid: int | None = None) -> None:
    with _con() as c:
        c.execute("""INSERT INTO execucoes(run_id, criado_em, atualizado_em, etapas, opcoes, status, pid)
                     VALUES (?,?,?,?,?,?,?)
                     ON CONFLICT(run_id) DO UPDATE SET atualizado_em=excluded.atualizado_em,
                       etapas=excluded.etapas, opcoes=excluded.opcoes, status=excluded.status,
                       pid=excluded.pid""",
                  (run_id, _agora(), _agora(), json.dumps(etapas), json.dumps(opcoes, default=str),
                   "executando", pid))


def status_execucao(run_id: str, status: str) -> None:
    with _con() as c:
        c.execute("UPDATE execucoes SET status=?, atualizado_em=? WHERE run_id=?", (status, _agora(), run_id))


def etapa_concluida(run_id: str, etapa: str) -> None:
    with _con() as c:
        r = c.execute("SELECT etapas_concluidas FROM execucoes WHERE run_id=?", (run_id,)).fetchone()
        feitas = json.loads(r["etapas_concluidas"]) if r and r["etapas_concluidas"] else []
        if etapa not in feitas:
            feitas.append(etapa)
        c.execute("UPDATE execucoes SET etapas_concluidas=?, atualizado_em=? WHERE run_id=?",
                  (json.dumps(feitas), _agora(), run_id))


def listar_execucoes() -> list[dict]:
    with _con() as c:
        rows = c.execute("SELECT * FROM execucoes ORDER BY criado_em DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("etapas", "opcoes", "etapas_concluidas"):
            try:
                d[k] = json.loads(d[k]) if d[k] else []
            except Exception:
                pass
        out.append(d)
    return out


def obter_execucao(run_id: str) -> dict | None:
    return next((e for e in listar_execucoes() if e["run_id"] == run_id), None)


# ─── Unidades de trabalho ────────────────────────────────────────────────────
def registrar_unidades(run_id: str, etapa: str, chaves: list[str]) -> None:
    with _con() as c:
        c.executemany("""INSERT OR IGNORE INTO unidades(run_id, etapa, chave, status, atualizado_em)
                         VALUES (?,?,?, 'pendente', ?)""",
                      [(run_id, etapa, k, _agora()) for k in chaves])


def marcar(run_id: str, etapa: str, chave: str, status: str, mensagem: str = "",
           dados: dict | None = None, incrementar: bool = False) -> None:
    with _con() as c:
        c.execute("""INSERT INTO unidades(run_id, etapa, chave, status, tentativas, mensagem, dados, atualizado_em)
                     VALUES (?,?,?,?,?,?,?,?)
                     ON CONFLICT(run_id, etapa, chave) DO UPDATE SET status=excluded.status,
                       tentativas=unidades.tentativas + ?, mensagem=excluded.mensagem,
                       dados=COALESCE(excluded.dados, unidades.dados), atualizado_em=excluded.atualizado_em""",
                  (run_id, etapa, chave, status, 1 if incrementar else 0, mensagem[:2000],
                   json.dumps(dados, default=str, ensure_ascii=False) if dados is not None else None,
                   _agora(), 1 if incrementar else 0))


def unidades(run_id: str, etapa: str, status: str | None = None) -> list[dict]:
    with _con() as c:
        q = "SELECT * FROM unidades WHERE run_id=? AND etapa=?"
        args = [run_id, etapa]
        if status:
            q += " AND status=?"
            args.append(status)
        rows = c.execute(q + " ORDER BY rowid", args).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["dados"] = json.loads(d["dados"]) if d.get("dados") else None
        out.append(d)
    return out


def pendentes(run_id: str, etapa: str) -> list[str]:
    return [u["chave"] for u in unidades(run_id, etapa) if u["status"] != "concluida"]


def progresso(run_id: str) -> dict:
    with _con() as c:
        rows = c.execute("""SELECT etapa, status, COUNT(*) n FROM unidades WHERE run_id=?
                            GROUP BY etapa, status""", (run_id,)).fetchall()
    out: dict = {}
    for r in rows:
        e = out.setdefault(r["etapa"], {"total": 0})
        e[r["status"]] = r["n"]
        e["total"] += r["n"]
    return out


# ─── Eventos (log de progresso, lido pela página de coordenação via SSE) ────
def evento(run_id: str, etapa: str, mensagem: str, nivel: str = "info") -> None:
    ts = _agora()
    print(f"[{ts[11:19]}] [{etapa}] {mensagem}", flush=True)
    try:
        with _con() as c:
            c.execute("INSERT INTO eventos(run_id, ts, etapa, nivel, mensagem) VALUES (?,?,?,?,?)",
                      (run_id, ts, etapa, nivel, mensagem[:2000]))
    except Exception:
        pass


def eventos_desde(run_id: str, apos_id: int = 0, limite: int = 200) -> list[dict]:
    with _con() as c:
        rows = c.execute("SELECT * FROM eventos WHERE run_id=? AND id>? ORDER BY id LIMIT ?",
                         (run_id, apos_id, limite)).fetchall()
    return [dict(r) for r in rows]


def ultimos_eventos(run_id: str, n: int = 50) -> list[dict]:
    with _con() as c:
        rows = c.execute("SELECT * FROM eventos WHERE run_id=? ORDER BY id DESC LIMIT ?",
                         (run_id, n)).fetchall()
    return [dict(r) for r in reversed(rows)]
