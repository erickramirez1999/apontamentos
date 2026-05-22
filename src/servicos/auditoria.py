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
