"""
Tela Início — Dashboard executivo do LLE Protestos.

Layout estilo LLE (consistente com LLE Acordos e LLE Índices):
  1. Saudação + busca rápida
  2. KPIs grandes coloridos (cards com borda lateral)
  3. Seção Protesto (cards menores)
  4. Seção Serasa (cards menores)
  5. Atividades recentes (lista enxuta)
"""
from __future__ import annotations

import streamlit as st

from src.banco.conexao import obter_conexao
from src.utils.marca import AZUL_ESCURO
from src.utils.estilo import (
    card_kpi,
    COR_AZUL, COR_VERDE, COR_LARANJA, COR_VERMELHO, COR_CINZA, COR_AMARELO,
)


def renderizar_inicio(usuario):
    primeiro_nome = usuario.nome.split()[0] if usuario.nome else "usuário"

    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO};margin-bottom:4px;'>"
        f"Olá, {primeiro_nome}! 👋</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Painel geral do sistema LLE Protestos")

    busca = st.text_input(
        "🔍 Buscar cliente (nome ou código de parceiro):",
        "",
        placeholder="Digite e pressione Enter...",
        key="dashboard_busca",
    )
    if busca:
        _renderizar_resultado_busca(busca)
        st.markdown("---")

    st.markdown("<br>", unsafe_allow_html=True)

    metricas = _obter_metricas()

    # ─── Visão geral ─────────────────────────
    st.markdown(
        f"<h3 style='color:{AZUL_ESCURO}; margin-bottom:8px;'>📊 Visão geral</h3>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(card_kpi(
            "Clientes cadastrados", f"{metricas['total_clientes']:,}",
            "no sistema", COR_AZUL, "👥"
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(card_kpi(
            "Valor total em Protesto", f"R$ {metricas['valor_protesto']:,.2f}",
            f"{metricas['remessas_total']} remessa(s)", COR_VERDE, "💼"
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(card_kpi(
            "Títulos no Serasa", f"{metricas['serasa_titulos']:,}",
            f"{metricas['serasa_inclusoes']} inclusões / {metricas['serasa_exclusoes']} exclusões",
            COR_LARANJA, "🔔"
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Protesto ─────────────────────────
    st.markdown(
        f"<h3 style='color:{AZUL_ESCURO}; margin-bottom:8px;'>📤 Protesto</h3>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(card_kpi(
            "Protestados", f"{metricas['em_protesto']:,}",
            "ativos no momento", COR_VERMELHO, "📤"
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(card_kpi(
            "Em acordo", f"{metricas['em_acordo']:,}",
            "negociando", COR_AMARELO, "🤝"
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(card_kpi(
            "Pagos", f"{metricas['pagos']:,}",
            "clientes que quitaram", COR_VERDE, "✅"
        ), unsafe_allow_html=True)
    with c4:
        st.markdown(card_kpi(
            "Não baixados", f"{metricas['nao_baixados']:,}",
            "pagos mas sem baixa cartório", COR_LARANJA, "⚠️"
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Serasa ─────────────────────────
    st.markdown(
        f"<h3 style='color:{AZUL_ESCURO}; margin-bottom:8px;'>🔔 Serasa</h3>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(card_kpi(
            "Inclusões", f"{metricas['serasa_inclusoes']:,}",
            "arquivos enviados", COR_AZUL, "📥"
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(card_kpi(
            "Exclusões", f"{metricas['serasa_exclusoes']:,}",
            "arquivos enviados", COR_VERDE, "📤"
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(card_kpi(
            "Títulos registrados", f"{metricas['serasa_titulos']:,}",
            "no histórico do Serasa", COR_CINZA, "📋"
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── Atividades recentes ─────────────────────────
    st.markdown(
        f"<h3 style='color:{AZUL_ESCURO}; margin-bottom:8px;'>"
        f"🕓 Atividades recentes</h3>",
        unsafe_allow_html=True,
    )

    atividades = _atividades_recentes()
    if atividades:
        for a in atividades:
            st.markdown(
                f"<div style='padding:8px 12px; border-left:3px solid {COR_CINZA}; "
                f"background:#FAFAFA; border-radius:4px; margin-bottom:4px;'>"
                f"<span style='font-size:11px; color:#999;'>{a['criado_em'][:16]}</span><br>"
                f"<span style='font-size:13px;'>{a['descricao']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info(
            "Nenhuma atividade registrada ainda. "
            "Comece subindo uma planilha em **📤 Protestar**."
        )


def _obter_metricas() -> dict:
    conn = obter_conexao()

    def _count(sql, params=()):
        try:
            cur = conn.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    def _sum(sql, params=()):
        try:
            cur = conn.execute(sql, params)
            row = cur.fetchone()
            return float(row[0]) if row and row[0] is not None else 0.0
        except Exception:
            return 0.0

    return {
        "total_clientes": _count("SELECT COUNT(*) FROM cliente_protesto;"),
        "em_protesto": _count(
            "SELECT COUNT(*) FROM andamento_protesto "
            "WHERE status_protesto = 'PROTESTADO';"
        ),
        "em_acordo": _count(
            "SELECT COUNT(*) FROM andamento_protesto "
            "WHERE status_protesto = 'ACORDO';"
        ),
        "pagos": _count(
            "SELECT COUNT(*) FROM cliente_protesto WHERE arquivado = 1;"
        ),
        "nao_baixados": _count(
            "SELECT COUNT(*) FROM cliente_protesto "
            "WHERE arquivado = 1 AND baixado = 0;"
        ),
        "serasa_inclusoes": _count(
            "SELECT COUNT(*) FROM evento_serasa WHERE tipo = 'INCLUSAO';"
        ),
        "serasa_exclusoes": _count(
            "SELECT COUNT(*) FROM evento_serasa WHERE tipo = 'EXCLUSAO';"
        ),
        "serasa_titulos": _count("SELECT COUNT(*) FROM titulo_serasa;"),
        "valor_protesto": _sum("SELECT SUM(valor_total) FROM remessa_protesto;"),
        "remessas_total": _count("SELECT COUNT(*) FROM remessa_protesto;"),
    }


def _atividades_recentes(limite: int = 10) -> list[dict]:
    conn = obter_conexao()
    try:
        cur = conn.execute(
            "SELECT acao, detalhes, criado_em FROM log_auditoria "
            "ORDER BY criado_em DESC LIMIT ?;",
            (limite,)
        )
        rows = cur.fetchall()
        from src.utils.traducoes import traduzir_acao
        return [
            {
                "criado_em": r["criado_em"],
                "descricao": traduzir_acao(r["acao"]) + (
                    f" — {r['detalhes']}" if r["detalhes"] else ""
                ),
            }
            for r in rows
        ]
    except Exception:
        return []


def _renderizar_resultado_busca(termo: str):
    conn = obter_conexao()
    try:
        cur = conn.execute(
            "SELECT id, cod_parceiro, nome, arquivado FROM cliente_protesto "
            "WHERE LOWER(nome) LIKE LOWER(?) OR CAST(cod_parceiro AS TEXT) LIKE ? "
            "ORDER BY nome LIMIT 20;",
            (f"%{termo}%", f"%{termo}%")
        )
        clientes = cur.fetchall()
    except Exception:
        clientes = []

    if not clientes:
        st.info(f"Nenhum cliente encontrado para **'{termo}'**.")
        return

    st.markdown(f"**{len(clientes)} cliente(s) encontrado(s):**")
    for c in clientes:
        emoji = "📁" if c['arquivado'] else "📋"
        st.write(f"{emoji} **{c['nome']}** — Parceiro {c['cod_parceiro']}")
