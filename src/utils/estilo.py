"""
Aplicação do CSS LLE no Streamlit.

Carrega Montserrat do Google Fonts + variáveis de cor + overrides nos
componentes. Inclui o FIX dos ícones Material do Streamlit (bug onde o
nome cru do ícone aparece como texto, sobrepondo o label do botão).

Chamar `aplicar_css_lle()` uma vez por página.
"""
from __future__ import annotations

import streamlit as st

from src.utils.marca import (
    AZUL_ESCURO, AMARELO, VERDE, AZUL_VIVO, BRANCO,
    FUNDO_ATRASO, TEXTO_ATRASO, FUNDO_PAGO, TEXTO_PAGO,
    FUNDO_PARCIAL, TEXTO_PARCIAL, LINHA_ALTERNADA, BORDA_FINA,
    CINZA_CLARO, CINZA_MEDIO,
)


def aplicar_css_lle():
    """Injeta CSS global. Chamar uma vez por página."""
    st.markdown(f"""
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --lle-azul-escuro: {AZUL_ESCURO};
            --lle-amarelo: {AMARELO};
            --lle-verde: {VERDE};
            --lle-azul-vivo: {AZUL_VIVO};
            --lle-branco: {BRANCO};
            --lle-fundo-atraso: {FUNDO_ATRASO};
            --lle-texto-atraso: {TEXTO_ATRASO};
            --lle-fundo-pago: {FUNDO_PAGO};
            --lle-texto-pago: {TEXTO_PAGO};
            --lle-fundo-parcial: {FUNDO_PARCIAL};
            --lle-texto-parcial: {TEXTO_PARCIAL};
            --lle-linha-alt: {LINHA_ALTERNADA};
            --lle-borda: {BORDA_FINA};
            --lle-cinza-claro: {CINZA_CLARO};
            --lle-cinza-medio: {CINZA_MEDIO};
        }}

        /* Fonte global */
        html, body, [class*="css"], [class*="st-"], button, input, select, textarea {{
            font-family: 'Montserrat', Calibri, Arial, sans-serif !important;
        }}

        /* Títulos */
        h1, h2, h3, h4, h5 {{
            color: var(--lle-azul-escuro) !important;
            font-weight: 700 !important;
        }}

        /* Botões primários */
        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"],
        button[data-testid="baseButton-primary"] {{
            background-color: var(--lle-azul-escuro) !important;
            color: var(--lle-branco) !important;
            border: none !important;
            font-weight: 600 !important;
            border-radius: 6px !important;
        }}
        .stButton > button[kind="primary"]:hover {{
            background-color: var(--lle-azul-vivo) !important;
        }}

        /* Botões secundários */
        .stButton > button[kind="secondary"] {{
            border: 1.5px solid var(--lle-azul-escuro) !important;
            color: var(--lle-azul-escuro) !important;
            font-weight: 600 !important;
            background-color: var(--lle-branco) !important;
        }}

        /* Sidebar — fundo azul institucional */
        section[data-testid="stSidebar"] {{
            background-color: var(--lle-azul-escuro) !important;
        }}
        section[data-testid="stSidebar"] * {{
            color: var(--lle-branco) !important;
        }}
        section[data-testid="stSidebar"] .stButton > button {{
            background-color: rgba(255,255,255,0.08) !important;
            color: var(--lle-branco) !important;
            border: 1px solid rgba(255,255,255,0.2) !important;
        }}
        section[data-testid="stSidebar"] .stButton > button:hover {{
            background-color: var(--lle-amarelo) !important;
            color: var(--lle-azul-escuro) !important;
            border-color: var(--lle-amarelo) !important;
        }}

        /* === FIX GLOBAL: ÍCONES MATERIAL QUEBRADOS NOS BOTÕES NATIVOS ===
           Streamlit usa Material Symbols que às vezes não carregam, mostrando
           o nome do ícone como texto cru (ex: "upload", "download",
           "keyboard_double_arrow_right"). Esse texto fica sobrepondo o
           label real do botão.

           A regra abaixo identifica esses ícones (que têm classes específicas)
           e força que o nome do ícone NUNCA apareça como texto - quando a
           fonte Material não carrega, fica simplesmente invisível.
        */
        span[data-testid="stIconMaterial"],
        span.material-icons,
        span.material-symbols-outlined,
        span.material-symbols-rounded,
        span[class*="stIconMaterial"] {{
            font-family: 'Material Symbols Outlined', 'Material Symbols Rounded',
                         'Material Icons' !important;
            font-weight: normal !important;
            font-style: normal !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            display: inline-block !important;
            white-space: nowrap !important;
            word-wrap: normal !important;
            direction: ltr !important;
            -webkit-font-feature-settings: 'liga' !important;
            -webkit-font-smoothing: antialiased !important;
        }}
        @supports not (font-variation-settings: normal) {{
            span[data-testid="stIconMaterial"],
            span.material-icons,
            span.material-symbols-outlined,
            span.material-symbols-rounded {{
                color: transparent !important;
                font-size: 0 !important;
            }}
        }}
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=block');

        /* Botão de toggle da sidebar — substitui o ícone Material por seta unicode */
        button[data-testid="collapsedControl"] {{
            background: var(--lle-azul-escuro) !important;
            border: 1px solid var(--lle-amarelo) !important;
            border-radius: 6px !important;
            color: var(--lle-amarelo) !important;
            padding: 6px 10px !important;
            font-size: 0 !important;
            min-width: 36px !important;
            min-height: 36px !important;
        }}
        button[data-testid="collapsedControl"] * {{
            font-size: 0 !important;
            color: transparent !important;
        }}
        button[data-testid="collapsedControl"]::before {{
            content: "☰" !important;
            font-size: 20px !important;
            color: var(--lle-amarelo) !important;
            display: inline-block !important;
            line-height: 1 !important;
        }}
        button[data-testid="collapsedControl"]:hover {{
            background: var(--lle-amarelo) !important;
        }}
        button[data-testid="collapsedControl"]:hover::before {{
            color: var(--lle-azul-escuro) !important;
        }}

        /* File uploader — visual LLE */
        section[data-testid="stFileUploaderDropzone"] {{
            border: 2px dashed var(--lle-azul-escuro) !important;
            border-radius: 8px !important;
            background-color: #F8F9FA !important;
            padding: 16px !important;
        }}
        section[data-testid="stFileUploaderDropzone"]:hover {{
            border-color: var(--lle-azul-vivo) !important;
            background-color: #EFF6FF !important;
        }}
        section[data-testid="stFileUploaderDropzone"] button {{
            background-color: var(--lle-azul-escuro) !important;
            color: var(--lle-branco) !important;
            border: none !important;
            border-radius: 6px !important;
            padding: 8px 20px !important;
            font-weight: 600 !important;
        }}

        /* Cards de métrica */
        div[data-testid="stMetricValue"] {{
            color: var(--lle-azul-escuro) !important;
            font-weight: 700 !important;
        }}
        div[data-testid="stMetricLabel"] {{
            color: var(--lle-cinza-medio) !important;
            font-weight: 500 !important;
        }}

        /* Tabelas */
        .stDataFrame thead th {{
            background-color: var(--lle-azul-escuro) !important;
            color: var(--lle-branco) !important;
            font-weight: 600 !important;
        }}

        /* Inputs */
        .stTextInput input, .stNumberInput input, .stDateInput input, .stSelectbox select {{
            border-radius: 6px !important;
            border: 1.5px solid var(--lle-borda) !important;
        }}

        /* Diminui padding superior */
        .block-container {{
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
            max-width: 1400px;
        }}

        /* Header limpo + esconde "Made with Streamlit" */
        header[data-testid="stHeader"] {{ background: transparent; }}
        footer {{ visibility: hidden; }}
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# HELPERS DE CARDS PARA DASHBOARDS
# ============================================================

def card_kpi(titulo: str, valor: str, sublabel: str = "", cor: str = "#0071FE",
             icone: str = "") -> str:
    """
    Card de KPI estilo plataforma de referência.

    Use com st.markdown(card_kpi(...), unsafe_allow_html=True)
    """
    return f"""
    <div style="background:#FFF; border-left:5px solid {cor};
                padding:14px 18px; border-radius:8px;
                box-shadow:0 1px 4px rgba(0,0,0,0.08); height:105px;
                margin-bottom:8px;">
        <div style="font-size:12px; color:#666; font-weight:600; margin-bottom:6px;">
            {icone} {titulo}
        </div>
        <div style="font-size:22px; font-weight:800; color:{cor}; line-height:1.1;">
            {valor}
        </div>
        <div style="font-size:11px; color:#999; margin-top:4px;">{sublabel}</div>
    </div>
    """


# Cores padrão pra KPIs
COR_AZUL = "#0071FE"
COR_VERDE = "#0F8C3B"
COR_LARANJA = "#FF8C00"
COR_VERMELHO = "#DC3545"
COR_CINZA = "#6C757D"
COR_AMARELO = "#FAC318"
