"""
Camada de banco de dados com adapter SQLite ↔ Postgres.

ESTRATÉGIA:
  - Sem configuração → SQLite local (.streamlit/data/app.db) — modo dev padrão
  - Com [postgres] nos Secrets → conecta no Postgres da nuvem
    (funciona com Neon, Supabase, Railway, AWS RDS, qualquer provedor Postgres)

O adapter traduz queries SQLite pra Postgres em tempo de execução, então
o resto do código (telas, repositórios, serviços) é IDÊNTICO nos dois modos.

Provedores Postgres testados:
  - Neon (neon.tech) — usar pooled connection (host com -pooler)
  - Supabase — usar Transaction Pooler (porta 6543)
  - Railway, AWS RDS, qualquer outro — Direct connection padrão

Tradução feita pelo adapter:
  - Placeholders: `?` → `%s`
  - `datetime('now')` → `NOW()`
  - `DATE('now')` → `CURRENT_DATE`
  - `julianday(a) - julianday(b)` → `(a::date - b::date)`
  - `IFNULL` → `COALESCE`
  - `INSERT OR IGNORE` → `INSERT ... ON CONFLICT DO NOTHING`
  - `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
  - `REAL` → `DOUBLE PRECISION`
  - `TEXT DEFAULT NOW()` → `TIMESTAMPTZ DEFAULT NOW()`
  - `lastrowid` → busca via `RETURNING id` adicionado automaticamente
  - PRAGMAs SQLite → ignorados
"""
from __future__ import annotations

import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

# ============================================================
# CAMINHOS
# ============================================================
PASTA_DADOS = Path(".streamlit/data")
ARQUIVO_BANCO = PASTA_DADOS / "app.db"

# Lock para escritas concorrentes (Streamlit pode ter múltiplas threads)
_LOCK_ESCRITA = threading.RLock()

# Cache da conexão por thread
_CONEXOES_THREAD: dict[int, Any] = {}

# Cache da string de conexão Postgres (carregada uma vez)
_CONEXAO_STRING_POSTGRES: Optional[str] = None


def garantir_pasta_dados() -> None:
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)


# ============================================================
# DETECÇÃO DO MODO DE BANCO
# ============================================================

def usar_postgres() -> bool:
    """
    Decide se vai usar Postgres (nuvem) ou SQLite (local).

    Ativa Postgres se encontrar (em ordem de prioridade):
      1. [postgres].connection_string nos Secrets — formato genérico recomendado
      2. [neon].connection_string nos Secrets — alias específico
      3. [supabase].connection_string nos Secrets — retrocompatibilidade
      4. Variável de ambiente DATABASE_URL — padrão de plataformas como Railway/Heroku
      5. Variável de ambiente POSTGRES_CONNECTION_STRING — fallback explícito

    Senão, cai no SQLite local.
    """
    global _CONEXAO_STRING_POSTGRES

    if _CONEXAO_STRING_POSTGRES is not None:
        return True

    # 1, 2, 3 — Streamlit Secrets em ordem de prioridade
    try:
        import streamlit as st
        for chave in ("postgres", "neon", "supabase"):
            if chave in st.secrets:
                cs = st.secrets[chave].get("connection_string")
                if cs:
                    _CONEXAO_STRING_POSTGRES = cs
                    return True
    except Exception:
        pass

    # 4 — Padrão de muitas plataformas cloud
    env = os.environ.get("DATABASE_URL")
    if env:
        _CONEXAO_STRING_POSTGRES = env
        return True

    # 5 — Fallback explícito
    env = os.environ.get("POSTGRES_CONNECTION_STRING")
    if env:
        _CONEXAO_STRING_POSTGRES = env
        return True

    return False


# Alias retrocompatível pra código que ainda chama usar_supabase()
def usar_supabase() -> bool:
    """Alias retrocompatível. Use `usar_postgres()` em código novo."""
    return usar_postgres()


# ============================================================
# ADAPTER POSTGRES — Tradução automática SQLite ↔ Postgres
# ============================================================

class _RowDict(dict):
    """Dict que também aceita acesso por índice (igual sqlite3.Row)."""
    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = list(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)

    def keys(self):
        return list(super().keys())


class _CursorPostgres:
    """Cursor adaptador. Resto do código acha que tá falando com sqlite3."""

    def __init__(self, pg_cursor):
        self._cur = pg_cursor
        self.lastrowid: Optional[int] = None

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in self._cur.description]
        return _RowDict(cols, row)

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows:
            return []
        cols = [d[0] for d in self._cur.description]
        return [_RowDict(cols, r) for r in rows]

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        self._cur.close()


class _ConexaoPostgres:
    """
    Conexão adaptadora. Mesma interface de sqlite3.Connection, mas executa
    Postgres por baixo.

    Configurações importantes:
      - autocommit=True: mesmo comportamento do nosso SQLite (transações
        explícitas via BEGIN/COMMIT/ROLLBACK)
      - prepare_threshold=None: desabilita prepared statements
        (necessário pra Transaction Poolers — Supabase 6543 e Neon -pooler —
        que reutilizam conexões entre transações)
    """

    def __init__(self, dsn: str):
        import psycopg
        self._dsn = dsn  # guarda pra possíveis reconexões
        self._conn = psycopg.connect(
            dsn,
            autocommit=True,
            prepare_threshold=None,
        )
        self.row_factory = None  # compatibilidade com sqlite3

    def _reconectar(self):
        """Reabre a conexão (usado quando o Neon fecha por timeout)."""
        import psycopg
        try:
            self._conn.close()
        except Exception:
            pass
        self._conn = psycopg.connect(
            self._dsn,
            autocommit=True,
            prepare_threshold=None,
        )

    def execute(self, sql: str, params: tuple = ()) -> _CursorPostgres:
        sql_pg, params_pg = _traduzir_sql(sql, params)

        # PRAGMAs do SQLite são ignorados em Postgres
        if sql_pg is None:
            cur = self._conn.cursor()
            return _CursorPostgres(cur)

        # Tenta executar; se a conexão estiver fechada, reconecta e tenta de novo
        try:
            cur = self._conn.cursor()
            cur.execute(sql_pg, params_pg)
        except Exception as e:
            msg = str(e).lower()
            if (
                "connection is closed" in msg
                or "server closed" in msg
                or "ssl connection has been closed" in msg
                or "connection closed" in msg
                or "no connection to the server" in msg
            ):
                # Reconecta e tenta uma vez só
                self._reconectar()
                cur = self._conn.cursor()
                cur.execute(sql_pg, params_pg)
            else:
                raise

        wrapper = _CursorPostgres(cur)

        # Se foi um INSERT, captura o id criado (lastrowid)
        if "RETURNING" in sql_pg.upper() and cur.description:
            try:
                row = cur.fetchone()
                if row and len(row) > 0:
                    wrapper.lastrowid = row[0]
                cur._description = None  # type: ignore
            except Exception:
                pass

        return wrapper

    def executescript(self, sql: str) -> None:
        """Executa múltiplos statements (usado por migrations)."""
        sql_pg, _ = _traduzir_sql(sql, ())
        if sql_pg is None:
            return
        try:
            cur = self._conn.cursor()
            cur.execute(sql_pg)
            cur.close()
        except Exception as e:
            msg = str(e).lower()
            if (
                "connection is closed" in msg
                or "server closed" in msg
                or "ssl connection has been closed" in msg
                or "connection closed" in msg
            ):
                self._reconectar()
                cur = self._conn.cursor()
                cur.execute(sql_pg)
                cur.close()
            else:
                raise

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


# ============================================================
# TRADUTOR DE QUERIES
# ============================================================

def _traduzir_sql(sql: str, params: tuple) -> tuple[Optional[str], tuple]:
    """
    Recebe (query SQLite, params) e devolve (query Postgres, params).
    Retorna (None, _) se a query deve ser IGNORADA (caso dos PRAGMAs).
    """
    sql_clean = sql.strip()
    sql_upper = sql_clean.upper()

    # 1) PRAGMAs do SQLite não existem em Postgres - ignora
    if sql_upper.startswith("PRAGMA "):
        return None, ()

    # 2) Comandos de transação
    if sql_upper in ("BEGIN;", "COMMIT;", "ROLLBACK;",
                     "BEGIN", "COMMIT", "ROLLBACK"):
        return sql_clean.rstrip(";"), ()

    sql_pg = sql

    # 3) Funções de data (PRIMEIRO — antes do CREATE TABLE)
    sql_pg = re.sub(r"datetime\s*\(\s*'now'\s*\)", "NOW()", sql_pg, flags=re.IGNORECASE)
    sql_pg = re.sub(r"DATE\s*\(\s*'now'\s*\)", "CURRENT_DATE", sql_pg, flags=re.IGNORECASE)
    sql_pg = re.sub(
        r"julianday\s*\(\s*'now'\s*\)\s*-\s*julianday\s*\(\s*([^)]+?)\s*\)",
        r"(CURRENT_DATE - (\1)::date)",
        sql_pg, flags=re.IGNORECASE,
    )
    sql_pg = re.sub(
        r"julianday\s*\(\s*([^)]+?)\s*\)\s*-\s*julianday\s*\(\s*([^)]+?)\s*\)",
        r"((\1)::date - (\2)::date)",
        sql_pg, flags=re.IGNORECASE,
    )
    sql_pg = re.sub(r"\bIFNULL\b", "COALESCE", sql_pg, flags=re.IGNORECASE)

    # 4) Tipos em CREATE TABLE (DEPOIS — pra TEXT DEFAULT (NOW()) ser reconhecido)
    if "CREATE TABLE" in sql_upper:
        sql_pg = _traduzir_create_table(sql_pg)

    # 5) INSERT OR IGNORE → ON CONFLICT DO NOTHING
    eh_or_ignore = False
    if re.search(r"INSERT\s+OR\s+IGNORE\s+INTO", sql_pg, flags=re.IGNORECASE):
        sql_pg = re.sub(
            r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO",
            sql_pg, flags=re.IGNORECASE,
        )
        eh_or_ignore = True
    elif re.search(r"INSERT\s+OR\s+REPLACE\s+INTO", sql_pg, flags=re.IGNORECASE):
        sql_pg = re.sub(
            r"INSERT\s+OR\s+REPLACE\s+INTO", "INSERT INTO",
            sql_pg, flags=re.IGNORECASE,
        )
        eh_or_ignore = True

    # 6) Adiciona RETURNING id em INSERTs (pra lastrowid funcionar)
    tem_on_conflict = "ON CONFLICT" in sql_pg.upper()
    if sql_upper.lstrip().startswith("INSERT") and "RETURNING" not in sql_upper:
        # Tabelas sem PK chamada "id" — adicione aqui conforme o projeto evoluir
        TABELAS_SEM_ID = {
            "schema_versao", "parametros_sistema",
        }
        m = re.match(r"\s*INSERT\s+(?:OR\s+\w+\s+)?INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                     sql_pg, flags=re.IGNORECASE)
        nome_tabela = m.group(1).lower() if m else ""

        if eh_or_ignore and not tem_on_conflict:
            sql_pg = sql_pg.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        elif (nome_tabela not in TABELAS_SEM_ID
              and not eh_or_ignore
              and not tem_on_conflict):
            sql_pg = sql_pg.rstrip().rstrip(";") + " RETURNING id"

    # 7) Placeholders: SQLite usa ?, Postgres usa %s
    sql_pg = sql_pg.replace("?", "%s")

    return sql_pg, params


def _traduzir_create_table(sql: str) -> str:
    """Traduz CREATE TABLE do SQLite pra Postgres."""
    sql = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "SERIAL PRIMARY KEY",
        sql, flags=re.IGNORECASE,
    )
    sql = re.sub(r"\bREAL\b", "DOUBLE PRECISION", sql, flags=re.IGNORECASE)

    # TEXT DEFAULT NOW() vira TIMESTAMPTZ
    sql = re.sub(
        r"\bTEXT\b(\s+NOT\s+NULL)?\s+DEFAULT\s+\(\s*NOW\(\)\s*\)",
        lambda m: f"TIMESTAMPTZ{m.group(1) or ''} DEFAULT NOW()",
        sql, flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"\bTEXT\b(\s+NOT\s+NULL)?\s+DEFAULT\s+NOW\(\)",
        lambda m: f"TIMESTAMPTZ{m.group(1) or ''} DEFAULT NOW()",
        sql, flags=re.IGNORECASE,
    )
    sql = re.sub(
        r"\bTEXT\b(\s+NOT\s+NULL)?\s+DEFAULT\s+CURRENT_DATE",
        lambda m: f"DATE{m.group(1) or ''} DEFAULT CURRENT_DATE",
        sql, flags=re.IGNORECASE,
    )

    return sql


# ============================================================
# FUNÇÕES PÚBLICAS
# ============================================================

def obter_conexao():
    """
    Devolve uma conexão pra thread atual.
    - SQLite: sqlite3.Connection
    - Postgres: _ConexaoPostgres (adapter)

    Em ambos os casos, conn.execute() funciona normalmente.
    
    Detecta conexões fechadas (timeout do Neon) e reconecta automaticamente.
    """
    thread_id = threading.get_ident()

    # Verifica se já temos uma conexão pra essa thread e se ainda está viva
    if thread_id in _CONEXOES_THREAD:
        conn = _CONEXOES_THREAD[thread_id]
        if _conexao_viva(conn):
            return conn
        # Conexão morta — remove do cache e cria nova
        try:
            conn.close()
        except Exception:
            pass
        del _CONEXOES_THREAD[thread_id]

    if usar_postgres():
        conn = _ConexaoPostgres(_CONEXAO_STRING_POSTGRES)
        _CONEXOES_THREAD[thread_id] = conn
        return conn

    # Modo SQLITE (padrão)
    garantir_pasta_dados()
    conn = sqlite3.connect(
        ARQUIVO_BANCO,
        check_same_thread=False,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    _CONEXOES_THREAD[thread_id] = conn
    return conn


def _conexao_viva(conn) -> bool:
    """
    Verifica se uma conexão ainda está aberta.
    Faz um SELECT 1 leve. Se falhar, retorna False.
    """
    try:
        # Postgres: verifica via atributo 'closed' antes (mais rápido)
        if usar_postgres():
            inner = getattr(conn, "_conn", None)
            if inner is None:
                return False
            # psycopg3 tem closed boolean property
            if getattr(inner, "closed", False):
                return False
        # Faz um query leve pra confirmar
        cur = conn.execute("SELECT 1;")
        cur.fetchone()
        return True
    except Exception:
        return False


@contextmanager
def transacao() -> Generator:
    """Context manager pra transação. Commit no sucesso, rollback em erro."""
    conn = obter_conexao()
    with _LOCK_ESCRITA:
        try:
            conn.execute("BEGIN;")
            yield conn
            conn.execute("COMMIT;")
        except Exception:
            try:
                conn.execute("ROLLBACK;")
            except Exception:
                pass
            raise


def fechar_conexoes() -> None:
    for conn in _CONEXOES_THREAD.values():
        try:
            conn.close()
        except Exception:
            pass
    _CONEXOES_THREAD.clear()
