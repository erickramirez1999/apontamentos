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

# Aplica menu customizado (sem inicializar banco)
from src.utils.auth_guard import aplicar_layout_logado
aplicar_layout_logado(usuario)

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
    "upload_cartorio", "titulo_cartorio",
]

for t in tabelas_esperadas:
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {t};").fetchone()
        count = row[0]
        st.success(f"✅ `{t}` — {count} registro(s)")
    except Exception as e:
        st.error(f"❌ `{t}` — ERRO: {str(e)[:200]}")

st.markdown("---")
st.markdown("### 💰 Auditoria do dashboard")
st.caption(
    "Mostra de onde vem o 'Valor total em Protesto' do dashboard — "
    "pra você poder conferir se a soma faz sentido."
)

try:
    # Stats da titulo_cartorio
    row = conn.execute(
        "SELECT "
        "COUNT(*) as total, "
        "SUM(CASE WHEN cancelado = 0 THEN 1 ELSE 0 END) as ativos, "
        "SUM(CASE WHEN cancelado = 1 THEN 1 ELSE 0 END) as cancelados, "
        "COALESCE(SUM(CASE WHEN cancelado = 0 THEN valor ELSE 0 END), 0) as soma_valor, "
        "COALESCE(SUM(CASE WHEN cancelado = 0 THEN saldo ELSE 0 END), 0) as soma_saldo "
        "FROM titulo_cartorio;"
    ).fetchone()

    st.write(f"**Títulos no cartório (total):** {row['total']}")
    st.write(f"**Ativos (entram no Valor total em Protesto):** {row['ativos']}")
    st.write(f"**Cancelados/Pagos (não entram):** {row['cancelados']}")
    st.write(f"**Soma de 'valor' dos ativos:** R$ {float(row['soma_valor']):,.2f}")
    st.write(f"**Soma de 'saldo' dos ativos:** R$ {float(row['soma_saldo']):,.2f}")

    # Verifica duplicatas por protocolo
    dups = conn.execute(
        "SELECT protocolo, cartorio, COUNT(*) as n FROM titulo_cartorio "
        "GROUP BY protocolo, cartorio HAVING COUNT(*) > 1 "
        "ORDER BY COUNT(*) DESC;"
    ).fetchall()

    if dups:
        st.warning(
            f"⚠️ **{len(dups)} protocolo(s) duplicado(s)** "
            f"(somam dinheiro em duplicidade no dashboard!):"
        )
        for d in dups[:10]:
            st.caption(f"  - Protocolo {d['protocolo']} aparece {d['n']}x")
        if len(dups) > 10:
            st.caption(f"  ... e mais {len(dups) - 10}")
    else:
        st.success("✓ Sem protocolos duplicados em titulo_cartorio.")

    # Uploads do cartório
    rows = conn.execute(
        "SELECT id, nome_arquivo, total_linhas, criado_em "
        "FROM upload_cartorio ORDER BY criado_em DESC;"
    ).fetchall()
    if rows:
        st.write(f"**Uploads de cartório no histórico ({len(rows)}):**")
        for r in rows:
            st.caption(
                f"  - #{r['id']} `{r['nome_arquivo']}` — "
                f"{r['total_linhas']} título(s) em {str(r['criado_em'])[:16]}"
            )
except Exception as e:
    st.error(f"❌ Erro lendo auditoria: {e}")

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
st.markdown("### 🔄 Reprocessar cadastros")
st.info(
    "Use isso se você subiu arquivos Serasa em uma versão anterior do sistema "
    "(antes da persistência automática) e os clientes não aparecem em **👥 Clientes**. "
    "Esse botão lê os títulos já carregados e cria os cadastros faltantes."
)

if st.button("🔄 Reprocessar eventos Serasa (gerar cadastros faltantes)"):
    try:
        from src.servicos.reprocessar import reprocessar_eventos_serasa
        resultado = reprocessar_eventos_serasa()
        st.success(
            f"✅ Reprocessado!\n\n"
            f"- Títulos processados: **{resultado['titulos_processados']}**\n"
            f"- Clientes novos criados: **{resultado['clientes_criados']}**\n"
            f"- Clientes já existentes atualizados: **{resultado['clientes_atualizados']}**\n"
            f"- Status Serasa atualizados: **{resultado['status_atualizados']}**"
        )
        st.balloons()
    except Exception as e:
        st.error(f"❌ Erro: {e}")
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
