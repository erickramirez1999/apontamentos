# Guia de Configuração — Neon (Postgres)

Passo a passo para configurar o banco Postgres no Neon e conectar ao app.

## 1. Criar projeto no Neon

1. Acesse <https://neon.tech> e crie conta (free tier dá 3 GB de armazenamento e 100 horas de compute mensal — sobra muito pro porte dos projetos LLE).
2. **Create a project**:
   - **Project name**: `lle-protestos` (ou o nome do seu app)
   - **Postgres version**: 16 (padrão atual)
   - **Region**: `AWS US East (Ohio)` ou `AWS South America (São Paulo)` — escolha São Paulo se preferir menor latência pra usuários brasileiros
3. Após criar, Neon abre direto a tela **Connection Details**.

## 2. Pegar a connection string CERTA

Na tela Connection Details, você vê duas opções:

- **Direct connection** → host SEM `-pooler` no meio (`ep-rapid-rain-12345.us-east-2.aws.neon.tech`)
- **Pooled connection** → host COM `-pooler` (`ep-rapid-rain-12345-pooler.us-east-2.aws.neon.tech`)

**SEMPRE use a Pooled connection.** O Streamlit pode abrir múltiplas conexões simultâneas (múltiplos usuários, múltiplas threads), e o Neon free tier limita conexões diretas. O pooler reaproveita conexões e resolve isso.

Como pegar:

1. Em **Connection Details**, marque a opção **"Pooled connection"** (geralmente um checkbox/toggle no topo)
2. Copie a connection string completa — algo como:
   ```
   postgresql://meuuser:senha123@ep-rapid-rain-12345-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
3. Guarde — a senha aparece só uma vez no Neon. Se perder, gera nova em **Settings → Reset password**.

## 3. Configurar nos Streamlit Secrets

### Localmente (dev)

No arquivo `.streamlit/secrets.toml` (criado a partir do `secrets.toml.example`):

```toml
[postgres]
connection_string = "postgresql://meuuser:senha123@ep-rapid-rain-12345-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
```

### Streamlit Cloud (produção)

1. No painel do app: **Manage app → Settings → Secrets**
2. Cole o mesmo bloco:
   ```toml
   [postgres]
   connection_string = "postgresql://meuuser:senha123@ep-rapid-rain-12345-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
   ```
3. Salve. O app reinicia automaticamente.

## 4. Primeiro deploy

No primeiro `streamlit run` (ou primeiro acesso após o deploy), o app vai:

1. Detectar que existe `[postgres]` nos Secrets → usar Neon
2. Rodar as migrations do `src/banco/schema.py` automaticamente — criando todas as tabelas
3. Pronto pra uso

Você **não precisa rodar SQL manual** no Neon. As migrations cuidam disso.

## 5. Verificar que está funcionando

Após o primeiro acesso:

1. Vá no Neon dashboard → seu projeto → **Tables**
2. Você deve ver: `usuario`, `parametros_sistema`, `schema_versao`, `log_auditoria` + as tabelas específicas do seu projeto
3. Em **SQL Editor**, rode:
   ```sql
   SELECT * FROM schema_versao;
   ```
   Deve mostrar as versões aplicadas.

## 6. Diferenças práticas vs. Supabase

| | Supabase (antigo) | Neon (novo) |
|---|---|---|
| Onde pegar connection string | Project Settings → Database → Transaction Pooler | Dashboard → Connection Details → Pooled |
| Porta | 6543 (pooler) ou 5432 (direct) | 5432 (padrão Postgres) com host `-pooler` |
| Row Level Security | Precisava DISABLE em cada tabela | Não tem RLS — nada a fazer |
| Backup | Daily backup retido 7 dias (free) | Point-in-time restore (até 24h no free) |
| Branching | Não tem | **Tem** — útil pra testar mudanças sem afetar prod |

### Sobre branching no Neon (vantagem nova)

Você pode criar uma "branch" do banco igual git branch — uma cópia instantânea que herda os dados, mas modificações ficam isoladas. Útil pra:

- Testar uma migration nova sem risco
- Rodar QA com dados de produção
- Reverter pro estado anterior se quebrar algo

Como criar: dashboard → **Branches** → **Create branch**. Cada branch tem sua própria connection string.

## 7. Custos e limites

**Free tier do Neon (em 2026):**

- 0,5 GB de storage (pode estender pra 3 GB no Launch tier pago)
- 100 horas de compute/mês (suficiente pra tráfego baixo-médio)
- Auto-suspend depois de 5 min sem atividade — primeira request "fria" pode demorar 1-2 segundos (depois fica rápido enquanto tem tráfego)
- 10 branches

Pra projetos LLE (operação interna de equipe pequena), o free tier deve sobrar — diferente do Supabase, onde 500 MB acabaram virando problema.

**Monitorar uso:** Dashboard → **Usage**. Se aproximar dos limites, o próximo tier (Launch) custa em torno de $19/mês.

## 8. Problemas comuns

### "FATAL: too many connections for role"
- Causa: usou Direct connection em vez de Pooled
- Solução: trocar pra connection string com `-pooler` no host

### "SSL connection required"
- Causa: faltou `?sslmode=require` no final da connection string
- Solução: adicionar ao final da URL

### App lento na primeira request
- Causa: auto-suspend do Neon (banco fica "dormindo" depois de inatividade)
- Solução normal: aguardar 1-2 segundos da primeira request — depois fica rápido
- Solução opcional: upgrade pro Launch tier (sempre ligado)

### Migrations não rodaram
- Sintoma: erro de "table doesn't exist" no primeiro uso
- Causa: provavelmente o app não chegou a chamar `inicializar_banco()` no startup
- Solução: conferir se `app.py` tem o bloco de inicialização no topo. Reiniciar o app force a primeira passagem.
