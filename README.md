# LLE Protestos

Sistema interno de controle de protestos e Serasa do Grupo LLE Ferragens.

## Funcionalidades

- 🏠 **Início** — Dashboard com métricas de Protesto, Serasa e atividades recentes
- 📤 **Protestar** — Geração da planilha de filtragem inicial (Passo 1), planilha confirmada (Passo 2) e arquivo do cartório (Passo 3)
- 📋 **Lista de Protesto** — Remessas geradas e busca de clientes em protesto
- 📁 **Arquivados** — Clientes que pagaram (com indicador BAIXADO)
- 🔔 **Serasa** — Upload de arquivos CNAB de Inclusão/Exclusão e visualização por dia
- 👥 **Usuários** — Gestão de cadastros (apenas ADMIN e DIRETORIA)

## Perfis

- **ADMIN** (mostrado como "Gestão"): pode tudo (uploads, alterações, gerenciar usuários)
- **OPERADOR**: pode editar (uploads, alterar status)
- **DIRETORIA**: só visualiza, pode ver usuários
- **FINANCEIRO** (Setor Financeiro): só visualiza

## Filtros aplicados (Sankhya)

- Atraso entre 60 e 364 dias
- `#PROT` no histórico → exclui cliente inteiro
- `ACORDO` isolado → bloqueia título (`QUEBRA DE ACORDO` NÃO bloqueia)
- `DV TOTAL`, `#Ticket`, `CHAMADO`, `TMK` → bloqueiam título
- Terceirizadas (`RENNOVARE`, `KNOWHOW`, `SOLUTE`) sem `DV` → bloqueiam título

## Passo 3 — Seleção pro cartório

Limite de títulos por cliente baseado no montante total:
- até R$ 10.000 → 2 títulos
- R$ 10.000 a R$ 30.000 → 4 títulos
- acima de R$ 30.000 → 5 títulos

Seleção: maiores valores; desempate por maior atraso.

Saída: arquivo `.txt` agrupado por Empresa (1/2) × Banco (Santander/Bradesco/etc).

## Stack

- Streamlit
- Python 3.11+
- Banco: SQLite (dev) / Postgres (produção, ex: Neon)
- bcrypt (autenticação)
- pandas + openpyxl + xlrd (leitura/geração de planilhas)

## Configuração

Veja [`docs/NEON.md`](docs/NEON.md) para configurar o banco Postgres.

Localmente, o sistema usa SQLite em `.streamlit/data/lle.db` (criado automaticamente).
