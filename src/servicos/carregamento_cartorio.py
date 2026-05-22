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

    # 1) Insere o cabeçalho upload_cartorio
    cur = conn.execute(
        "INSERT INTO upload_cartorio "
        "(nome_arquivo, total_linhas, total_clientes, total_cancelados, usuario_id) "
        "VALUES (?, ?, ?, ?, ?);",
        (nome_arquivo, relatorio.total_linhas,
         relatorio.total_clientes_unicos, relatorio.total_cancelados,
         usuario_id)
    )
    upload_id = cur.lastrowid

    # 2) Pra cada título, faz upsert do cliente e grava
    clientes_criados = 0
    clientes_atualizados = 0
    clientes_vistos: dict[int, dict] = {}  # cliente_id -> {tem_cancelado, tem_ativo}

    for t in relatorio.titulos:
        # Verifica se cliente existia
        existia_query = conn.execute(
            "SELECT id FROM cliente_protesto WHERE "
            "cod_parceiro = ? OR LOWER(nome) = LOWER(?) LIMIT 1;",
            (t.cod_parceiro, t.devedor_nome)
        ).fetchone()
        existia = existia_query is not None

        cliente_id = repo_cliente.upsert_cliente(
            nome=t.devedor_nome,
            cod_parceiro=t.cod_parceiro,
            cnpj_cpf=t.devedor_documento,
        )

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

    return {
        "upload_id": upload_id,
        "clientes_criados": clientes_criados,
        "clientes_atualizados": clientes_atualizados,
        "titulos_inseridos": len(relatorio.titulos),
        "clientes_protestados": clientes_protestados,
        "clientes_pagos": clientes_pagos,
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
