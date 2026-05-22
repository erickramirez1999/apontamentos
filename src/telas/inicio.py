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
            f"{metricas['titulos_cartorio']} título(s) no cartório",
            COR_VERDE, "💼"
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
            # criado_em pode ser datetime (Postgres) ou string (SQLite)
            criado_str = str(a['criado_em'])[:16]
            st.markdown(
                f"<div style='padding:8px 12px; border-left:3px solid {COR_CINZA}; "
                f"background:#FAFAFA; border-radius:4px; margin-bottom:4px;'>"
                f"<span style='font-size:11px; color:#999;'>{criado_str}</span><br>"
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
    """
    Coleta métricas do banco. Otimizado: agrupa contagens em poucas queries
    em vez de uma por métrica (10 queries → 4 queries).
    """
    conn = obter_conexao()

    metricas = {
        "total_clientes": 0, "em_protesto": 0, "em_acordo": 0,
        "pagos": 0, "nao_baixados": 0,
        "serasa_inclusoes": 0, "serasa_exclusoes": 0, "serasa_titulos": 0,
        "valor_protesto": 0.0, "remessas_total": 0,
        "titulos_cartorio": 0, "saldo_cartorio": 0.0,
    }

    # Query 1: dados de cliente_protesto (3 métricas)
    try:
        row = conn.execute(
            "SELECT "
            "COUNT(*) as total, "
            "COUNT(*) FILTER (WHERE arquivado = 1) as arquivados, "
            "COUNT(*) FILTER (WHERE arquivado = 1 AND baixado = 0) as nao_baixados "
            "FROM cliente_protesto;"
        ).fetchone()
        if row:
            metricas["total_clientes"] = row[0]
            metricas["pagos"] = row[1]
            metricas["nao_baixados"] = row[2]
    except Exception:
        # Fallback SQLite (não tem FILTER) — 3 queries
        try:
            metricas["total_clientes"] = conn.execute(
                "SELECT COUNT(*) FROM cliente_protesto;"
            ).fetchone()[0]
            metricas["pagos"] = conn.execute(
                "SELECT COUNT(*) FROM cliente_protesto WHERE arquivado = 1;"
            ).fetchone()[0]
            metricas["nao_baixados"] = conn.execute(
                "SELECT COUNT(*) FROM cliente_protesto WHERE arquivado = 1 AND baixado = 0;"
            ).fetchone()[0]
        except Exception:
            pass

    # Query 2: status andamento (2 métricas)
    try:
        rows = conn.execute(
            "SELECT status_protesto, COUNT(*) as n FROM andamento_protesto "
            "GROUP BY status_protesto;"
        ).fetchall()
        for r in rows:
            if r["status_protesto"] == "PROTESTADO":
                metricas["em_protesto"] = r["n"]
            elif r["status_protesto"] == "ACORDO":
                metricas["em_acordo"] = r["n"]
    except Exception:
        pass

    # Query 3: eventos serasa (2 métricas)
    try:
        rows = conn.execute(
            "SELECT tipo, COUNT(*) as n FROM evento_serasa GROUP BY tipo;"
        ).fetchall()
        for r in rows:
            if r["tipo"] == "INCLUSAO":
                metricas["serasa_inclusoes"] = r["n"]
            elif r["tipo"] == "EXCLUSAO":
                metricas["serasa_exclusoes"] = r["n"]
    except Exception:
        pass

    # Query 4: títulos serasa
    try:
        metricas["serasa_titulos"] = conn.execute(
            "SELECT COUNT(*) FROM titulo_serasa;"
        ).fetchone()[0]
    except Exception:
        pass

    # Query 5: remessas (geradas pelo sistema)
    try:
        row = conn.execute(
            "SELECT COUNT(*) as n, COALESCE(SUM(valor_total), 0) as soma "
            "FROM remessa_protesto;"
        ).fetchone()
        if row:
            metricas["remessas_total"] = row[0]
    except Exception:
        pass

    # Query 6: títulos do cartório (a fonte REAL do valor protestado).
    # Soma só o que NÃO está cancelado (saldo em aberto)
    try:
        row = conn.execute(
            "SELECT "
            "COUNT(*) as n, "
            "COALESCE(SUM(CASE WHEN cancelado = 0 THEN saldo ELSE 0 END), 0) as saldo, "
            "COALESCE(SUM(CASE WHEN cancelado = 0 THEN valor ELSE 0 END), 0) as valor "
            "FROM titulo_cartorio;"
        ).fetchone()
        if row:
            metricas["titulos_cartorio"] = row[0]
            metricas["saldo_cartorio"] = float(row[1])
            # Valor protestado real = soma dos valores dos títulos ativos no cartório
            metricas["valor_protesto"] = float(row[2])
    except Exception:
        pass

    return metricas


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
            "ORDER BY nome;",
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
