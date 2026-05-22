"""
Função utilitária para proteção de páginas — LLE Protestos.
"""
from __future__ import annotations
from pathlib import Path
import streamlit as st


CSS_SIDEBAR_FIXA = """
<style>
    section[data-testid="stSidebar"] {
        min-width: 260px !important;
        max-width: 260px !important;
        width: 260px !important;
        transform: translateX(0px) !important;
        visibility: visible !important;
        margin-left: 0 !important;
    }
    section[data-testid="stSidebar"] button[kind="header"],
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
    section[data-testid="stSidebar"] [data-testid="stSidebarCollapseControl"],
    button[data-testid="collapsedControl"],
    button[data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarUserContent"] button[kind="header"] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
        width: 0 !important;
        height: 0 !important;
        opacity: 0 !important;
    }
    [data-testid="stSidebarNav"] { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    .main .block-container {
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
</style>
"""


def exigir_login_ou_parar():
    usuario = st.session_state.get("usuario_atual")
    if usuario is None:
        st.markdown(
            """
            <style>
                section[data-testid="stSidebar"] { display: none !important; }
                [data-testid="stSidebarNav"] { display: none !important; }
                button[kind="header"] { display: none !important; }
                button[data-testid="collapsedControl"] { display: none !important; }
                header[data-testid="stHeader"] { display: none !important; }
                div[data-testid="stToolbar"] { display: none !important; }
                .block-container {
                    padding-top: 4rem !important;
                    max-width: 600px !important;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.warning("🔒 **Acesso restrito.** Faça login para acessar essa página.")
        st.page_link("app.py", label="← Ir para o login", icon="🏠")
        st.stop()

    st.markdown(CSS_SIDEBAR_FIXA, unsafe_allow_html=True)
    _renderizar_menu_sidebar(usuario)
    return usuario


def _renderizar_menu_sidebar(usuario):
    from src.modelos.tipos import PerfilUsuario
    from src.utils.traducoes import traduzir_perfil
    from src.utils.permissoes import pode_editar, pode_visualizar_admin

    LOGO_BRANCO = Path(__file__).parent.parent.parent / "assets" / "logo_lle_branco.png"
    LOGO_COR = Path(__file__).parent.parent.parent / "assets" / "logo_lle.png"
    logo_a_usar = LOGO_BRANCO if LOGO_BRANCO.exists() else LOGO_COR

    with st.sidebar:
        if logo_a_usar.exists():
            st.image(str(logo_a_usar), use_container_width=True)
        st.markdown("---")
        st.markdown(f"👤 **{usuario.nome}**")
        st.caption(f"Perfil: {traduzir_perfil(usuario.perfil.value)}")
        st.page_link("pages/0_👤_Meu_Perfil.py", label="👤 Meu Perfil")
        st.markdown("---")

        # Menu principal
        st.markdown("**Menu**")
        st.page_link("pages/1_🏠_Início.py", label="🏠 Início")
        st.page_link("pages/2_👥_Clientes.py", label="👥 Clientes")

        # Seção Protesto
        st.markdown("---")
        st.markdown("**Protesto**")
        if pode_editar(usuario):
            st.page_link("pages/3_⚖_Protestar.py", label="📤 Protestar")
        st.page_link("pages/4_📋_Lista_de_Protesto.py", label="📋 Lista de Protesto")
        st.page_link("pages/5_📁_Arquivados.py", label="📁 Arquivados")

        # Seção Serasa
        st.markdown("---")
        st.markdown("**Serasa**")
        if pode_editar(usuario):
            st.page_link("pages/6_⬆_Serasa_Carregamento.py", label="📤 Carregamento")
        st.page_link("pages/7_📥_Serasa_Inclusos.py", label="📥 Inclusos")
        st.page_link("pages/8_❌_Serasa_Exclusos.py", label="📤 Exclusos")

        # Área administrativa
        if pode_visualizar_admin(usuario):
            st.markdown("---")
            st.markdown("**Administração**")
            st.page_link("pages/9_🛡_Usuários.py", label="👥 Usuários")
            if usuario.perfil.value == "ADMIN":
                st.page_link("pages/10_🔧_Diagnóstico.py", label="🔧 Diagnóstico")

        st.markdown("---")
        if st.button("🚪 Sair", use_container_width=True,
                     key=f"sair_sidebar_{usuario.id}"):
            for k in list(st.session_state.keys()):
                if k not in ("banco_inicializado",):
                    del st.session_state[k]
            st.rerun()
