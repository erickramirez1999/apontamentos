"""
Tela 'Lista de Protesto' — clientes atualmente em protesto.

Mostra todos os clientes com status PROTESTADO, com seus títulos do cartório
e botão pra marcar como PAGO (movendo pra Arquivados).
"""
from __future__ import annotations

import streamlit as st

from src.banco.conexao import obter_conexao
from src.banco import repo_cliente
from src.utils.marca import AZUL_ESCURO
from src.utils.estilo import card_kpi, COR_AZUL, COR_VERDE, COR_LARANJA, COR_VERMELHO
from src.utils.permissoes import pode_editar
from src.utils.exclusao_com_senha import confirmar_exclusao_com_senha
from src.servicos.protesto_remessas import excluir_remessa_protesto


def renderizar(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO};margin-bottom:4px;'>📋 Lista de Protesto</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Clientes em PROTESTO no momento, com títulos do cartório.")

    conn = obter_conexao()

    # ─── Processar ações pendentes ─────────────────────────
    acao = st.session_state.pop("lista_acao", None)
    if acao:
        cliente_id, tipo_acao = acao
        try:
            if tipo_acao == "marcar_pago":
                repo_cliente.atualizar_status_protesto(cliente_id, "PAGO")
                conn.execute(
                    "UPDATE cliente_protesto SET arquivado = 1, baixado = 0, "
                    "atualizado_em = datetime('now') WHERE id = ?;",
                    (cliente_id,)
                )
                st.session_state["lista_msg"] = (
                    "sucesso",
                    "✅ Cliente marcado como PAGO. Veja em 📁 Arquivados."
                )
            elif tipo_acao == "marcar_acordo":
                repo_cliente.atualizar_status_protesto(cliente_id, "ACORDO")
                st.session_state["lista_msg"] = (
                    "sucesso", "✅ Cliente marcado como em ACORDO."
                )
            st.rerun()
        except Exception as e:
            st.session_state["lista_msg"] = ("erro", f"❌ Erro: {e}")
            st.rerun()

    msg = st.session_state.pop("lista_msg", None)
    if msg:
        tipo, texto = msg
        (st.success if tipo == "sucesso" else st.error)(texto)

    permite_editar = pode_editar(usuario)

    # ─── Tabs: clientes em protesto / remessas geradas ─────────────────────────
    tab_protesto, tab_remessas = st.tabs([
        "👥 Clientes em Protesto",
        "📦 Remessas Geradas",
    ])

    with tab_protesto:
        _renderizar_clientes_em_protesto(usuario, permite_editar, conn)

    with tab_remessas:
        _renderizar_remessas(usuario, permite_editar, conn)


# ============================================================
# CLIENTES EM PROTESTO
# ============================================================

def _renderizar_clientes_em_protesto(usuario, permite_editar, conn):
    # Buscar clientes com status PROTESTADO + agregados do cartório
    try:
        clientes = conn.execute(
            """
            SELECT
                c.id, c.cod_parceiro, c.nome, c.cnpj_cpf,
                a.status_protesto, a.status_serasa,
                COUNT(t.id) as n_titulos,
                COALESCE(SUM(CASE WHEN t.cancelado = 0 THEN t.valor ELSE 0 END), 0) as valor_total,
                COALESCE(SUM(CASE WHEN t.cancelado = 0 THEN t.saldo ELSE 0 END), 0) as saldo_total
            FROM cliente_protesto c
            JOIN andamento_protesto a ON a.cliente_id = c.id
            LEFT JOIN titulo_cartorio t ON t.cliente_id = c.id
            WHERE a.status_protesto = 'PROTESTADO'
            GROUP BY c.id, c.cod_parceiro, c.nome, c.cnpj_cpf,
                     a.status_protesto, a.status_serasa
            ORDER BY valor_total DESC, c.nome;
            """
        ).fetchall()
    except Exception as e:
        st.error(f"Erro ao buscar clientes: {e}")
        clientes = []

    if not clientes:
        st.info(
            "📭 **Nenhum cliente em protesto no momento.**\n\n"
            "Carregue um relatório do cartório em **⚖️ Cartório** ou gere "
            "uma remessa em **📤 Protestar** (Passo 3 → 💾 Salvar remessa)."
        )
        return

    # KPIs
    total = len(clientes)
    valor_total = sum(c['valor_total'] for c in clientes)
    saldo_total = sum(c['saldo_total'] for c in clientes)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(card_kpi(
            "Clientes em Protesto", f"{total:,}",
            "ativos no momento", COR_VERMELHO, "👥"
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(card_kpi(
            "Valor total", f"R$ {valor_total:,.2f}",
            "de títulos protestados", COR_LARANJA, "💼"
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(card_kpi(
            "Saldo em aberto", f"R$ {saldo_total:,.2f}",
            "ainda devido", COR_VERDE, "💰"
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Filtro busca
    busca = st.text_input("🔍 Buscar cliente:", "", placeholder="Nome ou código...")
    if busca:
        b = busca.lower()
        clientes = [c for c in clientes
                    if b in c['nome'].lower() or b in str(c['cod_parceiro'] or '')]

    if not clientes:
        st.caption("Nenhum cliente bate com a busca.")
        return

    st.markdown(
        f"<h3 style='color:{AZUL_ESCURO};margin-bottom:8px;'>"
        f"📋 {len(clientes)} cliente(s)</h3>",
        unsafe_allow_html=True,
    )

    for c in clientes:
        with st.container():
            col_info, col_btns = st.columns([3, 1])
            with col_info:
                st.markdown(
                    f"<div style='background:#FFF; padding:12px 16px; border-radius:8px; "
                    f"box-shadow:0 1px 3px rgba(0,0,0,0.06); margin-bottom:4px; "
                    f"border-left:4px solid {COR_VERMELHO};'>"
                    f"<span style='font-size:15px; font-weight:600; color:{AZUL_ESCURO};'>"
                    f"{c['nome']}</span><br>"
                    f"<span style='font-size:12px; color:#666;'>"
                    f"Parceiro <strong>{c['cod_parceiro'] or '—'}</strong> · "
                    f"{c['cnpj_cpf'] or '—'} · "
                    f"{c['n_titulos']} título(s) no cartório · "
                    f"<strong>R$ {c['valor_total']:,.2f}</strong> "
                    f"(saldo R$ {c['saldo_total']:,.2f})"
                    f"</span></div>",
                    unsafe_allow_html=True,
                )
            with col_btns:
                if permite_editar:
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("✅ Pago", key=f"pago_{c['id']}",
                                     use_container_width=True, type="primary"):
                            st.session_state["lista_acao"] = (c['id'], "marcar_pago")
                            st.rerun()
                    with btn_col2:
                        if st.button("🤝 Acordo", key=f"acordo_{c['id']}",
                                     use_container_width=True):
                            st.session_state["lista_acao"] = (c['id'], "marcar_acordo")
                            st.rerun()


# ============================================================
# REMESSAS GERADAS (Passo 3)
# ============================================================

def _renderizar_remessas(usuario, permite_editar, conn):
    try:
        remessas = conn.execute(
            "SELECT id, mes_referencia, nome_arquivo_gerado, total_clientes, "
            "total_titulos, valor_total, criado_em "
            "FROM remessa_protesto "
            "ORDER BY criado_em DESC;"
        ).fetchall()
    except Exception:
        remessas = []

    n_remessas = len(remessas)
    n_clientes = sum(r["total_clientes"] for r in remessas)
    valor_total = sum(r["valor_total"] for r in remessas)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(card_kpi(
            "Remessas", f"{n_remessas:,}", "geradas no sistema", COR_AZUL, "📦"
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(card_kpi(
            "Clientes", f"{n_clientes:,}", "em remessas", COR_LARANJA, "👥"
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(card_kpi(
            "Valor total", f"R$ {valor_total:,.2f}", "em remessas", COR_VERDE, "💰"
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if not remessas:
        st.info(
            "📭 **Nenhuma remessa registrada.**\n\n"
            "Pra criar: vá em **📤 Protestar** → Passo 3, e clique em "
            "**💾 Salvar remessa no sistema**."
        )
        return

    # Pré-carregar títulos
    ids_remessas = [r["id"] for r in remessas]
    titulos_por_remessa: dict[int, list] = {rid: [] for rid in ids_remessas}
    if ids_remessas:
        placeholders = ",".join("?" * len(ids_remessas))
        try:
            rows = conn.execute(
                f"SELECT t.remessa_id, c.nome, c.cod_parceiro, t.nro_unico, "
                f"t.empresa, t.valor "
                f"FROM titulo_protesto t "
                f"JOIN cliente_protesto c ON c.id = t.cliente_id "
                f"WHERE t.remessa_id IN ({placeholders}) "
                f"ORDER BY c.nome, t.empresa;",
                tuple(ids_remessas)
            ).fetchall()
            for row in rows:
                titulos_por_remessa[row["remessa_id"]].append(row)
        except Exception:
            pass

    for r in remessas:
        with st.expander(
            f"📦 {r['mes_referencia']} — "
            f"{r['total_clientes']} clientes · "
            f"R$ {r['valor_total']:,.2f}"
        ):
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.write(f"**Arquivo:** `{r['nome_arquivo_gerado']}`")
                st.write(f"**Criado em:** {r['criado_em']}")
                st.write(f"**Total de títulos:** {r['total_titulos']}")
            with col_btn:
                if permite_editar:
                    confirmar_exclusao_com_senha(
                        usuario_logado=usuario,
                        chave=f"del_remessa_{r['id']}",
                        descricao_item=f"Remessa {r['mes_referencia']}",
                        on_confirmar=lambda rid=r['id']: excluir_remessa_protesto(rid),
                    )

            titulos = titulos_por_remessa.get(r['id'], [])
            if titulos:
                st.markdown("**Títulos da remessa:**")
                ultimo_cliente = None
                for t in titulos:
                    if t['nome'] != ultimo_cliente:
                        st.markdown(
                            f"&nbsp;&nbsp;**{t['nome']}** "
                            f"<span style='color:#999;font-size:11px;'>"
                            f"Parc {t['cod_parceiro']}</span>",
                            unsafe_allow_html=True,
                        )
                        ultimo_cliente = t['nome']
                    st.caption(
                        f"  &nbsp;&nbsp;&nbsp;&nbsp;• {t['empresa']} · "
                        f"{t['nro_unico']} · R$ {t['valor']:,.2f}"
                    )
