# Configurações da aplicação (Settings), carregadas de variáveis de
# ambiente / arquivo .env via pydantic-settings: URLs de Redis, Mongo e
# Postgres, segredo de autenticação da API e número máximo de tentativas
# do agente juiz. Instanciado uma vez em `settings`, importado onde precisar.

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Caminho do JSON da conta de serviço do Firebase. Sem ele, o Firebase
    # Admin cai nas credenciais padrão do ambiente
    # (GOOGLE_APPLICATION_CREDENTIALS), que é como a credencial costuma ser
    # entregue em produção.
    firebase_credentials: str | None = None

    # Conexão do MongoDB que guarda histórico de conversa (checkpointer) e
    # memória de longo prazo (store). Sem ela, ambos caem na versão em RAM —
    # ver `infra/checkpointer.py`.
    mongodb_url: str | None = None

    # Langfuse: rastreia o que acontece dentro do grafo (tempo de cada agente,
    # tokens, custo). Sem as chaves, o chat funciona normal, só não é
    # rastreado. A base_url depende da região onde a conta foi criada.
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str | None = None


settings = Settings()
