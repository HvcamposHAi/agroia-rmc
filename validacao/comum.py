"""Utilidades compartilhadas da validação autônoma.

Regra 0.3.3 do plano: nada aqui importa `coleta_transparencia.py` nem módulos de
coleta. Normalização, comparação e acesso HTTP são implementados do zero.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

RAIZ_VALIDACAO = Path(__file__).resolve().parent
RAIZ_REPO = RAIZ_VALIDACAO.parent
EXECUCOES = RAIZ_VALIDACAO / "execucoes"
CONFIG_PADRAO = RAIZ_VALIDACAO / "config.yaml"


# ─── Configuração e ambiente ─────────────────────────────────────────────────
def carregar_config(caminho: str | Path | None = None) -> dict:
    p = Path(caminho) if caminho else CONFIG_PADRAO
    cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
    carregar_env()
    # Item 2.7 do plano: AGROIA_API_URL no ambiente sobrepõe a URL do backend (ex.: backend local).
    if os.getenv("AGROIA_API_URL"):
        cfg["fontes"]["agroia_api_url"] = os.environ["AGROIA_API_URL"].rstrip("/")
    return cfg


def carregar_env() -> None:
    """validacao/.env tem precedência; a raiz do repositório é o fallback."""
    from dotenv import load_dotenv
    for p in (RAIZ_VALIDACAO / ".env", RAIZ_REPO / ".env"):
        if p.exists():
            load_dotenv(p, override=False)


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def carimbo(dt: datetime | None = None, fuso: str = "America/Sao_Paulo") -> dict:
    dt = dt or agora_utc()
    return {"utc": dt.isoformat(), "brt": dt.astimezone(ZoneInfo(fuso)).isoformat()}


def novo_run_id() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y%m%d-%H%M%S")


def dir_execucao(run_id: str) -> Path:
    d = EXECUCOES / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def git_info() -> dict:
    def _git(*args):
        try:
            return subprocess.run(["git", *args], cwd=RAIZ_REPO, capture_output=True,
                                  text=True, timeout=20).stdout.strip()
        except Exception:
            return ""
    porcelain = _git("status", "--porcelain")
    return {"commit": _git("rev-parse", "HEAD"), "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "arvore_limpa": porcelain == "", "alteracoes": porcelain.splitlines()[:50]}


def versoes() -> dict:
    import importlib
    libs = {}
    for m in ("pandas", "pyarrow", "scipy", "statsmodels", "jinja2", "matplotlib",
              "playwright", "duckdb", "requests", "bs4", "pypdf", "fitz", "supabase"):
        try:
            mod = importlib.import_module(m)
            libs[m] = getattr(mod, "__version__", None) or getattr(mod, "VersionBind", None) or "ok"
        except Exception:
            libs[m] = None
    try:
        from importlib.metadata import version
        libs["playwright"] = version("playwright")
    except Exception:
        pass
    return {"python": sys.version.split()[0], "plataforma": sys.platform, "bibliotecas": libs,
            "claude_code": versao_claude()}


def versao_claude() -> str | None:
    try:
        r = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30,
                           shell=(os.name == "nt"))
        return r.stdout.strip() or None
    except Exception:
        return None


# ─── Hash / JSON ─────────────────────────────────────────────────────────────
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_arquivo(p: str | Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def salvar_json(p: str | Path, obj) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def ler_json(p: str | Path, padrao=None):
    p = Path(p)
    if not p.exists():
        return padrao
    return json.loads(p.read_text(encoding="utf-8"))


# ─── Normalização e comparação ───────────────────────────────────────────────
def sem_acento(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def norm_texto(v) -> str:
    """Minúsculas, sem acentos, espaços colapsados. None → ''."""
    if v is None:
        return ""
    s = sem_acento(str(v)).lower()
    return re.sub(r"\s+", " ", s).strip()


def norm_processo(v) -> str:
    """'PE 83 /2026', 'pe 83/2026 - SMSAN/FAAC' → 'PE 83/2026' (chave natural)."""
    s = re.sub(r"\s+", " ", str(v or "")).strip().upper()
    s = re.sub(r"\s*-\s*SMSAN/FAAC$", "", s)
    s = re.sub(r"\s*/\s*", "/", s)
    m = re.match(r"^([A-Z]{1,4})\s*0*(\d+)/(\d{4})$", s)
    return f"{m.group(1)} {int(m.group(2))}/{m.group(3)}" if m else s


def ano_processo(chave: str) -> int | None:
    m = re.search(r"/(\d{4})$", chave or "")
    return int(m.group(1)) if m else None


def valor_brl(v) -> float | None:
    """'R$ 1.234,56' → 1234.56; números passam direto; vazio → None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s or s in "-.,":
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")   # '120.000' na tela = 120 mil (separador de milhar pt-BR)
    try:
        return float(s)
    except ValueError:
        return None


def data_iso(v) -> str | None:
    """'03/02/2025', '2025-02-03', '2025-02-03T00:00' → '2025-02-03'."""
    if v is None:
        return None
    s = str(v).strip()
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    return None


def so_digitos(v) -> str:
    return re.sub(r"\D", "", str(v or ""))


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    ant = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(min(ant[j] + 1, atual[j - 1] + 1, ant[j - 1] + (ca != cb)))
        ant = atual
    return ant[-1]


def similaridade_lev(a, b) -> float:
    """1 − distância/len(maior), sobre texto normalizado. Ambos vazios → 1."""
    a, b = norm_texto(a), norm_texto(b)
    if not a and not b:
        return 1.0
    return 1.0 - levenshtein(a, b) / max(len(a), len(b))


def ngramas(texto: str, n: int = 5) -> set:
    palavras = re.findall(r"\w+", norm_texto(texto))
    return {tuple(palavras[i:i + n]) for i in range(max(0, len(palavras) - n + 1))}


def jaccard(a: set, b: set) -> float | None:
    if not a and not b:
        return None
    return len(a & b) / len(a | b)


def prf1(previstos, reais) -> dict:
    """Precisão, revocação e F1 entre dois multiconjuntos (listas)."""
    from collections import Counter
    cp, cr = Counter(previstos), Counter(reais)
    inter = sum((cp & cr).values())
    p = inter / sum(cp.values()) if cp else (1.0 if not cr else 0.0)
    r = inter / sum(cr.values()) if cr else (1.0 if not cp else 0.0)
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precisao": p, "revocacao": r, "f1": f1, "n_prev": sum(cp.values()), "n_real": sum(cr.values())}


# ─── Limite de taxa ──────────────────────────────────────────────────────────
class LimiteTaxa:
    def __init__(self, intervalo_s: float):
        self.intervalo = float(intervalo_s)
        self._ultimo = 0.0

    def esperar(self):
        dt = time.monotonic() - self._ultimo
        if dt < self.intervalo:
            time.sleep(self.intervalo - dt)
        self._ultimo = time.monotonic()


def sessao_http(cfg: dict):
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = cfg["acesso"]["user_agent"]
    return s


def get_com_backoff(sessao, url: str, cfg: dict, limite: LimiteTaxa | None = None, **kw):
    """GET com limite de taxa e backoff exponencial em 429/5xx. Devolve (resp|None, erro|None)."""
    tent = int(cfg["acesso"].get("tentativas", 4))
    erro = None
    for n in range(tent):
        if limite:
            limite.esperar()
        try:
            r = sessao.get(url, timeout=cfg["acesso"]["timeout_http_s"], **kw)
            if r.status_code == 429 or r.status_code >= 500:
                erro = f"HTTP {r.status_code}"
                time.sleep(min(60, 2 ** (n + 1)))
                continue
            return r, None
        except Exception as e:  # noqa: BLE001
            erro = str(e)[:300]
            time.sleep(min(60, 2 ** (n + 1)))
    return None, erro
