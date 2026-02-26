# Fase 1 — Coletor de Métricas (YouTube, X e Instagram)

Agora o projeto está em modo **Vercel-first** para você controlar tudo por endpoints.

## O que foi implementado

- `phase1_collector.py`: núcleo da coleta (YouTube, X, Instagram) + persistência.
- `api/collect.py`: endpoint serverless para coletar métricas.
- `api/report.py`: endpoint serverless para consultar top posts.
- `vercel.json`: runtime Python + cron diário (compatível com plano Hobby).

## 1) Rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python phase1_collector.py --action all
```

## 2) Variáveis de ambiente

Preencha no `.env` (local) e também no painel da Vercel (produção):

- `YOUTUBE_API_KEY`, `YOUTUBE_CHANNEL_ID`
- `X_BEARER_TOKEN`, `X_USER_ID`
- `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`
- `CRON_SECRET` (protege o endpoint `/api/collect`)
- `DB_PATH` (opcional; default `social_metrics.db`)

> Instagram exige conta Business/Creator.

## 3) Endpoints na Vercel

### `GET /api/collect`
Executa coleta.

- Header recomendado: `Authorization: Bearer $CRON_SECRET`
- Query opcional: `max_posts=10`

Exemplo:

```bash
curl -H "Authorization: Bearer $CRON_SECRET" "https://SEU-PROJETO.vercel.app/api/collect?max_posts=12"
```

### `GET /api/report`
Retorna top posts por plataforma.

- Query opcional: `limit=5`

Exemplo:

```bash
curl "https://SEU-PROJETO.vercel.app/api/report?limit=5"
```

## 4) Cron na Vercel (Hobby x Pro)

- **Hobby**: apenas cron diário (1x/dia).
- **Pro**: pode usar cron múltiplas vezes por dia (ex.: a cada 6 horas).

Neste repositório, o `vercel.json` está configurado para **diário**: `0 9 * * *`.

## 5) Deploy na Vercel (direto e simples)

1. Suba este repo no GitHub.
2. Na Vercel: **New Project** → importe o repositório.
3. Em **Environment Variables**, adicione todas as variáveis do `.env.example` + `CRON_SECRET`.
4. Faça deploy.
5. Teste `/api/collect` e `/api/report`.

## 6) Observação importante sobre banco na Vercel

`SQLite` em serverless é útil para testes, mas não é persistência ideal em produção.
Para produção real, próximo passo recomendado é trocar para um banco gerenciado (Postgres/Supabase/Turso).


## 7) "Destravar" Git local para facilitar controle por aqui

Se o seu ambiente estiver com hooks/regras locais atrapalhando commits, você pode usar estas opções no seu terminal:

```bash
# Ignorar hooks apenas no commit atual
git commit --no-verify -m "sua mensagem"

# Desativar hooks localmente para este repositório
git config core.hooksPath /dev/null

# Reativar hooks padrão depois, se quiser
git config --unset core.hooksPath
```

> Isso afeta só seu ambiente local/repositório atual.
