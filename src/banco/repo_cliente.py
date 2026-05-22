"""
Repositório de clientes do Protesto.

Implementa upsert por NOME (regra de cruzamento decidida):
- Se cliente não existe → cria
- Se existe → atualiza só os campos que chegaram preenchidos
  (não sobrescreve com NULL/vazio dados que já existem)
"""
from __future__ import annotations

from src.banco.conexao import obter_conexao


def upsert_cliente(
    nome: str,
    cod_parceiro: int | None = None,
    cnpj_cpf: str | None = None,
) -> int:
    """
    Cria ou atualiza cliente por NOME.

    Retorna o id do cliente.

    Regra de merge:
    - Se cliente não existe → cria com os dados fornecidos
    - Se existe:
      - cod_parceiro: atualiza se chegou um e ainda não tinha
      - cnpj_cpf: atualiza se chegou um e ainda não tinha
      - nome: nunca muda (é a chave)
    """
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Nome do cliente é obrigatório.")

    cnpj_cpf = (cnpj_cpf or "").strip() or None

    conn = obter_conexao()

    # Estratégia de busca:
    # 1) Se temos cod_parceiro, busca por ele primeiro (chave mais segura)
    # 2) Se não achou, busca por nome (case-insensitive)
    row = None
    if cod_parceiro is not None:
        row = conn.execute(
            "SELECT id, cod_parceiro, cnpj_cpf, nome FROM cliente_protesto "
            "WHERE cod_parceiro = ? LIMIT 1;",
            (cod_parceiro,)
        ).fetchone()

    if row is None:
        row = conn.execute(
            "SELECT id, cod_parceiro, cnpj_cpf, nome FROM cliente_protesto "
            "WHERE LOWER(nome) = LOWER(?) LIMIT 1;",
            (nome,)
        ).fetchone()

    if row is None:
        # Cria novo
        cur = conn.execute(
            "INSERT INTO cliente_protesto (nome, cod_parceiro, cnpj_cpf) "
            "VALUES (?, ?, ?);",
            (nome, cod_parceiro, cnpj_cpf)
        )
        cliente_id = cur.lastrowid

        # Cria andamento default
        conn.execute(
            "INSERT INTO andamento_protesto (cliente_id) VALUES (?);",
            (cliente_id,)
        )

        return cliente_id

    # Já existe — merge
    cliente_id = row["id"]
    updates = []
    params = []

    if cod_parceiro is not None and not row["cod_parceiro"]:
        updates.append("cod_parceiro = ?")
        params.append(cod_parceiro)

    if cnpj_cpf and not row["cnpj_cpf"]:
        updates.append("cnpj_cpf = ?")
        params.append(cnpj_cpf)

    if updates:
        updates.append("atualizado_em = datetime('now')")
        params.append(cliente_id)
        conn.execute(
            f"UPDATE cliente_protesto SET {', '.join(updates)} WHERE id = ?;",
            tuple(params)
        )

    return cliente_id


def atualizar_status_serasa(cliente_id: int, status: str) -> None:
    """
    Atualiza status Serasa do cliente. Cria andamento se não existe.
    
    NOTA: essa função aplica o status passado diretamente. Use
    `recalcular_status_serasa` se quiser que o sistema descubra o status
    correto baseado no evento Serasa mais recente do cliente.
    """
    conn = obter_conexao()
    cur = conn.execute(
        "UPDATE andamento_protesto SET status_serasa = ?, "
        "atualizado_em = datetime('now') WHERE cliente_id = ?;",
        (status, cliente_id)
    )
    if cur.rowcount == 0:
        conn.execute(
            "INSERT INTO andamento_protesto (cliente_id, status_serasa) "
            "VALUES (?, ?);",
            (cliente_id, status)
        )


def recalcular_status_serasa(cliente_id: int) -> str:
    """
    Olha TODOS os eventos Serasa do cliente, pega o mais recente
    (por data_arquivo, com desempate por sequencial), e define o status
    do cliente baseado no tipo desse evento.
    
    Retorna o status definido. Se cliente não tem eventos, status = NAO_ENVIADO.
    """
    conn = obter_conexao()
    row = conn.execute(
        """
        SELECT e.tipo FROM titulo_serasa t
        JOIN evento_serasa e ON e.id = t.evento_id
        WHERE t.cliente_id = ?
        ORDER BY e.data_arquivo DESC, e.sequencial DESC
        LIMIT 1;
        """,
        (cliente_id,)
    ).fetchone()

    if row is None:
        novo_status = "NAO_ENVIADO"
    else:
        novo_status = "ENVIADO" if row["tipo"] == "INCLUSAO" else "EXCLUIDO"

    atualizar_status_serasa(cliente_id, novo_status)
    return novo_status


def atualizar_status_protesto(cliente_id: int, status: str) -> None:
    """Atualiza status Protesto do cliente. Cria andamento se não existe."""
    conn = obter_conexao()
    cur = conn.execute(
        "UPDATE andamento_protesto SET status_protesto = ?, "
        "atualizado_em = datetime('now') WHERE cliente_id = ?;",
        (status, cliente_id)
    )
    if cur.rowcount == 0:
        conn.execute(
            "INSERT INTO andamento_protesto (cliente_id, status_protesto) "
            "VALUES (?, ?);",
            (cliente_id, status)
        )


def arquivar_cliente(cliente_id: int) -> None:
    """Marca cliente como arquivado (pago)."""
    conn = obter_conexao()
    conn.execute(
        "UPDATE cliente_protesto SET arquivado = 1, "
        "atualizado_em = datetime('now') WHERE id = ?;",
        (cliente_id,)
    )
