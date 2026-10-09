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

    # Chave do /v1/health/detalhado (header X-API-Key). Sem ela, vale a do
    # A2A; sem nenhuma, o endpoint responde 404 — nunca fica público.
    health_api_key: str | None = None

    # Pasta com os documentos do FAQ, indexados pro RAG do agente FAQ. Sem ela,
    # usa os documentos empacotados no SDK instalado — ver `infra/rag.py`.
    faq_dir: str | None = None

    # Tools externas do agente FAQ (ver `infra/ferramentas_externas.py`), em
    # JSON: MCP_SERVERS no formato do MultiServerMCPClient e
    # A2A_AGENTES_EXTERNOS como {"nome": "http://host:porta"}. Sem elas, o FAQ
    # usa só o índice do RAG e a busca na web.
    mcp_servers: str | None = None
    # Busca web do FAQ pelo servidor MCP oficial da Tavily (`infra/busca_web_mcp.py`):
    # liga com TAVILY_API_KEY. `tavily_mcp_comando` é o executável instalado na
    # imagem (Dockerfile); sem a chave, o SDK busca direto (DuckDuckGo).
    tavily_api_key: str | None = None
    tavily_mcp_comando: str = "tavily-mcp"
    a2a_agentes_externos: str | None = None

    # Limite de mensagens por usuário no /v1/chat (cada mensagem custa de 6 a
    # 12 chamadas de LLM). Ver `infra/limite_de_taxa.py`.
    chat_limite_por_minuto: int = 20
    chat_limite_por_dia: int = 300
    # Com o Mongo fora do ar, quanto tempo o limitador conta só em memória
    # antes de tentar o Mongo de novo (disjuntor).
    chat_limite_mongo_pausa_segundos: int = 30

    # Onde a API está rodando: "desenvolvimento" (padrão), "qa" ou "producao".
    # Em produção, cair num fallback que piora a resposta (ex.: o índice do
    # FAQ sem embeddings semânticos) é log `error` em vez de `warning`.
    # TODO(infra): definir AMBIENTE=producao na task definition do ECS de
    # produção (e AMBIENTE=qa na de QA); a task definition não está neste
    # repositório, e sem a variável o log fica no nível de desenvolvimento.
    ambiente: str = "desenvolvimento"

    # Google Calendar (`/v1/integracoes/google-calendar`): redirect URIs aceitas
    # na troca do `code`, separadas por vírgula — as mesmas cadastradas no
    # Google Console para o app. Sem a lista, nenhuma é aceita (400). As
    # credenciais (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    # GOOGLE_TOKEN_ENCRYPTION_KEY) e NEO4J_* são lidas pelo SDK direto do
    # ambiente do processo.
    google_redirect_uris_permitidas: str | None = None

    # CORS: origens (esquema + domínio + porta, sem barra no fim) que podem
    # chamar a API pelo navegador, separadas por vírgula — a web local
    # (http://localhost:5173) e a publicada. Sem a lista, nenhum navegador
    # consegue chamar a API; o app mobile não passa por CORS e não é afetado.
    cors_origens_permitidas: str | None = None


settings = Settings()
