"""Tela de Solicitações de Protesto."""
from __future__ import annotations
import streamlit as st

from src.servicos import solicitacoes as solic_svc
from src.servicos.solicitacoes import LinhaSolicitacao
from src.utils.marca import AZUL_ESCURO
from src.utils.estilo import card_kpi, fmt_real, COR_LARANJA, COR_VERDE, COR_VERMELHO, COR_AZUL
from src.utils.permissoes import pode_editar
from src.modelos.tipos import PerfilUsuario


def renderizar(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO};margin-bottom:4px;'>"
        f"📝 Solicitações de Protesto</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Solicite o protesto de clientes ou acompanhe os pedidos.")

    # Marca como visualizadas as resolvidas (pra zerar o badge ao abrir)
    solic_svc.marcar_visualizadas(usuario.id)

    pode_atender = pode_editar(usuario)  # ADMIN ou OPERADOR

    tab_nova, tab_pendentes, tab_historico, tab_minhas = st.tabs([
        "➕ Nova solicitação",
        "⏳ Pendentes",
        "📚 Histórico",
        "👤 Minhas solicitações",
    ])

    with tab_nova:
        _renderizar_nova_solicitacao(usuario)

    with tab_pendentes:
        _renderizar_pendentes(usuario, pode_atender)

    with tab_historico:
        _renderizar_historico()

    with tab_minhas:
        _renderizar_minhas(usuario)


# ============================================================
# Nova solicitação
# ============================================================

def _renderizar_nova_solicitacao(usuario):
    # Mensagem persistente do último envio (sobrevive ao rerun)
    msg = st.session_state.pop("solic_envio_msg", None)
    if msg:
        for texto in msg.get("sucesso", []):
            st.success(texto)
        for texto in msg.get("aviso", []):
            st.warning(texto)
        for texto in msg.get("erro", []):
            st.error(texto)

    st.markdown("### Preencha as linhas")
    st.caption(
        "Cada linha é uma solicitação separada. Só **Código do Parceiro** é "
        "obrigatório. Adicione mais linhas com o botão **+ adicionar linha**."
    )

    # Inicializa state: lista de linhas
    if "solic_linhas" not in st.session_state:
        st.session_state["solic_linhas"] = [{}]

    linhas = st.session_state["solic_linhas"]

    # Header
    h1, h2, h3, h4, h5 = st.columns([1.4, 1.6, 1.6, 1.1, 0.5])
    h1.caption("**Cód. Parceiro** *")
    h2.caption("**Valor (R$)**")
    h3.caption("**Nº Nota**")
    h4.caption("**Serasa?**")
    h5.caption(" ")

    indices_a_remover = []
    for i, linha in enumerate(linhas):
        c1, c2, c3, c4, c5 = st.columns([1.4, 1.6, 1.6, 1.1, 0.5])
        cod_str = c1.text_input(
            "Cód",
            value=str(linha.get("cod_parceiro", "")),
            key=f"linha_cod_{i}",
            label_visibility="collapsed",
            placeholder="ex: 12345",
        )
        valor_str = c2.text_input(
            "Valor",
            value=str(linha.get("valor", "")),
            key=f"linha_valor_{i}",
            label_visibility="collapsed",
            placeholder="opcional",
        )
        nota_str = c3.text_input(
            "Nota",
            value=str(linha.get("nro_nota", "")),
            key=f"linha_nota_{i}",
            label_visibility="collapsed",
            placeholder="opcional",
        )
        serasa = c4.checkbox(
            "Serasa?",
            value=linha.get("incluir_serasa", False),
            key=f"linha_serasa_{i}",
            label_visibility="collapsed",
        )

        # Atualiza o state
        linha["cod_parceiro"] = cod_str
        linha["valor"] = valor_str
        linha["nro_nota"] = nota_str
        linha["incluir_serasa"] = serasa

        if len(linhas) > 1:
            if c5.button("🗑", key=f"linha_del_{i}", help="Remover linha"):
                indices_a_remover.append(i)

    # Aplicar remoções (do final pro começo)
    for idx in sorted(indices_a_remover, reverse=True):
        linhas.pop(idx)
    if indices_a_remover:
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    col_add, col_obs = st.columns([1, 3])
    with col_add:
        if st.button("➕ Adicionar linha"):
            linhas.append({})
            st.rerun()

    obs_key = st.session_state.get("solic_obs_key", "solic_obs_v1")
    obs = st.text_area(
        "Observação geral (opcional)",
        key=obs_key,
        placeholder="Ex: pedido da diretoria pra protestar inadimplentes do trimestre",
        height=70,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("📤 Enviar solicitação(ões)", type="primary"):
        _processar_envio(linhas, obs, usuario)


def _processar_envio(linhas_state, obs, usuario):
    linhas_validas = []
    erros = []

    for i, linha in enumerate(linhas_state, 1):
        cod_str = str(linha.get("cod_parceiro", "")).strip()
        if not cod_str:
            continue  # linha vazia, ignora
        try:
            cod = int(cod_str)
        except ValueError:
            erros.append(f"Linha {i}: código de parceiro inválido ('{cod_str}')")
            continue

        valor_str = str(linha.get("valor", "")).strip()
        valor = None
        if valor_str:
            try:
                # Aceita "10.000,50" ou "10000.50" ou "10000,50"
                v = valor_str.replace("R$", "").strip()
                # Heurística: tem vírgula? formato BR
                if "," in v and "." in v:
                    v = v.replace(".", "").replace(",", ".")
                elif "," in v:
                    v = v.replace(",", ".")
                valor = float(v)
            except ValueError:
                erros.append(f"Linha {i}: valor inválido ('{valor_str}')")
                continue

        nota = str(linha.get("nro_nota", "")).strip() or None

        linhas_validas.append(LinhaSolicitacao(
            cod_parceiro=cod,
            valor=valor,
            nro_nota=nota,
            incluir_serasa=bool(linha.get("incluir_serasa", False)),
        ))

    if erros:
        for e in erros:
            st.error(e)
        return

    if not linhas_validas:
        st.warning("Preencha ao menos uma linha com código de parceiro.")
        return

    resultado = solic_svc.criar_solicitacoes(
        linhas=linhas_validas,
        observacao=obs.strip() if obs else None,
        solicitante_id=usuario.id,
    )

    # Monta a mensagem (vai pro session_state pra sobreviver ao rerun)
    partes_sucesso = []
    partes_aviso = []
    partes_erro = []

    if resultado["criadas"]:
        partes_sucesso.append(
            f"✅ **{resultado['criadas']} solicitação(ões) registrada(s)** com sucesso. "
            f"Veja em **⏳ Pendentes**."
        )

    if resultado.get("duplicadas"):
        n = len(resultado["duplicadas"])
        linhas_msg = [
            f"  • Cód **{d['cod_parceiro']}** — já tem pendente "
            f"(pedido por: {d['solicitante_anterior']})"
            for d in resultado["duplicadas"]
        ]
        partes_aviso.append(
            f"⚠️ **{n} cód(s) NÃO foi(ram) registrado(s)** porque já existem "
            f"solicitação(ões) pendente(s) pra eles:\n\n"
            + "\n".join(linhas_msg)
            + "\n\nAtenda ou recuse os pendentes primeiro pra solicitar de novo."
        )

    if resultado["erros"]:
        partes_erro.append("❌ Erros:\n\n" + "\n".join(f"  • {e}" for e in resultado["erros"]))

    # Guarda a mensagem no session_state (persiste no rerun)
    st.session_state["solic_envio_msg"] = {
        "sucesso": partes_sucesso,
        "aviso": partes_aviso,
        "erro": partes_erro,
    }

    # Toast pra dar feedback imediato
    if resultado["criadas"]:
        st.toast(f"✅ {resultado['criadas']} solicitação(ões) enviada(s)!", icon="✅")
    elif resultado.get("duplicadas"):
        st.toast(f"⚠️ Nenhuma criada — já tinham pendentes", icon="⚠️")

    # Só limpa o formulário se TUDO foi criado (não houve duplicados/erros)
    # Se houve problema, mantém o que o usuário digitou
    tudo_ok = bool(resultado["criadas"]) and not resultado.get("duplicadas") and not resultado["erros"]
    if tudo_ok:
        from time import time
        novo_sufixo = f"_v{int(time())}"
        st.session_state["solic_linhas"] = [{}]
        st.session_state["solic_obs_key"] = f"solic_obs{novo_sufixo}"
        for k in list(st.session_state.keys()):
            if k.startswith(("linha_cod_", "linha_valor_", "linha_nota_", "linha_serasa_")):
                del st.session_state[k]

    st.rerun()


# ============================================================
# Pendentes
# ============================================================

def _renderizar_pendentes(usuario, pode_atender):
    pendentes = solic_svc.listar_solicitacoes(status="PENDENTE")

    if not pendentes:
        st.info("📭 Nenhuma solicitação pendente.")
        return

    st.markdown(
        f"<h3 style='color:{AZUL_ESCURO};'>⏳ {len(pendentes)} pendente(s)</h3>",
        unsafe_allow_html=True,
    )

    # Processar ação pendente vinda do session_state
    acao = st.session_state.pop("solic_acao", None)
    if acao:
        sid, tipo, dados = acao
        if tipo == "atender":
            ok = solic_svc.atender_solicitacao(sid, usuario.id, dados.get("obs"))
            st.session_state["solic_msg"] = (
                "sucesso" if ok else "erro",
                "✅ Solicitação marcada como ATENDIDA." if ok else "❌ Não foi possível atender."
            )
        elif tipo == "recusar":
            ok = solic_svc.recusar_solicitacao(sid, usuario.id, dados["motivo"])
            st.session_state["solic_msg"] = (
                "sucesso" if ok else "erro",
                "✅ Solicitação RECUSADA." if ok else "❌ Motivo obrigatório."
            )
        st.rerun()

    msg = st.session_state.pop("solic_msg", None)
    if msg:
        (st.success if msg[0] == "sucesso" else st.error)(msg[1])

    for s in pendentes:
        _render_card_solicitacao(s, usuario, pode_atender, mostrar_acoes=True)


def _render_card_solicitacao(s, usuario, pode_atender, mostrar_acoes=False):
    nome = s["cliente_nome"] or "(cliente ainda não cadastrado)"
    valor_str = fmt_real(s["valor"]) if s["valor"] else "—"
    nota = s["nro_nota"] or "—"
    serasa = "Sim" if s["incluir_serasa"] else "Não"

    cor_borda = {
        "PENDENTE": COR_LARANJA,
        "ATENDIDA": COR_VERDE,
        "RECUSADA": COR_VERMELHO,
    }.get(s["status"], "#999")

    with st.container():
        col_info, col_acao = st.columns([3, 1.2])
        with col_info:
            st.markdown(
                f"<div style='background:#FFF; padding:12px 16px; border-radius:8px; "
                f"box-shadow:0 1px 3px rgba(0,0,0,0.06); margin-bottom:6px; "
                f"border-left:4px solid {cor_borda};'>"
                f"<span style='font-size:15px; font-weight:600; color:{AZUL_ESCURO};'>"
                f"Cód {s['cod_parceiro']} · {nome}</span><br>"
                f"<span style='font-size:12px; color:#666;'>"
                f"Valor: <strong>{valor_str}</strong> · Nota: {nota} · "
                f"Serasa: {serasa}<br>"
                f"Solicitado por <strong>{s['solicitante_nome']}</strong> em "
                f"{str(s['criado_em'])[:16]}"
                f"{'<br>Obs: ' + s['observacao'] if s['observacao'] else ''}"
                f"</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        if mostrar_acoes and pode_atender:
            with col_acao:
                if st.button("✅ Atender", key=f"atd_{s['id']}",
                             type="primary", use_container_width=True):
                    st.session_state["solic_acao"] = (s["id"], "atender", {})
                    st.rerun()
                if st.button("❌ Recusar", key=f"rec_{s['id']}",
                             use_container_width=True):
                    st.session_state[f"rec_input_{s['id']}"] = True
                    st.rerun()

                if st.session_state.get(f"rec_input_{s['id']}"):
                    motivo = st.text_input(
                        "Motivo:", key=f"motivo_{s['id']}",
                        placeholder="ex: cliente já pagou"
                    )
                    if st.button("Confirmar recusa", key=f"conf_rec_{s['id']}",
                                 use_container_width=True):
                        if motivo and motivo.strip():
                            st.session_state["solic_acao"] = (
                                s["id"], "recusar", {"motivo": motivo}
                            )
                            st.session_state.pop(f"rec_input_{s['id']}", None)
                            st.rerun()
                        else:
                            st.warning("Digite o motivo.")


# ============================================================
# Histórico
# ============================================================

def _renderizar_historico():
    filtro = st.selectbox(
        "Mostrar:",
        ["Todas resolvidas", "Apenas ATENDIDAS", "Apenas RECUSADAS"],
        key="hist_filtro",
    )

    if filtro == "Apenas ATENDIDAS":
        lista = solic_svc.listar_solicitacoes(status="ATENDIDA")
    elif filtro == "Apenas RECUSADAS":
        lista = solic_svc.listar_solicitacoes(status="RECUSADA")
    else:
        atendidas = solic_svc.listar_solicitacoes(status="ATENDIDA")
        recusadas = solic_svc.listar_solicitacoes(status="RECUSADA")
        # Combina ordenando por criado_em DESC
        lista = sorted(
            list(atendidas) + list(recusadas),
            key=lambda x: x["criado_em"], reverse=True
        )

    if not lista:
        st.info("Nenhuma solicitação resolvida ainda.")
        return

    for s in lista:
        _render_card_historico(s)


def _render_card_historico(s):
    nome = s["cliente_nome"] or "(cliente não cadastrado)"
    cor = COR_VERDE if s["status"] == "ATENDIDA" else COR_VERMELHO
    icone = "✅" if s["status"] == "ATENDIDA" else "❌"
    valor_str = fmt_real(s["valor"]) if s["valor"] else "—"
    auto = " <em>(auto-atendida)</em>" if s["auto_atendida"] else ""

    detalhe = ""
    if s["status"] == "ATENDIDA":
        detalhe = f"Atendida por <strong>{s['atendido_por_nome'] or '—'}</strong> em {str(s['atendido_em'])[:16]}{auto}"
    elif s["status"] == "RECUSADA":
        detalhe = f"Recusada por <strong>{s['atendido_por_nome'] or '—'}</strong> em {str(s['atendido_em'])[:16]}<br>Motivo: <em>{s['motivo_recusa']}</em>"

    st.markdown(
        f"<div style='background:#FFF; padding:10px 14px; border-radius:8px; "
        f"box-shadow:0 1px 2px rgba(0,0,0,0.05); margin-bottom:6px; "
        f"border-left:4px solid {cor};'>"
        f"<span style='font-size:14px; font-weight:600; color:{AZUL_ESCURO};'>"
        f"{icone} Cód {s['cod_parceiro']} · {nome}</span> "
        f"<span style='font-size:12px; color:#666;'>· {valor_str}</span><br>"
        f"<span style='font-size:11px; color:#888;'>"
        f"Pedido por {s['solicitante_nome']} em {str(s['criado_em'])[:16]}<br>"
        f"{detalhe}"
        f"</span></div>",
        unsafe_allow_html=True,
    )


# ============================================================
# Minhas solicitações
# ============================================================

def _renderizar_minhas(usuario):
    minhas = solic_svc.listar_solicitacoes(solicitante_id=usuario.id)

    if not minhas:
        st.info("Você ainda não fez nenhuma solicitação.")
        return

    n_pendentes = sum(1 for s in minhas if s["status"] == "PENDENTE")
    n_atendidas = sum(1 for s in minhas if s["status"] == "ATENDIDA")
    n_recusadas = sum(1 for s in minhas if s["status"] == "RECUSADA")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(card_kpi("Pendentes", f"{n_pendentes}", "aguardando",
                             COR_LARANJA, "⏳"), unsafe_allow_html=True)
    with c2:
        st.markdown(card_kpi("Atendidas", f"{n_atendidas}", "processadas",
                             COR_VERDE, "✅"), unsafe_allow_html=True)
    with c3:
        st.markdown(card_kpi("Recusadas", f"{n_recusadas}", "não atendidas",
                             COR_VERMELHO, "❌"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    for s in minhas:
        if s["status"] == "PENDENTE":
            _render_card_solicitacao(s, usuario, pode_atender=False)
        else:
            _render_card_historico(s)
