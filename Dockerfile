# Duas etapas: o `git` e o `npm` só existem na primeira (o pip precisa do git
# pra baixar o SDK do Venus do GitHub; o npm instala o servidor MCP da Tavily)
# e não vão pra imagem final. Só as dependências de produção
# (requirements.txt): as ferramentas de teste não entram na imagem.
FROM python:3.12-slim AS dependencias

RUN apt-get update \
    && apt-get install -y --no-install-recommends git nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY venus_api/requirements.txt venus_api/requirements.txt
RUN pip install --no-cache-dir --prefix=/instalado -r venus_api/requirements.txt

# Modelo de embeddings do FAQ (FastEmbed, ~220 MB) baixado no build: em
# produção o índice local do FAQ nunca depende de rede no startup. A imagem
# final roda como `venus`, não root: o cache precisa ficar legível por todos.
# Desde o SDK 0.3.0 o download tem tempo máximo (15 s por padrão, para o
# startup não esperar); aqui no build ele pode demorar o quanto precisar.
ENV FASTEMBED_CACHE_PATH=/modelos/fastembed
RUN VENUS_FASTEMBED_TIMEOUT_SEGUNDOS=900 PYTHONPATH=/instalado/lib/python3.12/site-packages \
    python -c "from venus_sdk.rag.vector_build import get_embed_model; get_embed_model()" \
    && chmod -R a+rX /modelos

# Servidor MCP oficial da Tavily (busca web do FAQ, ver
# infra/busca_web_mcp.py), com versão fixada e instalado no build: o
# container nunca baixa pacote no startup. Para atualizar, troque a versão.
ARG TAVILY_MCP_VERSAO=0.2.22
RUN npm install --prefix /opt/tavily-mcp --omit=dev --no-audit --no-fund "tavily-mcp@${TAVILY_MCP_VERSAO}" \
    && chmod -R a+rX /opt/tavily-mcp


FROM python:3.12-slim

# Só o runtime do Node (sem npm), para rodar o servidor MCP da Tavily.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=dependencias /instalado /usr/local
COPY --from=dependencias /modelos /modelos
COPY --from=dependencias /opt/tavily-mcp /opt/tavily-mcp
# O modelo já está na imagem: o FastEmbed lê do cache e não consulta o
# Hugging Face (HF_HUB_OFFLINE). `tavily-mcp` fica no PATH.
ENV FASTEMBED_CACHE_PATH=/modelos/fastembed \
    HF_HUB_OFFLINE=1 \
    PATH="/opt/tavily-mcp/node_modules/.bin:${PATH}"
# Os documentos do FAQ vêm dentro do SDK instalado (package data), não de
# uma pasta da API.
COPY venus_api/ venus_api/

RUN addgroup --system venus && adduser --system --ingroup venus venus
USER venus

EXPOSE 8080
CMD ["uvicorn", "venus_api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
