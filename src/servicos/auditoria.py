"""
Serviço de auditoria: detecta duplicação e inconsistências no banco.

Usado pelo dashboard pra alertar quando há dados inflados.
"""
from __future__ import annotations

from src.banco.conexao import obter_conexao


def detectar_duplicacao_cartorio() -> dict:
    """
    Detecta protocolos duplicados em titulo_cartorio.
    
    Retorna:
    {
        "tem_duplicacao": bool,
        "protocolos_duplicados": int,
        "titulos_excedentes": int,
        "valor_inflado": float,
    }
    """
    conn = obter_conexao()

    try:
        # Quantos protocolos têm mais de 1 ocorrência?
        rows = conn.execute(
            "SELECT protocolo, cartorio, COUNT(*) as n "
            "FROM titulo_cartorio "
            "WHERE protocolo IS NOT NULL AND protocolo != '' "
            "GROUP BY protocolo, cartorio "
            "HAVING COUNT(*) > 1;"
        ).fetchall()

        if not rows:
            return {
                "tem_duplicacao": False,
                "protocolos_duplicados": 0,
                "titulos_excedentes": 0,
                "valor_inflado": 0.0,
            }

        protocolos_duplicados = len(rows)
        titulos_excedentes = sum(r["n"] - 1 for r in rows)

        # Valor inflado = soma dos valores das linhas que excedem (todas menos a primeira)
        valor_inflado = conn.execute(
            "SELECT COALESCE(SUM(valor), 0) "
            "FROM titulo_cartorio "
            "WHERE id NOT IN ("
            "  SELECT MIN(id) FROM titulo_cartorio "
            "  WHERE protocolo IS NOT NULL AND protocolo != '' "
            "  GROUP BY protocolo, cartorio"
            ") AND cancelado = 0;"
        ).fetchone()[0]

        return {
            "tem_duplicacao": True,
            "protocolos_duplicados": protocolos_duplicados,
            "titulos_excedentes": titulos_excedentes,
            "valor_inflado": float(valor_inflado),
        }
    except Exception:
        return {
            "tem_duplicacao": False,
            "protocolos_duplicados": 0,
            "titulos_excedentes": 0,
            "valor_inflado": 0.0,
        }


def limpar_duplicacao_cartorio() -> dict:
    """
    Remove duplicatas de titulo_cartorio mantendo apenas uma cópia
    (a de menor id) de cada combinação (protocolo, cartorio).
    
    Retorna estatísticas da limpeza.
    """
    conn = obter_conexao()

    antes = conn.execute("SELECT COUNT(*) FROM titulo_cartorio;").fetchone()[0]

    conn.execute(
        "DELETE FROM titulo_cartorio "
        "WHERE id NOT IN ("
        "  SELECT MIN(id) FROM titulo_cartorio "
        "  GROUP BY protocolo, cartorio"
        ");"
    )

    depois = conn.execute("SELECT COUNT(*) FROM titulo_cartorio;").fetchone()[0]
    removidos = antes - depois

    return {
        "titulos_antes": antes,
        "titulos_depois": depois,
        "titulos_removidos": removidos,
    }


# ============================================================
# AUDITORIA DO SERASA — Detecta duplicação em titulo_serasa
# ============================================================

def detectar_duplicacao_serasa() -> dict:
    """
    Detecta duplicações REAIS em titulo_serasa.
    
    IMPORTANTE: o Serasa permite que o mesmo cliente entre, saia, entre de novo.
    Então NÃO é duplicação quando:
      - Cliente X tem nro_unico repetido em INCLUSOES de eventos diferentes (datas diferentes)
      - Cliente Y tem vários títulos no mesmo arquivo (cada um com nro_unico diferente)
    
    É duplicação SÓ quando:
      1. O MESMO título aparece DUAS VEZES dentro do MESMO evento
      2. O MESMO arquivo (mesmo nome) foi carregado 2 vezes
    """
    conn = obter_conexao()
    resultado = {
        "tem_duplicacao": False,
        "tipo_1_intra_evento": 0,       # mesmo título 2x dentro de 1 evento
        "tipo_3_nomes_repetidos": 0,    # mesmo nome_arquivo carregado N vezes
        "titulos_excedentes": 0,
        "valor_inflado": 0.0,
    }

    try:
        # Tipo 1: títulos duplicados DENTRO do mesmo evento
        # (esse é problema REAL — o mesmo arquivo não deveria inserir 2x o mesmo título)
        rows = conn.execute(
            "SELECT evento_id, nro_unico_serasa, COUNT(*) as n "
            "FROM titulo_serasa "
            "WHERE nro_unico_serasa IS NOT NULL "
            "  AND nro_unico_serasa != '' "
            "GROUP BY evento_id, nro_unico_serasa "
            "HAVING COUNT(*) > 1;"
        ).fetchall()
        if rows:
            resultado["tipo_1_intra_evento"] = sum(r["n"] - 1 for r in rows)

        # Tipo 3: nome_arquivo carregado mais de 1 vez
        # (mesmo arquivo de remessa foi processado 2x — duplicação real)
        rows = conn.execute(
            "SELECT nome_arquivo, COUNT(*) as n "
            "FROM evento_serasa "
            "WHERE nome_arquivo IS NOT NULL AND nome_arquivo != '' "
            "GROUP BY nome_arquivo "
            "HAVING COUNT(*) > 1;"
        ).fetchall()
        if rows:
            resultado["tipo_3_nomes_repetidos"] = sum(r["n"] - 1 for r in rows)

        # Total de títulos excedentes a remover (só os intra-evento)
        resultado["titulos_excedentes"] = resultado["tipo_1_intra_evento"]

        # Valor inflado (apenas títulos com nro_unico repetido DENTRO do mesmo evento)
        valor_row = conn.execute(
            "SELECT COALESCE(SUM(valor), 0) "
            "FROM titulo_serasa "
            "WHERE id NOT IN ("
            "  SELECT MIN(id) FROM titulo_serasa "
            "  WHERE nro_unico_serasa IS NOT NULL "
            "    AND nro_unico_serasa != '' "
            "  GROUP BY evento_id, nro_unico_serasa"
            ") "
            "AND nro_unico_serasa IS NOT NULL "
            "AND nro_unico_serasa != '';"
        ).fetchone()
        resultado["valor_inflado"] = float(valor_row[0]) if valor_row[0] else 0.0

        resultado["tem_duplicacao"] = (
            resultado["tipo_1_intra_evento"] > 0
            or resultado["tipo_3_nomes_repetidos"] > 0
        )

    except Exception:
        pass

    return resultado


def limpar_duplicacao_serasa() -> dict:
    """
    Remove duplicatas de titulo_serasa em 2 níveis:
    
    1. Títulos duplicados dentro do MESMO evento → mantém menor id
    2. Eventos com mesmo nome_arquivo → mantém o mais antigo, deleta os outros
       (e seus títulos cascateiam)
    
    Retorna estatísticas da limpeza.
    """
    conn = obter_conexao()

    titulos_antes = conn.execute("SELECT COUNT(*) FROM titulo_serasa;").fetchone()[0]
    eventos_antes = conn.execute("SELECT COUNT(*) FROM evento_serasa;").fetchone()[0]

    # 1) Remove títulos duplicados dentro do mesmo evento
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

    # 2) Remove eventos com mesmo nome_arquivo (mantém o mais antigo)
    # Pega ids a deletar
    try:
        rows = conn.execute(
            "SELECT id FROM evento_serasa "
            "WHERE id NOT IN ("
            "  SELECT MIN(id) FROM evento_serasa "
            "  WHERE nome_arquivo IS NOT NULL AND nome_arquivo != '' "
            "  GROUP BY nome_arquivo"
            ") "
            "AND nome_arquivo IS NOT NULL "
            "AND nome_arquivo != '';"
        ).fetchall()
        ids_a_apagar = [r["id"] for r in rows]

        if ids_a_apagar:
            placeholders = ",".join("?" * len(ids_a_apagar))
            # Deleta os títulos órfãos primeiro (não tem FK ON DELETE CASCADE no SQLite por padrão)
            conn.execute(
                f"DELETE FROM titulo_serasa WHERE evento_id IN ({placeholders});",
                tuple(ids_a_apagar)
            )
            # Agora deleta os eventos duplicados
            conn.execute(
                f"DELETE FROM evento_serasa WHERE id IN ({placeholders});",
                tuple(ids_a_apagar)
            )
    except Exception:
        pass

    titulos_depois = conn.execute("SELECT COUNT(*) FROM titulo_serasa;").fetchone()[0]
    eventos_depois = conn.execute("SELECT COUNT(*) FROM evento_serasa;").fetchone()[0]

    # Recalcula status dos clientes afetados (importante depois da limpeza)
    try:
        from src.banco import repo_cliente
        cids = [
            r["id"] for r in conn.execute(
                "SELECT DISTINCT cliente_id FROM titulo_serasa WHERE cliente_id IS NOT NULL;"
            ).fetchall()
        ]
        for cid in cids:
            try:
                repo_cliente.recalcular_status_serasa(cid)
            except Exception:
                pass
    except Exception:
        pass

    return {
        "titulos_antes": titulos_antes,
        "titulos_depois": titulos_depois,
        "titulos_removidos": titulos_antes - titulos_depois,
        "eventos_antes": eventos_antes,
        "eventos_depois": eventos_depois,
        "eventos_removidos": eventos_antes - eventos_depois,
    }
