"""Tela Serasa › Carregamento — upload de arquivos CNAB."""
from __future__ import annotations

import streamlit as st

from src.banco.conexao import obter_conexao
from src.servicos.parser_serasa import parsear_arquivo_serasa
from src.utils.marca import AZUL_ESCURO
from src.utils.permissoes import pode_editar
from src.utils.estilo import card_kpi, COR_AZUL, COR_VERDE


def renderizar(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO};margin-bottom:4px;'>📤 Carregamento Serasa</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Upload dos arquivos CNAB (Inclusão / Exclusão) gerados a partir do Sankhya.")

    if not pode_editar(usuario):
        st.error("🔒 Seu perfil não permite carregar arquivos. Você pode visualizar nas abas Inclusos / Exclusos.")
        return

    conn = obter_conexao()

    # KPIs rápidos
    try:
        total_inc = conn.execute(
            "SELECT COUNT(*) FROM evento_serasa WHERE tipo = 'INCLUSAO';"
        ).fetchone()[0]
        total_exc = conn.execute(
            "SELECT COUNT(*) FROM evento_serasa WHERE tipo = 'EXCLUSAO';"
        ).fetchone()[0]
    except Exception:
        total_inc = total_exc = 0

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(card_kpi(
            "Inclusões carregadas", f"{total_inc:,}",
            "arquivos no histórico", COR_AZUL, "📥"
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(card_kpi(
            "Exclusões carregadas", f"{total_exc:,}",
            "arquivos no histórico", COR_VERDE, "📤"
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Upload
    st.markdown(
        f"<h3 style='color:{AZUL_ESCURO}; margin-bottom:8px;'>"
        f"📂 Selecione os arquivos</h3>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Formato esperado: `Inclusão_DD_MM_YYYY_NNNN.txt` ou `Exclusão_DD_MM_YYYY_NNNN.txt`. "
        "Você pode subir vários de uma vez."
    )

    arquivos = st.file_uploader(
        " ",
        type=["txt"],
        accept_multiple_files=True,
        key=st.session_state.get("serasa_uploader_key", "serasa_uploader_v1"),
        label_visibility="collapsed",
    )

    # Mensagem persistente do último processamento (sobrevive ao rerun)
    msg = st.session_state.pop("serasa_msg_resultado", None)
    if msg:
        if msg.get("tipo") == "sucesso":
            st.success(msg["texto"])
        elif msg.get("tipo") == "aviso":
            st.warning(msg["texto"])
        elif msg.get("tipo") == "erro":
            st.error(msg["texto"])

    # Erros detalhados
    erros_detalhe = st.session_state.pop("serasa_erros_detalhe", None)
    if erros_detalhe:
        with st.expander(f"❌ Ver erros ({len(erros_detalhe)})"):
            for e in erros_detalhe:
                st.write(f"- {e}")

    if arquivos:
        st.markdown("<br>", unsafe_allow_html=True)
        st.info(f"📁 **{len(arquivos)} arquivo(s) selecionado(s).** Clique em processar para carregar.")

        # Hash combinado dos arquivos (anti-reprocesso na mesma sessão)
        import hashlib
        h = hashlib.md5()
        for a in arquivos:
            h.update(a.getvalue())
        hash_combinado = h.hexdigest()

        # Se já processou EXATAMENTE esses arquivos antes nessa sessão, avisa
        if st.session_state.get("serasa_hash_processado") == hash_combinado:
            st.warning(
                "ℹ️ **Esses arquivos já foram processados nessa sessão.** "
                "Pra carregar outros, remova os arquivos selecionados (ícone ✕) "
                "e selecione novos."
            )
            return

        col_btn, _ = st.columns([1, 2])
        with col_btn:
            if st.button(
                "▶️ Processar arquivos",
                type="primary",
                use_container_width=True,
                key="btn_processar_serasa",
            ):
                # Try/except externo pra GARANTIR que sempre tem feedback
                try:
                    _processar_uploads(arquivos, usuario)
                    # Se não setou mensagem alguma, isso indica problema silencioso
                    if "serasa_msg_resultado" not in st.session_state:
                        st.session_state["serasa_msg_resultado"] = {
                            "tipo": "aviso",
                            "texto": (
                                "⚠️ Processamento terminou sem resultado claro. "
                                "Verifique os carregamentos anteriores pra ver o que entrou."
                            ),
                        }
                    # Marca esse conjunto de arquivos como já processado
                    st.session_state["serasa_hash_processado"] = hash_combinado
                    # Trocar a key do uploader → força limpar a lista
                    import time as _t
                    st.session_state["serasa_uploader_key"] = f"serasa_uploader_{int(_t.time())}"
                except Exception as e:
                    # Erro FATAL (timeout, conexão caiu, etc) — registra a mensagem
                    import traceback
                    st.session_state["serasa_msg_resultado"] = {
                        "tipo": "erro",
                        "texto": (
                            f"❌ **Erro inesperado ao processar:** {type(e).__name__}: {e}\n\n"
                            f"Talvez a conexão com o banco tenha caído. Tente novamente."
                        ),
                    }
                    st.session_state["serasa_erros_detalhe"] = [traceback.format_exc()]
                st.rerun()


def _processar_uploads(arquivos, usuario):
    from src.banco import repo_cliente

    conn = obter_conexao()
    sucesso = 0
    duplicados = 0
    erros = []
    clientes_criados = 0
    clientes_atualizados = 0
    titulos_inseridos = 0

    for arquivo in arquivos:
        try:
            conteudo = arquivo.getvalue()
            arq = parsear_arquivo_serasa(arquivo.name, conteudo)

            cur = conn.execute(
                "SELECT id FROM evento_serasa WHERE sequencial = ?;",
                (arq.sequencial,)
            )
            if cur.fetchone():
                duplicados += 1
                continue

            cur = conn.execute(
                "INSERT INTO evento_serasa "
                "(tipo, data_arquivo, sequencial, nome_arquivo, total_clientes, usuario_id) "
                "VALUES (?, ?, ?, ?, ?, ?);",
                (arq.tipo, arq.data_arquivo.isoformat(), arq.sequencial,
                 arquivo.name, len(arq.titulos), usuario.id)
            )
            evento_id = cur.lastrowid

            # Status que esse arquivo aplica ao cliente
            # (NÃO usamos diretamente — vamos recalcular baseado no evento
            # mais recente, pra suportar uploads fora de ordem cronológica)

            # OTIMIZAÇÃO: pré-carrega clientes existentes em UM query
            nomes_arquivo = list({t.nome.upper() for t in arq.titulos if t.nome})
            existentes_nomes = set()
            if nomes_arquivo:
                placeholders = ",".join("?" * len(nomes_arquivo))
                rows = conn.execute(
                    f"SELECT UPPER(nome) as n FROM cliente_protesto "
                    f"WHERE UPPER(nome) IN ({placeholders});",
                    tuple(nomes_arquivo)
                ).fetchall()
                existentes_nomes = {r["n"] for r in rows}

            # Coletar clientes desse arquivo pra recalcular status no fim
            cids_deste_arquivo: set[int] = set()
            params_titulos_serasa = []  # batch insert

            for t in arq.titulos:
                # Upsert do cliente (cria ou atualiza por nome)
                try:
                    existia = t.nome.upper() in existentes_nomes
                    cliente_id = repo_cliente.upsert_cliente(
                        nome=t.nome,
                        cnpj_cpf=t.cnpj_cpf or None,
                    )
                    # Próximas iterações do mesmo arquivo veem esse nome como existente
                    existentes_nomes.add(t.nome.upper())

                    if existia:
                        clientes_atualizados += 1
                    else:
                        clientes_criados += 1
                except Exception as e:
                    erros.append(f"Cliente {t.nome}: {e}")
                    cliente_id = None

                # Acumula params do título Serasa (batch insert no fim)
                params_titulos_serasa.append((
                    evento_id, cliente_id, t.cnpj_cpf, t.nome,
                    t.valor, t.cep, t.nro_unico_serasa
                ))
                titulos_inseridos += 1

                if cliente_id is not None:
                    cids_deste_arquivo.add(cliente_id)

            # BATCH INSERT: insere TODOS os títulos Serasa em 1 ida ao banco
            if params_titulos_serasa:
                conn.executemany(
                    "INSERT INTO titulo_serasa "
                    "(evento_id, cliente_id, cnpj_cpf, nome, valor, cep, nro_unico_serasa) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?);",
                    params_titulos_serasa
                )

            # Recalcula status uma vez por cliente (não por título!)
            for cid in cids_deste_arquivo:
                repo_cliente.recalcular_status_serasa(cid)

            sucesso += 1
        except Exception as e:
            erros.append(f"{arquivo.name}: {e}")

    # Monta a mensagem final (vai pro session_state pra sobreviver ao rerun)
    partes = []

    if sucesso:
        partes.append(
            f"✅ {sucesso} arquivo(s) processado(s)! "
            f"{titulos_inseridos} título(s), "
            f"{clientes_criados} cliente(s) novo(s), "
            f"{clientes_atualizados} cliente(s) atualizado(s)."
        )
    if duplicados:
        partes.append(f"⚠️ {duplicados} arquivo(s) já estavam carregados (sequencial repetido).")
    if erros and not sucesso:
        partes.append(f"❌ Nenhum arquivo processado. {len(erros)} erro(s).")
    elif erros:
        partes.append(f"⚠️ {len(erros)} erro(s) durante o processamento.")

    # SEMPRE seta mensagem (mesmo se partes vazias) — pra usuário ter feedback
    if not partes:
        partes.append(
            "⚠️ Processamento terminou sem resultado. "
            f"Recebeu {len(arquivos)} arquivo(s), 0 sucesso, 0 duplicado, 0 erro. "
            "Pode ser um problema na conexão com o banco. Tente recarregar a página."
        )

    # Define o tipo da mensagem
    if sucesso and not erros:
        tipo = "sucesso"
    elif sucesso:
        tipo = "aviso"
    elif erros:
        tipo = "erro"
    else:
        tipo = "aviso"

    st.session_state["serasa_msg_resultado"] = {
        "tipo": tipo,
        "texto": "\n\n".join(partes) + (
            "\n\nVeja os clientes cadastrados em **👥 Clientes**."
            if sucesso else ""
        ),
    }

    # Guarda os erros detalhados pra mostrar num expander após rerun
    if erros:
        st.session_state["serasa_erros_detalhe"] = erros[:50]
    else:
        st.session_state.pop("serasa_erros_detalhe", None)
