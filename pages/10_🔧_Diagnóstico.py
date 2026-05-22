"""
Página de Diagnóstico do Banco.

Mostra o estado atual das tabelas e permite ao ADMIN resetar o banco
caso esteja em estado inconsistente.
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.estilo import aplicar_css_lle
from src.banco.schema import inicializar_banco

st.set_page_config(page_title="Diagnóstico · LLE", page_icon="🔧", layout="wide")

# NÃO chama inicializar_banco — essa página é pra diagnosticar problemas no banco
aplicar_css_lle()

# Verificar login manualmente (sem o auth_guard padrão, pra evitar query no banco)
usuario = st.session_state.get("usuario_atual")
if usuario is None:
    st.error("🔒 Faça login antes para acessar o diagnóstico.")
    st.page_link("app.py", label="← Ir para o login")
    st.stop()

from src.modelos.tipos import PerfilUsuario
if usuario.perfil != PerfilUsuario.ADMIN:
    st.error("🔒 Apenas a Gestão pode acessar esta página.")
    st.stop()

st.title("🔧 Diagnóstico do Banco")
st.caption("Estado atual das tabelas e ferramentas de reparo.")
st.markdown("---")

from src.banco.conexao import obter_conexao, usar_postgres

conn = obter_conexao()
modo = "Postgres (Nuvem)" if usar_postgres() else "SQLite (Local)"
st.info(f"**Modo do banco:** {modo}")

st.markdown("### 📊 Tabelas")

tabelas_esperadas = [
    "schema_versao", "usuario", "parametros_sistema", "log_auditoria",
    "cliente_protesto", "upload_sankhya", "remessa_protesto",
    "titulo_protesto", "andamento_protesto", "historico_andamento",
    "evento_serasa", "titulo_serasa",
]

for t in tabelas_esperadas:
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {t};").fetchone()
        count = row[0]
        st.success(f"✅ `{t}` — {count} registro(s)")
    except Exception as e:
        st.error(f"❌ `{t}` — ERRO: {str(e)[:200]}")

st.markdown("---")
st.markdown("### 🔢 Versão do schema")

try:
    row = conn.execute("SELECT MAX(versao) FROM schema_versao;").fetchone()
    st.write(f"**Versão atual:** {row[0]}")
except Exception as e:
    st.write(f"**Erro lendo versão:** {e}")

st.markdown("---")
st.markdown("### 🔧 Ações")

st.warning(
    "⚠️ **Aplicar migrations agora**: tenta recriar todas as tabelas "
    "que não existirem. Não apaga dados existentes."
)
if st.button("🔄 Aplicar migrations agora"):
    try:
        inicializar_banco()
        st.success("✅ Migrations aplicadas com sucesso! Recarregue a página.")
    except Exception as e:
        st.error(f"❌ Erro ao aplicar migrations: {e}")
        st.exception(e)

st.markdown("---")
st.error(
    "🔴 **RESET TOTAL**: Apaga TODAS as tabelas e recria do zero. "
    "Todos os dados serão PERDIDOS. Use apenas se o banco estiver "
    "irreversivelmente bagunçado."
)
confirmacao = st.text_input(
    "Digite `RESETAR TUDO` para confirmar:",
    "",
    key="confirm_reset",
)
if st.button("🔴 Resetar banco completamente",
             disabled=(confirmacao != "RESETAR TUDO")):
    try:
        for t in reversed(tabelas_esperadas):
            try:
                conn.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")
            except Exception:
                try:
                    conn.execute(f"DROP TABLE IF EXISTS {t};")
                except Exception:
                    pass

        inicializar_banco()
        st.success("✅ Banco resetado! Faça logout e logue novamente.")
        st.balloons()
    except Exception as e:
        st.error(f"❌ Erro: {e}")
        st.exception(e)
