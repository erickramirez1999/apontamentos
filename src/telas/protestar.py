"""Tela 'Protestar' — Passos 1, 2 e 3 do fluxo de protesto."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from src.servicos.filtragem_sankhya import (
    ler_planilha_sankhya,
    aplicar_filtros,
)
from src.servicos.agrupamento_resumo import (
    agrupar_para_planilha_resumo,
    gerar_excel_resumo,
)
from src.servicos.passo3_cartorio import (
    selecionar_titulos_passo3,
    gerar_txt_passo3,
)
from src.utils.permissoes import pode_editar
from src.utils.estilo import fmt_real


def renderizar(usuario):
    if not pode_editar(usuario):
        st.error("🔒 Seu perfil não permite gerar protestos.")
        st.stop()

    st.title("📤 Protestar")
    st.caption("Upload da planilha do Sankhya e geração dos arquivos para protesto.")
    st.markdown("---")

    # Tabs dos 3 passos
    tab1, tab2, tab3 = st.tabs([
        "1️⃣ Passo 1 — Filtragem Inicial",
        "2️⃣ Passo 2 — Planilha Confirmada",
        "3️⃣ Passo 3 — Gerar Arquivo Cartório",
    ])

    with tab1:
        _renderizar_passo1(usuario)
    with tab2:
        _renderizar_passo2(usuario)
    with tab3:
        _renderizar_passo3(usuario)


def _colorir_linha_empresa(row):
    """
    Cores por empresa LLE pra prévia das planilhas.
    PISA → azul · KING → amarelo · TRIO → verde
    (mesmas cores usadas no Excel gerado pra confirmação visual)
    """
    empresa = str(row.get("EMPRESA", "")).strip().upper()
    if empresa == "PISA":
        cor_bg = "#D6E4FF"  # azul claro
    elif empresa == "KING":
        cor_bg = "#FFF5CC"  # amarelo claro
    elif empresa == "TRIO":
        cor_bg = "#D6F5D6"  # verde claro
    else:
        cor_bg = ""
    return [f"background-color: {cor_bg}" if cor_bg else ""] * len(row)


def _mostrar_previa_resumo(resumo):
    """Mostra prévia do resumo com cores por empresa (helper)."""
    st.caption("🟦 PISA · 🟨 KING · 🟩 TRIO")
    try:
        st.dataframe(
            resumo.style.apply(_colorir_linha_empresa, axis=1),
            use_container_width=True,
            hide_index=True,
        )
    except Exception:
        # Fallback se algo der errado com a estilização
        st.dataframe(resumo, use_container_width=True, hide_index=True)


def _renderizar_passo1(usuario):
    st.subheader("Passo 1 — Filtragem Inicial")
    st.markdown(
        """
        Suba a planilha **crua do Sankhya** com todos os títulos vencidos.
        O sistema vai aplicar os filtros (PROT, ACORDO, DV TOTAL, terceirizadas, atraso 60-364)
        e gerar uma planilha resumida agrupada por cliente + empresa (PISA/KING/TRIO).
        """
    )

    arquivo = st.file_uploader(
        "Planilha do Sankhya (.xls ou .xlsx)",
        type=["xls", "xlsx"],
        key="passo1_uploader",
    )

    if arquivo is None:
        return

    try:
        df = ler_planilha_sankhya(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler a planilha: {e}")
        return

    resultado = aplicar_filtros(df)
    resumo = agrupar_para_planilha_resumo(resultado.df_validos)

    # Cards de métricas
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Títulos brutos", f"{resultado.total_brutos:,}")
    col2.metric("Títulos válidos", f"{resultado.total_validos:,}")
    col3.metric("Clientes excluídos por #PROT", f"{resultado.clientes_excluidos_prot:,}")
    col4.metric("Linhas resumo (cliente+empresa)", f"{len(resumo):,}")

    with st.expander("📊 Ver detalhes dos motivos de exclusão"):
        for motivo, qtd in resultado.motivos_exclusao.items():
            if qtd > 0:
                st.write(f"- **{motivo}**: {qtd} título(s)")

        # Detalhe específico do filtro de tipo (boletos)
        if resultado.titulos_excluidos_tipo > 0:
            tipos_str = ", ".join(str(t) for t in sorted(resultado.tipos_ignorados))
            st.caption(
                f"ℹ️ {resultado.titulos_excluidos_tipo} título(s) foram ignorado(s) "
                f"por não serem boletos. Tipos não-boleto encontrados: **{tipos_str}**. "
                f"Tipos permitidos: 4, 28, 29, 39, 40, 41, 47, 48, 64, 70."
            )

    if resumo.empty:
        st.warning("Nenhum título elegível após os filtros.")
        return

    st.markdown("### 📋 Prévia da planilha gerada")
    _mostrar_previa_resumo(resumo)

    # Botão de download
    data = gerar_excel_resumo(resumo)
    nome_saida = f"Passo1_Filtragem_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    st.download_button(
        label="⬇️ Baixar Planilha do Passo 1",
        data=data,
        file_name=nome_saida,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )

    st.info(
        "💡 **Próximo passo:** baixe essa planilha, faça a análise manual "
        "(tickets, sistemas, etc.) e quando estiver pronto, vá ao **Passo 2** "
        "com a planilha completa (vida total dos clientes selecionados)."
    )


def _renderizar_passo2(usuario):
    st.subheader("Passo 2 — Planilha Confirmada")
    st.markdown(
        """
        Suba a planilha do Sankhya com a **vida completa** dos clientes que você
        decidiu protestar (mesmo formato do Passo 1).
        O sistema aplica os mesmos filtros e gera uma planilha resumida pra
        confirmação visual.
        """
    )

    arquivo = st.file_uploader(
        "Planilha do Sankhya completa (.xls ou .xlsx)",
        type=["xls", "xlsx"],
        key="passo2_uploader",
    )

    if arquivo is None:
        return

    try:
        df = ler_planilha_sankhya(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler a planilha: {e}")
        return

    resultado = aplicar_filtros(df)
    resumo = agrupar_para_planilha_resumo(resultado.df_validos)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Títulos brutos", f"{resultado.total_brutos:,}")
    col2.metric("Títulos válidos", f"{resultado.total_validos:,}")
    col3.metric("Clientes excluídos por #PROT", f"{resultado.clientes_excluidos_prot:,}")
    col4.metric("Linhas resumo", f"{len(resumo):,}")

    if resumo.empty:
        st.warning("Nenhum título elegível após os filtros.")
        return

    st.markdown("### 📋 Prévia da planilha gerada")
    _mostrar_previa_resumo(resumo)

    data = gerar_excel_resumo(resumo)
    nome_saida = f"Passo2_Confirmacao_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    st.download_button(
        label="⬇️ Baixar Planilha do Passo 2",
        data=data,
        file_name=nome_saida,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )


def _renderizar_passo3(usuario):
    st.subheader("Passo 3 — Gerar Arquivo do Cartório")
    st.markdown(
        """
        Suba a **mesma planilha completa** do Passo 2.
        O sistema seleciona os títulos com base no montante:

        - **até R$ 10.000** → 2 títulos por cliente
        - **R$ 10.000 a R$ 30.000** → 4 títulos por cliente
        - **acima de R$ 30.000** → 5 títulos por cliente

        Seleciona os de maior valor (desempate por maior atraso) e gera
        um arquivo `.txt` agrupado por **Empresa 1/2 × Banco**.
        """
    )

    arquivo = st.file_uploader(
        "Planilha do Sankhya completa (.xls ou .xlsx)",
        type=["xls", "xlsx"],
        key="passo3_uploader",
    )

    if arquivo is None:
        return

    try:
        df = ler_planilha_sankhya(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler a planilha: {e}")
        return

    resultado = aplicar_filtros(df)
    p3 = selecionar_titulos_passo3(resultado.df_validos)

    col1, col2, col3 = st.columns(3)
    col1.metric("Clientes selecionados", f"{p3.total_clientes:,}")
    col2.metric("Títulos selecionados", f"{p3.total_titulos:,}")
    col3.metric("Valor total", f"{fmt_real(p3.valor_total)}")

    if not p3.grupos:
        st.warning("Nenhum título selecionado.")
        return

    st.markdown("### 📋 Grupos gerados")
    for chave, nros in sorted(p3.grupos.items()):
        st.write(f"**{chave}** — {len(nros)} título(s)")

    txt = gerar_txt_passo3(p3.grupos)
    with st.expander("📄 Ver conteúdo do arquivo .txt"):
        st.code(txt, language="text")

    nome_saida = f"Passo3_Cartorio_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"

    col_dl, col_save = st.columns(2)

    with col_dl:
        st.download_button(
            label="⬇️ Baixar arquivo .txt do cartório",
            data=txt.encode("utf-8"),
            file_name=nome_saida,
            mime="text/plain",
            type="primary",
        )

    with col_save:
        if st.button("💾 Salvar remessa no sistema",
                     type="secondary",
                     use_container_width=True,
                     help="Cadastra os clientes e a remessa no banco de dados"):
            _salvar_remessa_no_banco(p3, nome_saida, usuario)


def _salvar_remessa_no_banco(p3, nome_arquivo: str, usuario):
    """
    Persiste clientes, remessa e títulos no banco.
    Cria cadastros novos ou atualiza existentes.
    """
    from src.banco.conexao import obter_conexao
    from src.banco import repo_cliente

    conn = obter_conexao()
    mes_ref = datetime.now().strftime("%Y-%m")

    try:
        # 1) Cria a remessa
        cur = conn.execute(
            "INSERT INTO remessa_protesto "
            "(mes_referencia, nome_arquivo_gerado, total_clientes, "
            "total_titulos, valor_total, usuario_id) "
            "VALUES (?, ?, ?, ?, ?, ?);",
            (mes_ref, nome_arquivo, p3.total_clientes,
             p3.total_titulos, p3.valor_total, usuario.id)
        )
        remessa_id = cur.lastrowid

        # 2) Upsert dos clientes + cria títulos
        clientes_criados = 0
        clientes_atualizados = 0

        for _, row in p3.df_selecionados.iterrows():
            import pandas as pd
            cod_parc = int(row["Parceiro"]) if pd.notna(row["Parceiro"]) else None
            nome = str(row["Nome Parceiro (Parceiro)"]).strip()

            # Verifica se já existia
            existia = conn.execute(
                "SELECT 1 FROM cliente_protesto "
                "WHERE LOWER(nome) = LOWER(?) LIMIT 1;",
                (nome,)
            ).fetchone() is not None

            cliente_id = repo_cliente.upsert_cliente(
                nome=nome,
                cod_parceiro=cod_parc,
            )

            if existia:
                clientes_atualizados += 1
            else:
                clientes_criados += 1

            # Status PROTESTADO
            repo_cliente.atualizar_status_protesto(cliente_id, "PROTESTADO")

            # Cria título
            from src.servicos.filtragem_sankhya import classificar_empresa
            empresa_lle = classificar_empresa(row["Empresa"], row["Vendedor"])
            nro_unico = str(int(row["Nro Único"])) if pd.notna(row["Nro Único"]) else ""

            conn.execute(
                "INSERT INTO titulo_protesto "
                "(cliente_id, remessa_id, nro_unico, nro_nota, empresa, empresa_cod, "
                "vendedor_cod, vendedor_nome, banco_descricao, valor, "
                "atraso_dias, historico) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                (
                    cliente_id, remessa_id, nro_unico,
                    str(int(row["Nro Nota"])) if pd.notna(row.get("Nro Nota")) else None,
                    empresa_lle,
                    int(row["Empresa"]) if pd.notna(row["Empresa"]) else None,
                    int(row["Vendedor"]) if pd.notna(row.get("Vendedor")) else None,
                    str(row.get("Apelido", "")) if pd.notna(row.get("Apelido")) else None,
                    str(row.get("Descrição (Banco)", "")) if pd.notna(row.get("Descrição (Banco)")) else None,
                    float(row["Vlr do Desdobramento"]),
                    int(row["Atraso (dias)"]) if pd.notna(row.get("Atraso (dias)")) else None,
                    str(row.get("Histórico", "")) if pd.notna(row.get("Histórico")) else None,
                )
            )

        st.success(
            f"✅ Remessa salva! "
            f"{clientes_criados} cliente(s) novo(s), "
            f"{clientes_atualizados} atualizado(s), "
            f"{p3.total_titulos} título(s)."
        )
        st.info("Veja em **📋 Lista de Protesto** e **👥 Clientes**.")
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}")
        st.exception(e)
