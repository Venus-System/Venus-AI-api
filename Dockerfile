# Duas etapas: o `git` só existe na primeira (o pip precisa dele pra baixar o
# SDK do Venus do GitHub) e não vai pra imagem final.
FROM python:3.12-slim AS dependencias

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY venus_api/requirements.txt venus_api/requirements.txt
RUN pip install --no-cache-dir --prefix=/instalado -r venus_api/requirements.txt


FROM python:3.12-slim

WORKDIR /app

COPY --from=dependencias /instalado /usr/local
COPY venus_api/ venus_api/

RUN addgroup --system venus && adduser --system --ingroup venus venus
USER venus

EXPOSE 8080
CMD ["uvicorn", "venus_api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
