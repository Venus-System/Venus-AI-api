# venus-api-ai

API de integração entre aplicações e agentes de IA do Venus

## Instalação

Na raiz do projeto, execute:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r venus_api/requirements.txt
```

## Testes

Com o ambiente virtual ativado, execute:

```powershell
python -m pytest
```

## Configuração

As variáveis vão num arquivo `.env` na raiz (local) ou no gerenciador de
segredos do ambiente (nuvem). Nenhuma é obrigatória para a API subir, mas sem
elas parte das funções fica desligada.

| Variável | Para quê | Sem ela |
|---|---|---|
| `GEMINI_API_KEY`, `GROQ_API_KEY` | Chaves dos modelos de linguagem | A Venus só devolve a mensagem de reserva |
| `FIREBASE_CREDENTIALS` | Conta de serviço do Firebase: **caminho** do JSON (local) ou o **conteúdo** do JSON (nuvem) | O chat recusa todas as mensagens |
| `MONGODB_URL` | Histórico de conversa, memória de longo prazo e métricas | Tudo em RAM, perdido ao reiniciar |
| `DATABASE_URL` | Postgres do CRUD (produto, ingrediente, alergia) | Esses especialistas avisam que não conseguiram consultar |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` | Rastreamento no Langfuse | Sem rastreamento |
| `A2A_API_KEY`, `A2A_BASE_URL` | Servidor A2A em `/a2a` (chave no header `X-API-Key`; a URL pública da API, sem barra no fim) | Servidor A2A desligado — precisa das duas |

## Subir a API

```powershell
python -m uvicorn venus_api.app.main:app --env-file .env
```

O `--env-file` é necessário: o SDK lê as chaves dos modelos no momento em que
é importado.

## Imagem Docker

```powershell
docker build -t venus-api .
```

A imagem escuta na porta `8080`; o health check é `GET /v1/health`.
