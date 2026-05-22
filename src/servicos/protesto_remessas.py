"""
Serviço: operações sobre remessas de protesto.
"""
from __future__ import annotations

from src.banco.conexao import obter_conexao


def excluir_remessa_protesto(remessa_id: int) -> dict:
    """
    Exclui uma remessa e seus títulos vinculados.
    
    Reverte o status_protesto dos clientes afetados:
    - Se não há outras remessas com títulos desse cliente → NAO_PROTESTADO
    - Senão mantém PROTESTADO
    
    Retorna: {clientes_afetados, titulos_removidos}
    """
    conn = obter_conexao()

    cur = conn.execute(
        "SELECT DISTINCT cliente_id FROM titulo_protesto WHERE remessa_id = ?;",
        (remessa_id,)
    )
    cliente_ids = [r["cliente_id"] for r in cur.fetchall()]

    n_titulos = conn.execute(
        "SELECT COUNT(*) FROM titulo_protesto WHERE remessa_id = ?;",
        (remessa_id,)
    ).fetchone()[0]

    conn.execute("DELETE FROM titulo_protesto WHERE remessa_id = ?;", (remessa_id,))
    conn.execute("DELETE FROM remessa_protesto WHERE id = ?;", (remessa_id,))

    for cid in cliente_ids:
        # Tem outros títulos em outras remessas?
        cur = conn.execute(
            "SELECT COUNT(*) FROM titulo_protesto WHERE cliente_id = ?;",
            (cid,)
        )
        n_restantes = cur.fetchone()[0]

        if n_restantes == 0:
            conn.execute(
                "UPDATE andamento_protesto SET status_protesto = 'NAO_PROTESTADO', "
                "atualizado_em = datetime('now') WHERE cliente_id = ?;",
                (cid,)
            )

    return {
        "clientes_afetados": len(cliente_ids),
        "titulos_removidos": n_titulos,
    }
