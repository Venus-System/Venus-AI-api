# venus-api-ai

API de integração entre aplicações e agentes de IA do Venus

Arquitetura do sistema (componentes e o caminho de uma mensagem): [`docs/arquitetura-sistema.md`](docs/arquitetura-sistema.md).

## Instalação

Na raiz do projeto, execute:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r venus_api/requirements-dev.txt
```

`requirements.txt` tem só o que vai para produção (é o que a imagem Docker
instala); `requirements-dev.txt` acrescenta `pytest` e `httpx`. O SDK é
instalado por **tag** (`@v0.2.0`), não por branch — para atualizar, siga o
processo de release do README do SDK e troque a tag. A suíte roda contra o
SDK instalado assim (nunca `pip install -e` de um checkout local), e
`tests/test_versao_sdk.py` falha se a versão instalada for menor que a 0.2.0
ou não tiver as correções do guardrail.

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
| `GROQ_API_KEY`, `MISTRAL_API_KEY`, `GEMINI_API_KEY` | Chaves dos modelos de linguagem (cadeia com fallback entre os provedores que tiverem chave) | Sem nenhuma, a Venus só devolve a mensagem de reserva |
| `FIREBASE_CREDENTIALS` | Conta de serviço do Firebase: **caminho** do JSON (local) ou o **conteúdo** do JSON (nuvem) | O chat recusa todas as mensagens |
| `MONGODB_URL` | Histórico de conversa, memória de longo prazo, métricas e contador do limite de mensagens | Histórico e memória em RAM (perdidos ao reiniciar), métricas não são gravadas e o limite conta por instância |
| `DATABASE_URL` | Postgres do CRUD (produto, ingrediente, alergia) e identificação do usuário pelo `uid` do Firebase (`venus.users.firebase_uid`) | Esses especialistas avisam que não conseguiram consultar, e a conversa fica sem os dados da conta (favoritos, alergias) |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` | Rastreamento no Langfuse | Sem rastreamento |
| `A2A_API_KEY`, `A2A_BASE_URL` | Servidor A2A em `/a2a` (chave no header `X-API-Key`; a URL pública da API, sem barra no fim) | Servidor A2A desligado — precisa das duas |
| `FAQ_DIR` | Outra pasta com documentos do FAQ para o RAG do agente FAQ | Usa os documentos empacotados no SDK instalado (`venus_sdk/data/faq`, mantidos no repositório do SDK) |
| `QDRANT_URL`, `QDRANT_API_KEY` | Coleção do FAQ no Qdrant (alimentada pela ingestão do SDK: `python -m venus_sdk.rag.faq_ingest`) | Índice local em memória sobre `FAQ_DIR`: **FastEmbed** quando o extra `rag` está instalado e o modelo foi baixado (na imagem Docker ele já vem); senão **`EmbeddingsHash`** (busca por palavras, não semântica), com aviso no log. O log do startup diz qual subiu (`Índice do FAQ: IndiceRAG/FastEmbed`) |
| `FASTEMBED_CACHE_PATH` | Pasta do modelo de embeddings (~220 MB). Na imagem Docker já vem `/modelos/fastembed`, com o modelo baixado no build (e `HF_HUB_OFFLINE=1`) | Fora da imagem: o modelo é baixado no primeiro uso, o que precisa de rede; sem rede, o índice local cai no `EmbeddingsHash` |
| `VENUS_GUARDRAIL_LLM` | Segunda camada do guardrail de entrada: um LLM rápido classifica o que a regex deixou passar. **Ligada por padrão**; `0` desliga. **Custo: uma chamada extra de LLM rápido por mensagem** que a regex não bloqueou | — (ligada). Se o LLM falhar, a mensagem passa |
| `AMBIENTE` | `desenvolvimento` (padrão), `qa` ou `producao`. Em `producao`, o índice do FAQ com `EmbeddingsHash` é log `error` | Tratado como `desenvolvimento` |
| `TAVILY_API_KEY` | Busca na web do agente FAQ pela Tavily | Usa o DuckDuckGo |
| `MCP_SERVERS` | JSON com servidores MCP externos, cujas tools o agente FAQ pode usar | Sem tools MCP externas |
| `CHAT_LIMITE_POR_MINUTO`, `CHAT_LIMITE_POR_DIA` | Máximo de mensagens por usuário no `/v1/chat` (padrão 20/min e 300/dia); acima disso, `429` com `Retry-After`. Com `MONGODB_URL` o contador é compartilhado entre instâncias; se o Mongo cair, a API continua no ar e conta em memória por instância (log `error`) | — |
| `A2A_AGENTES_EXTERNOS` | JSON `{"nome": "http://host:porta"}` de agentes A2A que o FAQ pode consultar | Sem consulta a agentes externos |

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
