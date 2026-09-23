# Configurações da aplicação (Settings), carregadas de variáveis de
# ambiente / arquivo .env via pydantic-settings: credencial do Firebase, URLs
# de Mongo e Postgres, chaves do Langfuse e do servidor A2A. Instanciado uma
# vez em `settings`, importado onde precisar.

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Credencial da conta de serviço do Firebase: o CAMINHO do arquivo JSON
    # (uso local) ou o próprio CONTEÚDO do JSON (uso na nuvem, onde não existe
    # pasta pra guardar o arquivo — o segredo entra como variável de ambiente).
    # Sem ela, o Firebase Admin cai nas credenciais padrão do ambiente
    # (GOOGLE_APPLICATION_CREDENTIALS).
    firebase_credentials: str | None = None

    # Conexão do MongoDB que guarda histórico de conversa (checkpointer) e
    # memória de longo prazo (store). Sem ela, ambos caem na versão em RAM —
    # ver `infra/checkpointer.py`.
    mongodb_url: str | None = None

    # Postgres do CRUD, consultado pelas tools de produto e ingrediente e pela
    # checagem de alergia. Sem ele, o chat funciona, mas esses especialistas
    # respondem que não conseguiram consultar os dados — ver `infra/postgres.py`.
    database_url: str | None = None

    # Langfuse: rastreia o que acontece dentro do grafo (tempo de cada agente,
    # tokens, custo). Sem as chaves, o chat funciona normal, só não é
    # rastreado. A base_url depende da região onde a conta foi criada.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str | None = None

    # Servidor A2A (outros agentes conversando com a Venus), montado em
    # `/a2a`. O SDK não traz autenticação nenhuma, então ele só liga quando as
    # DUAS variáveis existem: a chave (exigida no header `X-API-Key`) e a URL
    # pública da API (vai no Agent Card, sem barra no fim — ela só existe
    # depois do primeiro deploy). Ver `api/a2a.py`.
    a2a_api_key: str | None = None
    a2a_base_url: str | None = None


settings = Settings()
