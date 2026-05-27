"""
Schema do banco de dados — LLE Protestos.

Tabelas:
- schema_versao: controle de versão das migrations
- usuario: cadastro + autenticação
- parametros_sistema: chave/valor genérico
- log_auditoria: log de ações
- cliente_protesto: cadastro de clientes do Protesto (chave: cod_parceiro)
- upload_sankhya: cada upload da planilha (passo 1 ou 2)
- remessa_protesto: cada lote de protesto gerado (passo 3) por mês
- titulo_protesto: cada título individual (Nro Único)
- andamento_protesto: status corrente do cliente
- historico_andamento: histórico de mudanças de status
- evento_serasa: cada arquivo Serasa enviado/recebido
- titulo_serasa: cada título em um arquivo Serasa
"""
from __future__ import annotations
from typing import List


MIGRATIONS: List[str] = []


# ============================================================
# MIGRATION 001 — Tabelas base do esqueleto
# ============================================================
MIGRATIONS.append("""
CREATE TABLE IF NOT EXISTS schema_versao (
    versao INTEGER PRIMARY KEY,
    aplicada_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS usuario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    perfil TEXT NOT NULL CHECK(perfil IN ('ADMIN', 'USUARIO', 'DIRETORIA')),
    ativo INTEGER NOT NULL DEFAULT 1,
    deve_trocar_senha INTEGER NOT NULL DEFAULT 0,
    chave_aprovacao TEXT,
    aprovado INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    ultimo_login TEXT
);

CREATE INDEX IF NOT EXISTS idx_usuario_email ON usuario(email);
CREATE INDEX IF NOT EXISTS idx_usuario_perfil_ativo ON usuario(perfil, ativo);

CREATE TABLE IF NOT EXISTS parametros_sistema (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL,
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS log_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER REFERENCES usuario(id),
    acao TEXT NOT NULL,
    entidade TEXT,
    entidade_id INTEGER,
    detalhes TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_usuario ON log_auditoria(usuario_id);
CREATE INDEX IF NOT EXISTS idx_audit_acao ON log_auditoria(acao);
""")


# ============================================================
# MIGRATION 002 — Atualizar perfis (USUARIO→OPERADOR, +FINANCEIRO)
# ============================================================
MIGRATIONS.append("-- aplicada via Python (ver aplicar_migrations)")


# ============================================================
# MIGRATION 003 — Tabelas do projeto Protestos
# ============================================================
MIGRATIONS.append("""
CREATE TABLE IF NOT EXISTS cliente_protesto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_parceiro INTEGER UNIQUE,
    nome TEXT NOT NULL,
    cnpj_cpf TEXT,
    arquivado INTEGER NOT NULL DEFAULT 0,
    baixado INTEGER NOT NULL DEFAULT 0,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cliente_cod ON cliente_protesto(cod_parceiro);
CREATE INDEX IF NOT EXISTS idx_cliente_nome ON cliente_protesto(nome);
CREATE INDEX IF NOT EXISTS idx_cliente_arquivado ON cliente_protesto(arquivado);

CREATE TABLE IF NOT EXISTS upload_sankhya (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    passo INTEGER NOT NULL CHECK(passo IN (1, 2, 3)),
    mes_referencia TEXT NOT NULL,
    nome_arquivo TEXT NOT NULL,
    total_titulos_brutos INTEGER NOT NULL DEFAULT 0,
    total_titulos_validos INTEGER NOT NULL DEFAULT 0,
    total_clientes_validos INTEGER NOT NULL DEFAULT 0,
    usuario_id INTEGER REFERENCES usuario(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_upload_passo ON upload_sankhya(passo);
CREATE INDEX IF NOT EXISTS idx_upload_mes ON upload_sankhya(mes_referencia);

CREATE TABLE IF NOT EXISTS remessa_protesto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mes_referencia TEXT NOT NULL,
    nome_arquivo_gerado TEXT NOT NULL,
    total_clientes INTEGER NOT NULL DEFAULT 0,
    total_titulos INTEGER NOT NULL DEFAULT 0,
    valor_total REAL NOT NULL DEFAULT 0.0,
    usuario_id INTEGER REFERENCES usuario(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_remessa_mes ON remessa_protesto(mes_referencia);

CREATE TABLE IF NOT EXISTS titulo_protesto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL REFERENCES cliente_protesto(id),
    remessa_id INTEGER REFERENCES remessa_protesto(id),
    nro_unico TEXT NOT NULL,
    nro_nota TEXT,
    empresa TEXT NOT NULL,
    empresa_cod INTEGER,
    vendedor_cod INTEGER,
    vendedor_nome TEXT,
    banco_descricao TEXT,
    banco_codigo INTEGER,
    valor REAL NOT NULL,
    dt_vencimento TEXT,
    atraso_dias INTEGER,
    historico TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_titulo_cliente ON titulo_protesto(cliente_id);
CREATE INDEX IF NOT EXISTS idx_titulo_remessa ON titulo_protesto(remessa_id);
CREATE INDEX IF NOT EXISTS idx_titulo_nro_unico ON titulo_protesto(nro_unico);

CREATE TABLE IF NOT EXISTS andamento_protesto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL UNIQUE REFERENCES cliente_protesto(id),
    status_protesto TEXT NOT NULL DEFAULT 'NAO_PROTESTADO',
    status_serasa TEXT NOT NULL DEFAULT 'NAO_ENVIADO',
    indicador_consolidado TEXT NOT NULL DEFAULT 'PENDENTE_PROTESTO',
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_andamento_status_p ON andamento_protesto(status_protesto);
CREATE INDEX IF NOT EXISTS idx_andamento_status_s ON andamento_protesto(status_serasa);

CREATE TABLE IF NOT EXISTS historico_andamento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL REFERENCES cliente_protesto(id),
    tipo_mudanca TEXT NOT NULL,
    status_anterior TEXT,
    status_novo TEXT,
    observacao TEXT,
    usuario_id INTEGER REFERENCES usuario(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_hist_cliente ON historico_andamento(cliente_id);

CREATE TABLE IF NOT EXISTS evento_serasa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL CHECK(tipo IN ('INCLUSAO', 'EXCLUSAO')),
    data_arquivo TEXT NOT NULL,
    sequencial INTEGER NOT NULL UNIQUE,
    nome_arquivo TEXT NOT NULL,
    total_clientes INTEGER NOT NULL DEFAULT 0,
    usuario_id INTEGER REFERENCES usuario(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_serasa_seq ON evento_serasa(sequencial);
CREATE INDEX IF NOT EXISTS idx_serasa_data ON evento_serasa(data_arquivo);

CREATE TABLE IF NOT EXISTS titulo_serasa (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id INTEGER NOT NULL REFERENCES evento_serasa(id),
    cliente_id INTEGER REFERENCES cliente_protesto(id),
    cnpj_cpf TEXT,
    nome TEXT NOT NULL,
    valor REAL,
    cep TEXT,
    nro_unico_serasa TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_titulo_serasa_evento ON titulo_serasa(evento_id);
CREATE INDEX IF NOT EXISTS idx_titulo_serasa_cliente ON titulo_serasa(cliente_id);
CREATE INDEX IF NOT EXISTS idx_titulo_serasa_nome ON titulo_serasa(nome);
""")


# ============================================================
# MIGRATION 004 — Remove NOT NULL de cod_parceiro
# (Serasa não tem essa info, precisamos permitir cliente vindo só do Serasa)
# ============================================================
MIGRATIONS.append("-- aplicada via Python (ver aplicar_migrations)")


# ============================================================
# MIGRATION 005 — Tabelas pro carregamento do cartório
# ============================================================
MIGRATIONS.append("""
CREATE TABLE IF NOT EXISTS upload_cartorio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_arquivo TEXT NOT NULL,
    total_linhas INTEGER NOT NULL DEFAULT 0,
    total_clientes INTEGER NOT NULL DEFAULT 0,
    total_cancelados INTEGER NOT NULL DEFAULT 0,
    usuario_id INTEGER REFERENCES usuario(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_upload_cart_data ON upload_cartorio(criado_em);

CREATE TABLE IF NOT EXISTS titulo_cartorio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_id INTEGER REFERENCES upload_cartorio(id),
    cliente_id INTEGER NOT NULL REFERENCES cliente_protesto(id),
    devedor_nome TEXT NOT NULL,
    devedor_documento TEXT,
    cod_parceiro INTEGER,
    cartorio TEXT,
    municipio TEXT,
    uf TEXT,
    protocolo TEXT,
    nro_titulo TEXT,
    valor REAL,
    saldo REAL,
    data_protesto TEXT,
    data_vencimento TEXT,
    data_emissao TEXT,
    cancelado INTEGER NOT NULL DEFAULT 0,
    data_cancelamento TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_titulo_cart_cliente ON titulo_cartorio(cliente_id);
CREATE INDEX IF NOT EXISTS idx_titulo_cart_upload ON titulo_cartorio(upload_id);
CREATE INDEX IF NOT EXISTS idx_titulo_cart_protocolo ON titulo_cartorio(protocolo);
CREATE INDEX IF NOT EXISTS idx_titulo_cart_cancelado ON titulo_cartorio(cancelado);
""")


# ============================================================
# MIGRATION 006 — Índices de performance (Postgres + SQLite)
# Aplicação varia por banco — ver aplicar_migrations
# ============================================================
MIGRATIONS.append("-- aplicada via Python (ver aplicar_migrations)")


# ============================================================
# MIGRATION 007 — UNIQUE constraint anti-duplicação no cartório
# Garante em hardware que (protocolo, cartorio) é único.
# ============================================================
MIGRATIONS.append("-- aplicada via Python (ver aplicar_migrations)")


# ============================================================
# MIGRATION 008 — Solicitações de protesto
# ============================================================
MIGRATIONS.append("""
CREATE TABLE IF NOT EXISTS solicitacao_protesto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_parceiro INTEGER NOT NULL,
    cliente_id INTEGER REFERENCES cliente_protesto(id),
    valor REAL,
    nro_nota TEXT,
    incluir_serasa INTEGER NOT NULL DEFAULT 0,
    observacao TEXT,
    status TEXT NOT NULL DEFAULT 'PENDENTE',
    solicitante_id INTEGER NOT NULL REFERENCES usuario(id),
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    atendido_por_id INTEGER REFERENCES usuario(id),
    atendido_em TEXT,
    obs_atendimento TEXT,
    motivo_recusa TEXT,
    auto_atendida INTEGER NOT NULL DEFAULT 0,
    visualizada_pelo_solicitante INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_solic_status ON solicitacao_protesto(status);
CREATE INDEX IF NOT EXISTS idx_solic_solicitante ON solicitacao_protesto(solicitante_id);
CREATE INDEX IF NOT EXISTS idx_solic_cod ON solicitacao_protesto(cod_parceiro);
CREATE INDEX IF NOT EXISTS idx_solic_criado ON solicitacao_protesto(criado_em);
""")


# ============================================================
# MIGRATION 009 — Anti-duplicação em titulo_serasa (hardware)
# ============================================================
# Limpa duplicatas existentes + cria UNIQUE em (evento_id, nro_unico_serasa).
# Aplicada via Python (vê aplicar_migrations) por causa do DELETE.
MIGRATIONS.append("-- aplicada via Python (ver aplicar_migrations)")


# ============================================================
# APLICAÇÃO
# ============================================================
def aplicar_migrations(conn) -> int:
    """Aplica todas as migrations pendentes. Idempotente."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_versao (
            versao INTEGER PRIMARY KEY,
            aplicada_em TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    cur = conn.execute("SELECT COALESCE(MAX(versao), 0) FROM schema_versao;")
    versao_atual = cur.fetchone()[0]

    from src.banco.conexao import usar_postgres

    # AUTO-REPARO: se a tabela usuario não existe mas schema_versao já tem
    # versão >= 1, a migration anterior falhou no meio. Resetamos versao_atual
    # pra 0 pra reaplicar tudo (os CREATE TABLE têm IF NOT EXISTS).
    if versao_atual >= 1:
        try:
            conn.execute("SELECT 1 FROM usuario LIMIT 1;").fetchone()
        except Exception:
            # Tabela usuario não existe — refaz tudo
            versao_atual = 0
            try:
                conn.execute("DELETE FROM schema_versao;")
            except Exception:
                pass

    for i, sql in enumerate(MIGRATIONS, start=1):
        if i <= versao_atual:
            continue

        if i == 1:
            conn.executescript(sql)

        elif i == 2:
            # Atualiza dados existentes (USUARIO → OPERADOR)
            conn.execute(
                "UPDATE usuario SET perfil = 'OPERADOR' WHERE perfil = 'USUARIO';"
            )
            # Atualiza CHECK constraint
            if usar_postgres():
                try:
                    conn.execute(
                        "ALTER TABLE usuario DROP CONSTRAINT IF EXISTS usuario_perfil_check;"
                    )
                except Exception:
                    pass
                try:
                    conn.execute(
                        "ALTER TABLE usuario ADD CONSTRAINT usuario_perfil_check "
                        "CHECK (perfil IN ('ADMIN', 'OPERADOR', 'DIRETORIA', 'FINANCEIRO'));"
                    )
                except Exception:
                    pass
            else:
                # SQLite: recriar tabela com CHECK novo
                try:
                    conn.executescript("""
                        CREATE TABLE usuario_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            nome TEXT NOT NULL,
                            email TEXT NOT NULL UNIQUE,
                            senha_hash TEXT NOT NULL,
                            perfil TEXT NOT NULL CHECK(perfil IN ('ADMIN', 'OPERADOR', 'DIRETORIA', 'FINANCEIRO')),
                            ativo INTEGER NOT NULL DEFAULT 1,
                            deve_trocar_senha INTEGER NOT NULL DEFAULT 0,
                            chave_aprovacao TEXT,
                            aprovado INTEGER NOT NULL DEFAULT 0,
                            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
                            ultimo_login TEXT
                        );
                        INSERT INTO usuario_new SELECT * FROM usuario;
                        DROP TABLE usuario;
                        ALTER TABLE usuario_new RENAME TO usuario;
                        CREATE INDEX IF NOT EXISTS idx_usuario_email ON usuario(email);
                        CREATE INDEX IF NOT EXISTS idx_usuario_perfil_ativo ON usuario(perfil, ativo);
                    """)
                except Exception:
                    pass

        elif i == 3:
            conn.executescript(sql)

        elif i == 4:
            # Remove NOT NULL de cod_parceiro
            if usar_postgres():
                try:
                    conn.execute(
                        "ALTER TABLE cliente_protesto "
                        "ALTER COLUMN cod_parceiro DROP NOT NULL;"
                    )
                except Exception:
                    pass
            else:
                # SQLite: recriar tabela
                try:
                    conn.executescript("""
                        CREATE TABLE cliente_protesto_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            cod_parceiro INTEGER UNIQUE,
                            nome TEXT NOT NULL,
                            cnpj_cpf TEXT,
                            arquivado INTEGER NOT NULL DEFAULT 0,
                            baixado INTEGER NOT NULL DEFAULT 0,
                            criado_em TEXT NOT NULL DEFAULT (datetime('now')),
                            atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
                        );
                        INSERT INTO cliente_protesto_new SELECT * FROM cliente_protesto;
                        DROP TABLE cliente_protesto;
                        ALTER TABLE cliente_protesto_new RENAME TO cliente_protesto;
                        CREATE INDEX IF NOT EXISTS idx_cliente_cod ON cliente_protesto(cod_parceiro);
                        CREATE INDEX IF NOT EXISTS idx_cliente_nome ON cliente_protesto(nome);
                        CREATE INDEX IF NOT EXISTS idx_cliente_arquivado ON cliente_protesto(arquivado);
                    """)
                except Exception:
                    pass

        elif i == 5:
            # Tabelas do carregamento do cartório
            conn.executescript(sql)

        elif i == 6:
            # Índices de performance
            indices_pg = [
                # Index funcional pra busca case-insensitive de nome
                "CREATE INDEX IF NOT EXISTS idx_cliente_nome_lower ON cliente_protesto (LOWER(nome));",
                # Andamento por cliente (JOIN frequente)
                "CREATE INDEX IF NOT EXISTS idx_andamento_cliente ON andamento_protesto(cliente_id);",
                # Devedor nome do cartório (busca por nome)
                "CREATE INDEX IF NOT EXISTS idx_titulo_cart_devedor_lower ON titulo_cartorio (LOWER(devedor_nome));",
                # Composto: status combinado
                "CREATE INDEX IF NOT EXISTS idx_andamento_combinado ON andamento_protesto(status_protesto, status_serasa);",
                # Cliente arquivado + baixado (filtros comuns)
                "CREATE INDEX IF NOT EXISTS idx_cliente_arq_baixado ON cliente_protesto(arquivado, baixado);",
            ]
            indices_sqlite = [
                # SQLite suporta LOWER em índice funcional desde 3.9
                "CREATE INDEX IF NOT EXISTS idx_cliente_nome_lower ON cliente_protesto (LOWER(nome));",
                "CREATE INDEX IF NOT EXISTS idx_andamento_cliente ON andamento_protesto(cliente_id);",
                "CREATE INDEX IF NOT EXISTS idx_titulo_cart_devedor_lower ON titulo_cartorio (LOWER(devedor_nome));",
                "CREATE INDEX IF NOT EXISTS idx_andamento_combinado ON andamento_protesto(status_protesto, status_serasa);",
                "CREATE INDEX IF NOT EXISTS idx_cliente_arq_baixado ON cliente_protesto(arquivado, baixado);",
            ]
            for stmt in (indices_pg if usar_postgres() else indices_sqlite):
                try:
                    conn.execute(stmt)
                except Exception:
                    pass

        elif i == 7:
            # UNIQUE em (protocolo, cartorio) — anti-duplicação em hardware.
            # Antes de criar o índice, limpa duplicatas existentes
            # (mantém a linha de menor id de cada combinação).
            try:
                conn.execute(
                    "DELETE FROM titulo_cartorio "
                    "WHERE id NOT IN ("
                    "  SELECT MIN(id) FROM titulo_cartorio "
                    "  GROUP BY protocolo, cartorio"
                    ");"
                )
            except Exception:
                pass

            # Agora cria o índice único
            stmt = (
                "CREATE UNIQUE INDEX IF NOT EXISTS uniq_titulo_cart_prot "
                "ON titulo_cartorio(protocolo, cartorio) "
                "WHERE protocolo IS NOT NULL AND protocolo != '';"
            )
            try:
                conn.execute(stmt)
            except Exception:
                # Em SQLite mais antigo, parte do WHERE pode falhar; tenta sem
                try:
                    conn.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uniq_titulo_cart_prot "
                        "ON titulo_cartorio(protocolo, cartorio);"
                    )
                except Exception:
                    pass

        elif i == 8:
            # Tabela de solicitações de protesto
            conn.executescript(sql)

        elif i == 9:
            # Anti-duplicação em titulo_serasa.
            # 1) Limpa duplicatas (mantém menor id por evento+nro_unico_serasa)
            # 2) Cria UNIQUE constraint
            try:
                conn.execute(
                    "DELETE FROM titulo_serasa "
                    "WHERE id NOT IN ("
                    "  SELECT MIN(id) FROM titulo_serasa "
                    "  WHERE nro_unico_serasa IS NOT NULL "
                    "    AND nro_unico_serasa != '' "
                    "  GROUP BY evento_id, nro_unico_serasa"
                    ") "
                    "AND nro_unico_serasa IS NOT NULL "
                    "AND nro_unico_serasa != '';"
                )
            except Exception:
                pass

            stmt = (
                "CREATE UNIQUE INDEX IF NOT EXISTS uniq_titulo_serasa_evt "
                "ON titulo_serasa(evento_id, nro_unico_serasa) "
                "WHERE nro_unico_serasa IS NOT NULL AND nro_unico_serasa != '';"
            )
            try:
                conn.execute(stmt)
            except Exception:
                # SQLite antigo: tenta sem WHERE
                try:
                    conn.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uniq_titulo_serasa_evt "
                        "ON titulo_serasa(evento_id, nro_unico_serasa);"
                    )
                except Exception:
                    pass

        # Marca versão
        if usar_postgres():
            conn.execute(
                "INSERT INTO schema_versao(versao) VALUES (%s) ON CONFLICT DO NOTHING;",
                (i,)
            )
        else:
            conn.execute(
                "INSERT OR IGNORE INTO schema_versao(versao) VALUES (?);",
                (i,)
            )

    return len(MIGRATIONS)


def inicializar_banco() -> None:
    """Chamado no startup do app."""
    from src.banco.conexao import obter_conexao
    conn = obter_conexao()
    aplicar_migrations(conn)
    _criar_parametros_default(conn)


def _criar_parametros_default(conn) -> None:
    defaults = {}
    for chave, valor in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO parametros_sistema (chave, valor) VALUES (?, ?);",
            (chave, valor),
        )
