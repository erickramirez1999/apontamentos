"""
Serviço: carregamento de relatório do cartório.

Persiste:
- 1 upload_cartorio (cabeçalho do arquivo)
- N titulo_cartorio (cada linha do arquivo)
- Atualiza/cria clientes (upsert por cod_parceiro ou nome)
- Atualiza status_protesto dos clientes:
  - Cliente com TODOS os títulos cancelados → PAGO + arquivado (não baixado)
  - Cliente com algum título não cancelado → PROTESTADO
"""
from __future__ import annotations

from src.banco.conexao import obter_conexao
from src.banco import repo_cliente
from src.servicos.parser_cartorio import RelatorioCartorio


def processar_relatorio_cartorio(
    relatorio: RelatorioCartorio,
    nome_arquivo: str,
    usuario_id: int,
) -> dict:
    """
    Processa o relatório do cartório.
    
    Retorna estatísticas: {clientes_criados, clientes_atualizados,
    titulos_inseridos, clientes_protestados, clientes_pagos}
    """
    conn = obter_conexao()

    # 0) DEDUPLICAÇÃO: protocolo + cartório identificam unicamente um título
    # Carrega os já existentes pra ignorar duplicatas
    protocolos_arquivo = list({
        (t.protocolo, t.cartorio) for t in relatorio.titulos
        if t.protocolo
    })

    chaves_existentes: set[tuple[str, str]] = set()
    if protocolos_arquivo:
        # Buscar todos os protocolos do arquivo que já estão no banco
        protocolos_so_nums = list({p for p, _ in protocolos_arquivo})
        placeholders = ",".join("?" * len(protocolos_so_nums))
        rows = conn.execute(
            f"SELECT protocolo, cartorio FROM titulo_cartorio "
            f"WHERE protocolo IN ({placeholders});",
            tuple(protocolos_so_nums)
        ).fetchall()
        chaves_existentes = {(r["protocolo"], r["cartorio"]) for r in rows}

    # Filtra os títulos: ignora os que já existem (mesmo protocolo + cartório)
    titulos_novos = [
        t for t in relatorio.titulos
        if (t.protocolo, t.cartorio) not in chaves_existentes
    ]
    titulos_duplicados = len(relatorio.titulos) - len(titulos_novos)

    # Se TUDO já existe, nem cria upload novo
    if not titulos_novos:
        return {
            "upload_id": None,
            "clientes_criados": 0,
            "clientes_atualizados": 0,
            "titulos_inseridos": 0,
            "titulos_duplicados": titulos_duplicados,
            "clientes_protestados": 0,
            "clientes_pagos": 0,
            "tudo_duplicado": True,
        }

    # 1) Insere o cabeçalho upload_cartorio
    cur = conn.execute(
        "INSERT INTO upload_cartorio "
        "(nome_arquivo, total_linhas, total_clientes, total_cancelados, usuario_id) "
        "VALUES (?, ?, ?, ?, ?);",
        (nome_arquivo, len(titulos_novos),
         len({t.devedor_nome.upper() for t in titulos_novos}),
         sum(1 for t in titulos_novos if t.cancelado),
         usuario_id)
    )
    upload_id = cur.lastrowid

    # 2) Otimização: pré-carrega clientes existentes em UM query só
    # (em vez de fazer N queries dentro do loop)
    cods_unicos = list({t.cod_parceiro for t in titulos_novos
                        if t.cod_parceiro is not None})
    nomes_unicos = list({t.devedor_nome.upper() for t in titulos_novos
                         if t.devedor_nome})

    clientes_existentes_por_cod: dict[int, int] = {}
    clientes_existentes_por_nome: dict[str, int] = {}

    if cods_unicos:
        placeholders = ",".join("?" * len(cods_unicos))
        rows = conn.execute(
            f"SELECT id, cod_parceiro FROM cliente_protesto "
            f"WHERE cod_parceiro IN ({placeholders});",
            tuple(cods_unicos)
        ).fetchall()
        for r in rows:
            clientes_existentes_por_cod[r["cod_parceiro"]] = r["id"]

    if nomes_unicos:
        # Postgres não suporta LOWER(?) com IN; fazemos em lotes
        # ou um query com OR. Vamos usar UPPER pra padronizar (caso o índice ajude).
        # SQL portátil: WHERE UPPER(nome) IN (...)
        placeholders = ",".join("?" * len(nomes_unicos))
        rows = conn.execute(
            f"SELECT id, UPPER(nome) as nome_up FROM cliente_protesto "
            f"WHERE UPPER(nome) IN ({placeholders});",
            tuple(nomes_unicos)
        ).fetchall()
        for r in rows:
            clientes_existentes_por_nome[r["nome_up"]] = r["id"]

    # 3) Pra cada título, faz upsert do cliente e grava
    clientes_criados = 0
    clientes_atualizados = 0
    clientes_vistos: dict[int, dict] = {}  # cliente_id -> {tem_cancelado, tem_ativo}

    for t in titulos_novos:
        # Verifica se cliente existia (usando os mapas pré-carregados)
        existia = (
            (t.cod_parceiro is not None and t.cod_parceiro in clientes_existentes_por_cod)
            or (t.devedor_nome.upper() in clientes_existentes_por_nome)
        )

        cliente_id = repo_cliente.upsert_cliente(
            nome=t.devedor_nome,
            cod_parceiro=t.cod_parceiro,
            cnpj_cpf=t.devedor_documento,
        )

        # Adiciona aos mapas pra evitar duplicação no mesmo upload
        if t.cod_parceiro is not None:
            clientes_existentes_por_cod[t.cod_parceiro] = cliente_id
        clientes_existentes_por_nome[t.devedor_nome.upper()] = cliente_id

        if existia:
            clientes_atualizados += 1
        else:
            clientes_criados += 1

        # Insere título cartório
        conn.execute(
            "INSERT INTO titulo_cartorio "
            "(upload_id, cliente_id, devedor_nome, devedor_documento, "
            "cod_parceiro, cartorio, municipio, uf, protocolo, nro_titulo, "
            "valor, saldo, data_protesto, data_vencimento, data_emissao, "
            "cancelado, data_cancelamento) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                upload_id, cliente_id, t.devedor_nome, t.devedor_documento,
                t.cod_parceiro, t.cartorio, t.municipio, t.uf,
                t.protocolo, t.nro_titulo,
                t.valor, t.saldo,
                t.data_protesto.isoformat() if t.data_protesto else None,
                t.data_vencimento.isoformat() if t.data_vencimento else None,
                t.data_emissao.isoformat() if t.data_emissao else None,
                1 if t.cancelado else 0,
                t.data_cancelamento.isoformat() if t.data_cancelamento else None,
            )
        )

        # Acumula situação dos títulos por cliente
        info = clientes_vistos.setdefault(cliente_id, {
            "tem_cancelado": False,
            "tem_ativo": False,
        })
        if t.cancelado:
            info["tem_cancelado"] = True
        else:
            info["tem_ativo"] = True

    # 3) Define status_protesto de cada cliente baseado nos títulos:
    #    - Todos os títulos cancelados → PAGO + arquivado (sem baixa)
    #    - Algum título ativo → PROTESTADO
    clientes_protestados = 0
    clientes_pagos = 0

    for cliente_id, info in clientes_vistos.items():
        if info["tem_ativo"]:
            repo_cliente.atualizar_status_protesto(cliente_id, "PROTESTADO")
            # Garante que não está arquivado (pode estar protestado de novo)
            conn.execute(
                "UPDATE cliente_protesto SET arquivado = 0, "
                "atualizado_em = datetime('now') WHERE id = ?;",
                (cliente_id,)
            )
            clientes_protestados += 1
        else:
            # Só tem cancelados → cliente pagou tudo
            repo_cliente.atualizar_status_protesto(cliente_id, "PAGO")
            conn.execute(
                "UPDATE cliente_protesto SET arquivado = 1, baixado = 0, "
                "atualizado_em = datetime('now') WHERE id = ?;",
                (cliente_id,)
            )
            clientes_pagos += 1

    # 4) Auto-atender solicitações pendentes pros cods que apareceram
    from src.servicos.solicitacoes import auto_atender_por_cods_parceiro
    cods_titulo = list({t.cod_parceiro for t in titulos_novos
                        if t.cod_parceiro is not None})
    auto_atendidas = auto_atender_por_cods_parceiro(cods_titulo, usuario_id)

    return {
        "upload_id": upload_id,
        "clientes_criados": clientes_criados,
        "clientes_atualizados": clientes_atualizados,
        "titulos_inseridos": len(titulos_novos),
        "titulos_duplicados": titulos_duplicados,
        "clientes_protestados": clientes_protestados,
        "clientes_pagos": clientes_pagos,
        "solicitacoes_auto_atendidas": auto_atendidas,
        "tudo_duplicado": False,
    }


def excluir_upload_cartorio(upload_id: int) -> dict:
    """
    Apaga um upload e seus títulos.
    Recalcula status dos clientes afetados.
    """
    conn = obter_conexao()

    # Coleta clientes afetados
    cliente_ids = [
        r["cliente_id"] for r in conn.execute(
            "SELECT DISTINCT cliente_id FROM titulo_cartorio WHERE upload_id = ?;",
            (upload_id,)
        ).fetchall()
    ]
    n_titulos = conn.execute(
        "SELECT COUNT(*) FROM titulo_cartorio WHERE upload_id = ?;",
        (upload_id,)
    ).fetchone()[0]

    # Apaga
    conn.execute("DELETE FROM titulo_cartorio WHERE upload_id = ?;", (upload_id,))
    conn.execute("DELETE FROM upload_cartorio WHERE id = ?;", (upload_id,))

    # Recalcula status dos clientes
    for cid in cliente_ids:
        # Quantos títulos ainda existem desse cliente (de outros uploads)?
        cur = conn.execute(
            "SELECT COUNT(*) FROM titulo_cartorio "
            "WHERE cliente_id = ? AND cancelado = 0;",
            (cid,)
        )
        ativos = cur.fetchone()[0]

        cur = conn.execute(
            "SELECT COUNT(*) FROM titulo_cartorio WHERE cliente_id = ?;",
            (cid,)
        )
        total = cur.fetchone()[0]

        if total == 0:
            # Não há mais títulos do cartório pra esse cliente
            conn.execute(
                "UPDATE andamento_protesto SET status_protesto = 'NAO_PROTESTADO', "
                "atualizado_em = datetime('now') WHERE cliente_id = ?;",
                (cid,)
            )
            conn.execute(
                "UPDATE cliente_protesto SET arquivado = 0, "
                "atualizado_em = datetime('now') WHERE id = ?;",
                (cid,)
            )
        elif ativos > 0:
            conn.execute(
                "UPDATE andamento_protesto SET status_protesto = 'PROTESTADO', "
                "atualizado_em = datetime('now') WHERE cliente_id = ?;",
                (cid,)
            )
            conn.execute(
                "UPDATE cliente_protesto SET arquivado = 0, "
                "atualizado_em = datetime('now') WHERE id = ?;",
                (cid,)
            )
        else:
            # Só restaram cancelados → PAGO
            conn.execute(
                "UPDATE andamento_protesto SET status_protesto = 'PAGO', "
                "atualizado_em = datetime('now') WHERE cliente_id = ?;",
                (cid,)
            )
            conn.execute(
                "UPDATE cliente_protesto SET arquivado = 1, baixado = 0, "
                "atualizado_em = datetime('now') WHERE id = ?;",
                (cid,)
            )

    return {
        "clientes_afetados": len(cliente_ids),
        "titulos_removidos": n_titulos,
    }
