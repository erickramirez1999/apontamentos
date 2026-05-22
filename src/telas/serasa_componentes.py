"""
Componente reutilizável: listagem de eventos Serasa (Inclusões ou Exclusões).

Usado por src/telas/serasa_inclusos.py e serasa_exclusos.py.
Evita duplicação de código.
"""
from __future__ import annotations

import streamlit as st

from src.banco.conexao import obter_conexao
from src.utils.marca import AZUL_ESCURO
from src.utils.estilo import card_kpi
from src.utils.permissoes import pode_editar
from src.utils.exclusao_com_senha import confirmar_exclusao_com_senha
from src.servicos.serasa_eventos import excluir_evento_serasa


def listar_eventos_serasa(tipo: str, usuario, cor: str, icone: str,
                          chave_prefix: str):
    """
    Renderiza listagem de eventos Serasa por tipo (INCLUSAO ou EXCLUSAO).

    Args:
        tipo: 'INCLUSAO' ou 'EXCLUSAO'
        usuario: usuário logado
        cor: cor dos KPIs (COR_AZUL / COR_VERDE)
        icone: emoji do KPI
        chave_prefix: prefixo das chaves de session_state pra exclusão
    """
    conn = obter_conexao()

    try:
        eventos = conn.execute(
            "SELECT id, data_arquivo, sequencial, nome_arquivo, "
            "total_clientes, criado_em "
            "FROM evento_serasa WHERE tipo = ? "
            "ORDER BY data_arquivo DESC, sequencial DESC;",
            (tipo,)
        ).fetchall()
    except Exception:
        eventos = []

    if not eventos:
        nome_tipo = "inclusão" if tipo == "INCLUSAO" else "exclusão"
        st.info(
            f"📭 **Nenhum arquivo de {nome_tipo} carregado ainda.**\n\n"
            "Vá em **📤 Carregamento** para subir os arquivos do Serasa."
        )
        return

    total_arquivos = len(eventos)
    total_titulos = sum(e["total_clientes"] for e in eventos)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(card_kpi(
            "Arquivos", f"{total_arquivos:,}", "carregados", cor, icone
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(card_kpi(
            "Títulos", f"{total_titulos:,}", "registrados", cor, "📋"
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Pré-carregar TODOS os títulos dos eventos visíveis em UMA query
    # (evita N+1 ao expandir cada arquivo)
    ids_eventos = [e["id"] for e in eventos]
    titulos_por_evento: dict[int, list] = {eid: [] for eid in ids_eventos}
    if ids_eventos:
        placeholders = ",".join("?" * len(ids_eventos))
        rows = conn.execute(
            f"SELECT evento_id, cnpj_cpf, nome FROM titulo_serasa "
            f"WHERE evento_id IN ({placeholders}) ORDER BY nome;",
            tuple(ids_eventos)
        ).fetchall()
        for r in rows:
            titulos_por_evento[r["evento_id"]].append(r)

    by_day: dict = {}
    for e in eventos:
        d = e["data_arquivo"]
        by_day.setdefault(d, []).append(e)

    permite_excluir = pode_editar(usuario)
    nome_singular = "Inclusão" if tipo == "INCLUSAO" else "Exclusão"

    for dia in sorted(by_day.keys(), reverse=True):
        # Postgres pode retornar como date object, SQLite como string
        dia_str = str(dia)
        st.markdown(
            f"<h4 style='color:{AZUL_ESCURO}; margin-bottom:6px;'>📆 {dia_str}</h4>",
            unsafe_allow_html=True,
        )
        for e in by_day[dia]:
            with st.expander(
                f"#{e['sequencial']} · {e['total_clientes']} título(s)"
            ):
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    st.write(f"**Arquivo:** `{e['nome_arquivo']}`")
                    st.write(f"**Carregado em:** {e['criado_em']}")
                with col_btn:
                    if permite_excluir:
                        confirmar_exclusao_com_senha(
                            usuario_logado=usuario,
                            chave=f"{chave_prefix}_{e['id']}",
                            descricao_item=f"{nome_singular} #{e['sequencial']}",
                            on_confirmar=lambda eid=e['id']: excluir_evento_serasa(eid),
                        )

                titulos = titulos_por_evento.get(e["id"], [])
                if titulos:
                    st.markdown("**Clientes:**")
                    for t in titulos:
                        cnpj = t["cnpj_cpf"] or "—"
                        st.caption(f"  • {t['nome']} (CNPJ/CPF: {cnpj})")
