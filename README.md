# Fase 1 — Coletor de Métricas (YouTube, X e Instagram)

Script Python para:
- inicializar banco SQLite local;
- coletar métricas básicas das 3 redes (quando credenciais existirem);
- salvar snapshots de conta e posts;
- mostrar top posts por engajamento.

## 1) Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2) Configurar credenciais

Edite o arquivo `.env` com suas chaves:
- `YOUTUBE_API_KEY`, `YOUTUBE_CHANNEL_ID`
- `X_BEARER_TOKEN`, `X_USER_ID`
- `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`

> Instagram precisa de conta Business/Creator para Graph API.

## 3) Executar

Tudo em um comando (init + coleta + relatório):

```bash
python phase1_collector.py --action all
```

Comandos separados:

```bash
python phase1_collector.py --action init-db
python phase1_collector.py --action collect --max-posts 15
python phase1_collector.py --action report
```

## 4) Estrutura SQLite

- `account_metrics`: snapshots de seguidores por plataforma.
- `post_metrics`: snapshots de posts/vídeos e métricas de engajamento.

Banco padrão: `social_metrics.db`.

## 5) Próximo passo (Fase 2)

Adicionar camada de análise com LLM (OpenAI/Claude) para:
- detectar melhor horário;
- identificar padrões de conteúdo;
- gerar relatório semanal automático.
