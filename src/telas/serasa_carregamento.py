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
        key="serasa_carregamento_uploader",
        label_visibility="collapsed",
    )

    if arquivos:
        st.markdown("<br>", unsafe_allow_html=True)
        st.info(f"📁 **{len(arquivos)} arquivo(s) selecionado(s).** Clique em processar para carregar.")

        col_btn, _ = st.columns([1, 2])
        with col_btn:
            if st.button(
                "▶️ Processar arquivos",
                type="primary",
                use_container_width=True,
                key="btn_processar_serasa",
            ):
                _processar_uploads(arquivos, usuario)


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
            conteudo = arquivo.read()
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
            novo_status = "ENVIADO" if arq.tipo == "INCLUSAO" else "EXCLUIDO"

            for t in arq.titulos:
                # Upsert do cliente (cria ou atualiza por nome)
                try:
                    # Verifica se cliente já existia
                    existia = conn.execute(
                        "SELECT 1 FROM cliente_protesto "
                        "WHERE LOWER(nome) = LOWER(?) LIMIT 1;",
                        (t.nome,)
                    ).fetchone() is not None

                    cliente_id = repo_cliente.upsert_cliente(
                        nome=t.nome,
                        cnpj_cpf=t.cnpj_cpf or None,
                    )

                    if existia:
                        clientes_atualizados += 1
                    else:
                        clientes_criados += 1

                    # Atualiza status Serasa
                    repo_cliente.atualizar_status_serasa(cliente_id, novo_status)
                except Exception as e:
                    erros.append(f"Cliente {t.nome}: {e}")
                    cliente_id = None

                # Insere o título do Serasa (linkado ao cliente)
                conn.execute(
                    "INSERT INTO titulo_serasa "
                    "(evento_id, cliente_id, cnpj_cpf, nome, valor, cep, nro_unico_serasa) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?);",
                    (evento_id, cliente_id, t.cnpj_cpf, t.nome,
                     t.valor, t.cep, t.nro_unico_serasa)
                )
                titulos_inseridos += 1

            sucesso += 1
        except Exception as e:
            erros.append(f"{arquivo.name}: {e}")

    if sucesso:
        st.success(
            f"✅ {sucesso} arquivo(s) processado(s)! "
            f"{titulos_inseridos} título(s), "
            f"{clientes_criados} cliente(s) novo(s), "
            f"{clientes_atualizados} cliente(s) atualizado(s)."
        )
    if duplicados:
        st.warning(f"⚠️ {duplicados} arquivo(s) já estavam carregados (sequencial repetido).")
    if erros:
        with st.expander("❌ Ver erros"):
            for e in erros:
                st.write(f"- {e}")

    if sucesso:
        st.info("Veja os clientes cadastrados em **👥 Clientes**.")
