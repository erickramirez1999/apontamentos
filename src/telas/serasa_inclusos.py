"""Tela Serasa › Inclusos."""
from __future__ import annotations

import streamlit as st

from src.utils.marca import AZUL_ESCURO
from src.utils.estilo import COR_AZUL
from src.telas.serasa_componentes import listar_eventos_serasa


def renderizar(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO};margin-bottom:4px;'>📥 Serasa — Inclusos</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Arquivos de Inclusão enviados ao Serasa.")
    listar_eventos_serasa(
        tipo="INCLUSAO",
        usuario=usuario,
        cor=COR_AZUL,
        icone="📥",
        chave_prefix="del_serasa_inc",
    )
