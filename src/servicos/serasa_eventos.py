"""
Serviço: operações sobre eventos Serasa.

Exclusão de evento desfaz status do cliente (volta pra NAO_ENVIADO se não
houver outros eventos).
"""
from __future__ import annotations

from src.banco.conexao import obter_conexao


def excluir_evento_serasa(evento_id: int) -> dict:
    """
    Exclui um evento Serasa e seus títulos vinculados.
    
    Reverte o status_serasa dos clientes afetados:
    - Se o cliente NÃO tem mais nenhum outro evento Serasa → NAO_ENVIADO
    - Se tem outros eventos → mantém o status mais recente (último evento)
    
    Retorna dict com estatísticas: {clientes_afetados, titulos_removidos}
    """
    conn = obter_conexao()

    # 1) Coletar clientes afetados (que tinham títulos nesse evento)
    cur = conn.execute(
        "SELECT DISTINCT cliente_id FROM titulo_serasa "
        "WHERE evento_id = ? AND cliente_id IS NOT NULL;",
        (evento_id,)
    )
    cliente_ids = [r["cliente_id"] for r in cur.fetchall()]

    # 2) Contar títulos a remover
    n_titulos = conn.execute(
        "SELECT COUNT(*) FROM titulo_serasa WHERE evento_id = ?;",
        (evento_id,)
    ).fetchone()[0]

    # 3) Remover títulos e evento
    conn.execute("DELETE FROM titulo_serasa WHERE evento_id = ?;", (evento_id,))
    conn.execute("DELETE FROM evento_serasa WHERE id = ?;", (evento_id,))

    # 4) Atualizar status dos clientes afetados
    for cid in cliente_ids:
        # Procura último evento restante desse cliente
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
        else:
            novo_status = "NAO_ENVIADO"

        conn.execute(
            "UPDATE andamento_protesto SET status_serasa = ?, "
            "atualizado_em = datetime('now') WHERE cliente_id = ?;",
            (novo_status, cid)
        )

    return {
        "clientes_afetados": len(cliente_ids),
        "titulos_removidos": n_titulos,
    }
