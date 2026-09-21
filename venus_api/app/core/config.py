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


settings = Settings()
