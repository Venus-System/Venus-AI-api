# Duas etapas: o `git` só existe na primeira (o pip precisa dele pra baixar o
# SDK do Venus do GitHub) e não vai pra imagem final. Só as dependências de
# produção (requirements.txt): as ferramentas de teste não entram na imagem.
FROM python:3.12-slim AS dependencias

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY venus_api/requirements.txt venus_api/requirements.txt
RUN pip install --no-cache-dir --prefix=/instalado -r venus_api/requirements.txt

# Modelo de embeddings do FAQ (FastEmbed, ~220 MB) baixado no build: em
# produção o índice local do FAQ nunca depende de rede no startup. A imagem
# final roda como `venus`, não root: o cache precisa ficar legível por todos.
ENV FASTEMBED_CACHE_PATH=/modelos/fastembed
RUN PYTHONPATH=/instalado/lib/python3.12/site-packages \
    python -c "from venus_sdk.rag.vector_build import get_embed_model; get_embed_model()" \
    && chmod -R a+rX /modelos


FROM python:3.12-slim

WORKDIR /app

COPY --from=dependencias /instalado /usr/local
COPY --from=dependencias /modelos /modelos
# O modelo já está na imagem: o FastEmbed lê do cache e não consulta o
# Hugging Face (HF_HUB_OFFLINE).
ENV FASTEMBED_CACHE_PATH=/modelos/fastembed \
    HF_HUB_OFFLINE=1
# Os documentos do FAQ vêm dentro do SDK instalado (package data), não de
# uma pasta da API.
COPY venus_api/ venus_api/

RUN addgroup --system venus && adduser --system --ingroup venus venus
USER venus

EXPOSE 8080
CMD ["uvicorn", "venus_api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
