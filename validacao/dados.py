"""Acesso ao snapshot congelado (Parquet) via pandas e DuckDB.

Todo gabarito da A2 e da B é calculado aqui, sobre o snapshot, nunca sobre a base viva.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from validacao.comum import dir_execucao, norm_processo, so_digitos


class Snapshot:
    def __init__(self, run_id: str):
        self.dir = dir_execucao(run_id) / "snapshot"
        if not (self.dir / "snapshot.json").exists():
            raise FileNotFoundError(f"Snapshot ausente em {self.dir}; rode a etapa 'snapshot'.")
        self._dfs: dict[str, pd.DataFrame] = {}
        self._duck = None

    def df(self, tabela: str) -> pd.DataFrame:
        if tabela not in self._dfs:
            p = self.dir / f"{tabela}.parquet"
            self._dfs[tabela] = pd.read_parquet(p) if p.exists() else pd.DataFrame()
        return self._dfs[tabela]

    # ─── SQL (DuckDB) ────────────────────────────────────────────────────────
    def sql(self, consulta: str, **params) -> pd.DataFrame:
        if self._duck is None:
            import duckdb
            self._duck = duckdb.connect()
            for p in self.dir.glob("*.parquet"):
                caminho = str(p).replace("\\", "/").replace("'", "''")
                self._duck.execute(f"CREATE VIEW {p.stem} AS SELECT * FROM read_parquet('{caminho}')")
        return self._duck.execute(consulta, params or None).df() if params else self._duck.execute(consulta).df()

    # ─── visão por processo ──────────────────────────────────────────────────
    @property
    def licitacoes(self) -> pd.DataFrame:
        df = self.df("licitacoes").copy()
        if "chave" not in df.columns:
            df["chave"] = df["processo"].map(norm_processo)
            df["ano"] = df["chave"].str.extract(r"/(\d{4})$")[0].astype("Int64")
        return df

    @lru_cache(maxsize=None)
    def _forn_doc(self) -> dict:
        f = self.df("fornecedores")
        return {int(r.id): so_digitos(r.cpf_cnpj) for r in f.itertuples()}

    @lru_cache(maxsize=None)
    def _itens_legado(self) -> set:
        it = self.df("itens_licitacao")
        return set(it.loc[it["codigo"].fillna("").astype(str).str.strip() != "", "licitacao_id"].astype(int))

    def origem(self, lic: dict) -> str:
        """TRANSPARENCIA: registro criado pela fonte atual.
        JSF_ENRIQUECIDO: carga do portal JSF que o coletor atual enriqueceu (tem url_detalhe, mas por
        regra do coletor mantém itens e situação originais e não recebe modalidade nem nº do edital).
        JSF_LEGADO: carga do portal JSF sem enriquecimento."""
        legado = int(lic["id"]) in self._itens_legado()
        if lic.get("url_detalhe"):
            return "JSF_ENRIQUECIDO" if legado else "TRANSPARENCIA"
        return "JSF_LEGADO"

    def processo(self, chave: str) -> dict | None:
        lics = self.licitacoes
        linha = lics[lics["chave"] == chave]
        if linha.empty:
            return None
        lic = linha.iloc[0].to_dict()
        lid = int(lic["id"])
        it = self.df("itens_licitacao")
        itens = it[it["licitacao_id"] == lid].sort_values("seq")
        part = self.df("participacoes")
        part = part[part["licitacao_id"] == lid]
        docs = self._forn_doc()
        participantes = [docs.get(int(f), "") for f in part.loc[part["participou"].astype("boolean").fillna(True).astype(bool),
                                                                 "fornecedor_id"]]
        vencedores = [docs.get(int(f), "") for f in part.loc[part["vencedor"].astype("boolean").fillna(False).astype(bool),
                                                              "fornecedor_id"]]
        emp = self.df("empenhos")
        emp = emp[emp["item_id"].isin(set(itens["id"]))]
        documentos = self.df("documentos_licitacao")
        documentos = documentos[documentos["licitacao_id"] == lid]
        return {
            "licitacao": lic,
            "origem": self.origem(lic),
            "itens_legado": lid in self._itens_legado(),
            "itens": itens.to_dict("records"),
            "participantes": [p for p in participantes if p],
            "vencedores": [v for v in vencedores if v],
            "empenhos": [{**e, "doc": docs.get(int(e["fornecedor_id"]), "") if pd.notna(e.get("fornecedor_id")) else ""}
                         for e in emp.to_dict("records")],
            "documentos": documentos.to_dict("records"),
        }


def carregar(run_id: str) -> Snapshot:
    return Snapshot(run_id)


def caminho_snapshot(run_id: str) -> Path:
    return dir_execucao(run_id) / "snapshot"
