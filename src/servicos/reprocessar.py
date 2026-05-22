"""
Serviço: reprocessar eventos Serasa antigos.

Pega TODOS os títulos já registrados na tabela titulo_serasa que NÃO têm
cliente_id (foram carregados pela versão antiga sem persistência) e cria
os cadastros faltantes.
"""
from __future__ import annotations

from src.banco.conexao import obter_conexao
from src.banco import repo_cliente


def reprocessar_eventos_serasa() -> dict:
    """
    Cria cadastros de clientes a partir dos títulos Serasa que não estão
    vinculados a cliente algum.
    
    Retorna estatísticas.
    """
    conn = obter_conexao()

    # 1) Pegar todos os títulos sem cliente_id
    cur = conn.execute(
        "SELECT id, evento_id, cnpj_cpf, nome FROM titulo_serasa "
        "WHERE cliente_id IS NULL AND nome IS NOT NULL AND nome != '';"
    )
    titulos_orfaos = cur.fetchall()

    if not titulos_orfaos:
        return {"titulos_processados": 0, "clientes_criados": 0,
                "clientes_atualizados": 0, "status_atualizados": 0}

    clientes_criados = 0
    clientes_atualizados = 0
    status_atualizados = 0

    # 2) Pra cada título, faz o upsert
    for t in titulos_orfaos:
        nome = t["nome"]
        cnpj = (t["cnpj_cpf"] or "").strip() or None

        # Verifica se cliente já existia
        existia = conn.execute(
            "SELECT 1 FROM cliente_protesto WHERE LOWER(nome) = LOWER(?) LIMIT 1;",
            (nome,)
        ).fetchone() is not None

        cliente_id = repo_cliente.upsert_cliente(nome=nome, cnpj_cpf=cnpj)

        if existia:
            clientes_atualizados += 1
        else:
            clientes_criados += 1

        # Vincula título ao cliente
        conn.execute(
            "UPDATE titulo_serasa SET cliente_id = ? WHERE id = ?;",
            (cliente_id, t["id"])
        )

    # 3) Atualizar status_serasa de cada cliente baseado no último evento dele
    cur = conn.execute(
        "SELECT DISTINCT cliente_id FROM titulo_serasa WHERE cliente_id IS NOT NULL;"
    )
    cids = [r["cliente_id"] for r in cur.fetchall()]

    for cid in cids:
        cur = conn.execute(
            """
            SELECT e.tipo FROM titulo_serasa t
            JOIN evento_serasa e ON e.id = t.evento_id
            WHERE t.cliente_id = ?
            ORDER BY e.data_arquivo DESC, e.sequencial DESC
            LIMIT 1;
            """,
            (cid,)
        )
        ultimo = cur.fetchone()
        if ultimo:
            novo_status = "ENVIADO" if ultimo["tipo"] == "INCLUSAO" else "EXCLUIDO"
            repo_cliente.atualizar_status_serasa(cid, novo_status)
            status_atualizados += 1

    return {
        "titulos_processados": len(titulos_orfaos),
        "clientes_criados": clientes_criados,
        "clientes_atualizados": clientes_atualizados,
        "status_atualizados": status_atualizados,
    }
