"""
Tela Clientes — lista única consolidada.

Junta clientes em protesto, em acordo, pagos e arquivados.
Mostra status consolidado (Protesto + Serasa) com badges visuais.
"""
from __future__ import annotations

import streamlit as st

from src.banco.conexao import obter_conexao
from src.utils.marca import AZUL_ESCURO
from src.utils.estilo import (
    card_kpi, COR_AZUL, COR_VERDE, COR_LARANJA, COR_VERMELHO, COR_CINZA, COR_AMARELO
)
from src.utils.traducoes import traduzir_status_protesto, traduzir_status_serasa


# Mapeamento de status pra cor do badge
_COR_STATUS_P = {
    "PROTESTADO": COR_VERMELHO,
    "ACORDO": COR_AMARELO,
    "PAGO": COR_VERDE,
    "NAO_PROTESTADO": COR_CINZA,
}
_COR_STATUS_S = {
    "ENVIADO": COR_VERMELHO,
    "EXCLUIDO": COR_VERDE,
    "NAO_ENVIADO": COR_CINZA,
}


def renderizar(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO};margin-bottom:4px;'>👥 Clientes</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Lista única de todos os clientes do sistema (Protesto + Serasa).")

    conn = obter_conexao()

    # ─── Filtros ─────────────────────────
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        busca = st.text_input(
            "🔍 Buscar por nome ou código:",
            "",
            placeholder="Digite para filtrar...",
        )
    with col_f2:
        filtro_p = st.selectbox(
            "Status Protesto",
            ["(todos)", "Protestado", "Em acordo", "Pago", "Não protestado"],
        )
    with col_f3:
        filtro_s = st.selectbox(
            "Status Serasa",
            ["(todos)", "Enviado", "Excluído", "Não enviado"],
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Buscar dados ─────────────────────────
    try:
        rows = conn.execute(
            """
            SELECT
                c.id, c.cod_parceiro, c.nome, c.cnpj_cpf,
                c.arquivado, c.baixado,
                COALESCE(a.status_protesto, 'NAO_PROTESTADO') AS status_p,
                COALESCE(a.status_serasa, 'NAO_ENVIADO') AS status_s,
                c.atualizado_em
            FROM cliente_protesto c
            LEFT JOIN andamento_protesto a ON a.cliente_id = c.id
            ORDER BY c.nome;
            """
        ).fetchall()
    except Exception as e:
        st.error(f"❌ Erro ao buscar clientes: {e}")
        st.exception(e)
        rows = []

    # Aplicar filtros em Python
    def passa(r):
        if busca:
            termo = busca.lower()
            if (termo not in r["nome"].lower()
                    and termo not in str(r["cod_parceiro"])):
                return False
        if filtro_p != "(todos)":
            mapa = {"Protestado": "PROTESTADO", "Em acordo": "ACORDO",
                    "Pago": "PAGO", "Não protestado": "NAO_PROTESTADO"}
            if r["status_p"] != mapa.get(filtro_p):
                return False
        if filtro_s != "(todos)":
            mapa = {"Enviado": "ENVIADO", "Excluído": "EXCLUIDO",
                    "Não enviado": "NAO_ENVIADO"}
            if r["status_s"] != mapa.get(filtro_s):
                return False
        return True

    rows_filtradas = [r for r in rows if passa(r)]

    # ─── Estado vazio ─────────────────────────
    if not rows:
        st.info(
            "📭 **Ainda não há clientes cadastrados.**\n\n"
            "Os clientes aparecem aqui automaticamente quando você gera "
            "um protesto na tela **📤 Protestar** (Passo 3)."
        )
        return

    if not rows_filtradas:
        st.warning("Nenhum cliente encontrado com esses filtros.")
        return

    # ─── KPIs do recorte ─────────────────────────
    total = len(rows_filtradas)
    em_prot = sum(1 for r in rows_filtradas if r["status_p"] == "PROTESTADO")
    em_acordo = sum(1 for r in rows_filtradas if r["status_p"] == "ACORDO")
    pagos = sum(1 for r in rows_filtradas if r["arquivado"])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(card_kpi(
            "Total", f"{total:,}", "clientes encontrados", COR_AZUL, "👥"
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(card_kpi(
            "Em Protesto", f"{em_prot:,}", "ativos", COR_VERMELHO, "📤"
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(card_kpi(
            "Em Acordo", f"{em_acordo:,}", "negociando", COR_AMARELO, "🤝"
        ), unsafe_allow_html=True)
    with c4:
        st.markdown(card_kpi(
            "Pagos / Arquivados", f"{pagos:,}", "quitados", COR_VERDE, "✅"
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Lista de clientes ─────────────────────────
    st.markdown(
        f"<h3 style='color:{AZUL_ESCURO}; margin-bottom:8px;'>"
        f"📋 {total} cliente(s)</h3>",
        unsafe_allow_html=True,
    )

    for r in rows_filtradas:
        _render_linha_cliente(r)


def _render_linha_cliente(r):
    """Renderiza uma linha de cliente com badges de status."""
    cor_p = _COR_STATUS_P.get(r["status_p"], COR_CINZA)
    cor_s = _COR_STATUS_S.get(r["status_s"], COR_CINZA)

    txt_p = traduzir_status_protesto(r["status_p"])
    txt_s = traduzir_status_serasa(r["status_s"])

    arquivado_badge = ""
    if r["arquivado"]:
        baixado = "BAIXADO" if r["baixado"] else "NÃO BAIXADO"
        cor_baixa = COR_VERDE if r["baixado"] else COR_LARANJA
        arquivado_badge = (
            f"<span style='background:{cor_baixa}; color:white; "
            f"padding:2px 8px; border-radius:10px; font-size:10px; "
            f"font-weight:600; margin-left:8px;'>📁 {baixado}</span>"
        )

    cnpj = r["cnpj_cpf"] or "—"

    st.markdown(
        f"<div style='background:#FFF; padding:12px 16px; border-radius:8px; "
        f"box-shadow:0 1px 3px rgba(0,0,0,0.06); margin-bottom:8px; "
        f"border-left:4px solid {cor_p};'>"
        f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
        f"<div>"
        f"<span style='font-size:15px; font-weight:600; color:{AZUL_ESCURO};'>{r['nome']}</span>"
        f"{arquivado_badge}"
        f"<br>"
        f"<span style='font-size:12px; color:#666;'>"
        f"Parceiro <strong>{r['cod_parceiro']}</strong> · {cnpj}"
        f"</span>"
        f"</div>"
        f"<div style='text-align:right;'>"
        f"<span style='background:{cor_p}; color:white; padding:3px 10px; "
        f"border-radius:12px; font-size:11px; font-weight:600;'>{txt_p}</span>"
        f"<br>"
        f"<span style='background:{cor_s}; color:white; padding:3px 10px; "
        f"border-radius:12px; font-size:11px; font-weight:600; "
        f"margin-top:4px; display:inline-block;'>{txt_s}</span>"
        f"</div>"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
