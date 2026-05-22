"""
Serviço: solicitações de protesto.

Fluxo:
- Qualquer perfil pode criar solicitação
- Operador/Gestão/Admin pode atender ou recusar
- Quando carregar relatório do cartório, auto-atende solicitações pendentes
  de clientes que aparecerem
- Solicitante recebe notificação visível ao logar
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from src.banco.conexao import obter_conexao


@dataclass
class LinhaSolicitacao:
    """Uma linha do formulário (1 cliente por linha)."""
    cod_parceiro: int
    valor: Optional[float] = None
    nro_nota: Optional[str] = None
    incluir_serasa: bool = False


def criar_solicitacoes(
    linhas: list[LinhaSolicitacao],
    observacao: Optional[str],
    solicitante_id: int,
) -> dict:
    """
    Cria múltiplas solicitações de uma vez (uma por linha do formulário).
    
    Bloqueia se já existir solicitação PENDENTE para o mesmo cod_parceiro
    (independente do solicitante).
    
    Retorna: {criadas, duplicadas, erros}
    """
    conn = obter_conexao()
    criadas = 0
    duplicadas = []  # lista de cod_parceiro que já tinham pendente
    erros = []

    # Pré-carrega cods que já têm solicitação PENDENTE
    cods = list({linha.cod_parceiro for linha in linhas})
    pendentes_existentes: dict[int, str] = {}
    if cods:
        try:
            placeholders = ",".join("?" * len(cods))
            rows = conn.execute(
                f"SELECT s.cod_parceiro, u.nome as solicitante_nome "
                f"FROM solicitacao_protesto s "
                f"LEFT JOIN usuario u ON u.id = s.solicitante_id "
                f"WHERE s.cod_parceiro IN ({placeholders}) "
                f"AND s.status = 'PENDENTE';",
                tuple(cods)
            ).fetchall()
            for r in rows:
                pendentes_existentes[r["cod_parceiro"]] = r["solicitante_nome"]
        except Exception:
            pass

    for i, linha in enumerate(linhas, 1):
        # Bloqueia se já tem pendente desse cod
        if linha.cod_parceiro in pendentes_existentes:
            quem = pendentes_existentes[linha.cod_parceiro]
            duplicadas.append({
                "cod_parceiro": linha.cod_parceiro,
                "solicitante_anterior": quem,
            })
            continue

        try:
            # Tenta achar cliente já cadastrado
            row = conn.execute(
                "SELECT id FROM cliente_protesto WHERE cod_parceiro = ? LIMIT 1;",
                (linha.cod_parceiro,)
            ).fetchone()
            cliente_id = row["id"] if row else None

            conn.execute(
                "INSERT INTO solicitacao_protesto "
                "(cod_parceiro, cliente_id, valor, nro_nota, incluir_serasa, "
                "observacao, solicitante_id, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDENTE');",
                (
                    linha.cod_parceiro, cliente_id, linha.valor,
                    linha.nro_nota, 1 if linha.incluir_serasa else 0,
                    observacao, solicitante_id,
                )
            )
            criadas += 1

            # Marca como pendente pra próximas iterações do mesmo lote
            pendentes_existentes[linha.cod_parceiro] = "você (nessa submissão)"
        except Exception as e:
            erros.append(f"Linha {i} (cód {linha.cod_parceiro}): {e}")

    return {"criadas": criadas, "duplicadas": duplicadas, "erros": erros}


def listar_solicitacoes(
    status: Optional[str] = None,
    solicitante_id: Optional[int] = None,
    limite: Optional[int] = None,
) -> list:
    """
    Lista solicitações. Pode filtrar por status e/ou solicitante.
    Retorna ordenado por criado_em DESC.
    """
    conn = obter_conexao()

    sql = """
        SELECT s.*,
               c.nome as cliente_nome,
               us.nome as solicitante_nome,
               ua.nome as atendido_por_nome
        FROM solicitacao_protesto s
        LEFT JOIN cliente_protesto c ON c.id = s.cliente_id
        LEFT JOIN usuario us ON us.id = s.solicitante_id
        LEFT JOIN usuario ua ON ua.id = s.atendido_por_id
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND s.status = ?"
        params.append(status)
    if solicitante_id:
        sql += " AND s.solicitante_id = ?"
        params.append(solicitante_id)

    sql += " ORDER BY s.criado_em DESC"
    if limite:
        sql += f" LIMIT {int(limite)}"
    sql += ";"

    try:
        return conn.execute(sql, tuple(params)).fetchall()
    except Exception:
        return []


def contar_pendentes() -> int:
    """Quantas solicitações estão pendentes."""
    conn = obter_conexao()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM solicitacao_protesto WHERE status = 'PENDENTE';"
        ).fetchone()[0]
    except Exception:
        return 0


def contar_resolvidas_nao_vistas(solicitante_id: int) -> int:
    """
    Quantas solicitações DESSE solicitante foram resolvidas (atendidas/recusadas)
    e ainda não foram visualizadas por ele.
    """
    conn = obter_conexao()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM solicitacao_protesto "
            "WHERE solicitante_id = ? "
            "AND status IN ('ATENDIDA', 'RECUSADA') "
            "AND visualizada_pelo_solicitante = 0;",
            (solicitante_id,)
        ).fetchone()[0]
    except Exception:
        return 0


def marcar_visualizadas(solicitante_id: int) -> None:
    """Marca todas as resolvidas do solicitante como visualizadas."""
    conn = obter_conexao()
    try:
        conn.execute(
            "UPDATE solicitacao_protesto SET visualizada_pelo_solicitante = 1 "
            "WHERE solicitante_id = ? "
            "AND status IN ('ATENDIDA', 'RECUSADA') "
            "AND visualizada_pelo_solicitante = 0;",
            (solicitante_id,)
        )
    except Exception:
        pass


def atender_solicitacao(
    solicitacao_id: int,
    atendido_por_id: int,
    obs: Optional[str] = None,
    auto: bool = False,
) -> bool:
    """
    Marca solicitação como ATENDIDA.
    Retorna True se sucesso.
    """
    conn = obter_conexao()
    try:
        conn.execute(
            "UPDATE solicitacao_protesto SET "
            "status = 'ATENDIDA', "
            "atendido_por_id = ?, "
            "atendido_em = datetime('now'), "
            "obs_atendimento = ?, "
            "auto_atendida = ?, "
            "visualizada_pelo_solicitante = 0 "
            "WHERE id = ? AND status = 'PENDENTE';",
            (atendido_por_id, obs, 1 if auto else 0, solicitacao_id)
        )
        return True
    except Exception:
        return False


def recusar_solicitacao(
    solicitacao_id: int,
    atendido_por_id: int,
    motivo: str,
) -> bool:
    """Marca solicitação como RECUSADA (com motivo obrigatório)."""
    if not motivo or not motivo.strip():
        return False
    conn = obter_conexao()
    try:
        conn.execute(
            "UPDATE solicitacao_protesto SET "
            "status = 'RECUSADA', "
            "atendido_por_id = ?, "
            "atendido_em = datetime('now'), "
            "motivo_recusa = ?, "
            "visualizada_pelo_solicitante = 0 "
            "WHERE id = ? AND status = 'PENDENTE';",
            (atendido_por_id, motivo.strip(), solicitacao_id)
        )
        return True
    except Exception:
        return False


def excluir_solicitacao(solicitacao_id: int, usuario_id: int, eh_admin: bool) -> bool:
    """
    Exclui solicitação. Só o próprio solicitante (se pendente) ou ADMIN.
    """
    conn = obter_conexao()
    try:
        row = conn.execute(
            "SELECT solicitante_id, status FROM solicitacao_protesto WHERE id = ?;",
            (solicitacao_id,)
        ).fetchone()
        if not row:
            return False

        # Regras de permissão
        if eh_admin:
            pode = True
        elif row["solicitante_id"] == usuario_id and row["status"] == "PENDENTE":
            pode = True
        else:
            pode = False

        if not pode:
            return False

        conn.execute(
            "DELETE FROM solicitacao_protesto WHERE id = ?;",
            (solicitacao_id,)
        )
        return True
    except Exception:
        return False


def auto_atender_por_cods_parceiro(
    cods_parceiro: list[int],
    sistema_user_id: int,
) -> int:
    """
    Auto-atende todas as solicitações PENDENTES dos clientes cujos
    cod_parceiro estão na lista (chamado após carregamento do cartório).
    
    Retorna quantas foram auto-atendidas.
    """
    if not cods_parceiro:
        return 0

    conn = obter_conexao()
    try:
        placeholders = ",".join("?" * len(cods_parceiro))
        rows = conn.execute(
            f"SELECT id FROM solicitacao_protesto "
            f"WHERE cod_parceiro IN ({placeholders}) "
            f"AND status = 'PENDENTE';",
            tuple(cods_parceiro)
        ).fetchall()

        if not rows:
            return 0

        ids = [r["id"] for r in rows]
        ids_ph = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE solicitacao_protesto SET "
            f"status = 'ATENDIDA', "
            f"atendido_por_id = ?, "
            f"atendido_em = datetime('now'), "
            f"obs_atendimento = 'Auto-atendida: cliente apareceu no cartório.', "
            f"auto_atendida = 1, "
            f"visualizada_pelo_solicitante = 0 "
            f"WHERE id IN ({ids_ph}) AND status = 'PENDENTE';",
            (sistema_user_id, *ids)
        )
        return len(ids)
    except Exception:
        return 0
