# Arquitetura do sistema Venus (IA)

Visão de alto nível da API (`Venus-AI-api`) e do SDK (`Venus-AI-Sdk`), como
estão no código. Linhas tracejadas são componentes **opcionais**, que só ligam
com a variável de ambiente correspondente.

## Componentes

```mermaid
flowchart TB
    app["App mobile"]
    firebase["Firebase Auth<br/>(ID token)"]
    externo["Sistema externo<br/>(cliente A2A)"]

    subgraph ecs["API FastAPI — AWS ECS"]
        chat["POST /v1/chat<br/>token -> uid<br/>limite por uid (429)<br/>uid -> user_id (Postgres)"]
        a2a_srv["/a2a — servidor A2A<br/>(X-API-Key)"]
        metricas["Middleware de métricas"]

        subgraph grafo["Grafo LangGraph (SDK venus_sdk)"]
            ge["Guardrail de entrada"]
            mem_in["Carregar memória"]
            rot["Roteador"]
            esp["Especialistas<br/>produto · ingrediente · rotina · FAQ (RAG)"]
            juiz["Agente Juiz"]
            orq["Orquestrador"]
            gs["Guardrail de saída"]
            mem_out["Atualizar memória"]
            ge --> mem_in --> rot --> esp --> juiz
            juiz -- "reprovado (retry)" --> esp
            juiz -- "aprovado / esgotado" --> orq --> gs --> mem_out
            rot -- "small talk / fora de escopo" --> gs
        end
    end

    postgres[("Postgres<br/>catálogo · usuários · favoritos<br/>alergias · google_oauth_tokens")]
    mongo[("MongoDB<br/>checkpointer · memória de longo prazo<br/>métricas · limites do chat")]
    qdrant[("Qdrant<br/>coleção do FAQ")]
    faqlocal["Índice local do FAQ<br/>(FastEmbed, sem Qdrant)"]
    llms["LLMs com fallback<br/>Groq -> Mistral -> Gemini"]
    web["Busca web<br/>Tavily / DuckDuckGo"]
    gcal["Google Calendar"]
    mcp_ext["Servidores MCP externos"]
    a2a_ext["Agentes A2A externos"]
    langfuse["Langfuse<br/>(rastreamento)"]

    app -- "login" --> firebase
    app -- "Bearer token" --> chat
    externo --> a2a_srv
    chat --> ge
    a2a_srv --> ge
    chat -. "valida token" .-> firebase
    chat --> postgres
    chat --> mongo
    metricas --> mongo
    mem_in --> mongo
    mem_out --> mongo
    esp --> postgres
    esp --> llms
    rot --> llms
    juiz --> llms
    orq --> llms
    esp --> web
    esp -. "QDRANT_URL" .-> qdrant
    esp --> faqlocal
    esp -. "MCP_SERVERS" .-> mcp_ext
    esp -. "A2A_AGENTES_EXTERNOS" .-> a2a_ext
    esp -. "SDK pronto; ainda não ligado na API" .-> gcal
    grafo -. "LANGFUSE_*" .-> langfuse
```

- **Identidade:** o `uid` vem do token do Firebase; o `user_id` do Postgres é
  resolvido pela API (`venus.users.firebase_uid`), nunca enviado pelo app. Dentro
  do grafo, as tools de dados da conta usam sempre o usuário da conversa.
- **FAQ:** com `QDRANT_URL`, a coleção do Qdrant (alimentada por
  `python -m venus_sdk.rag.faq_ingest`); sem ela, o índice local sobre
  `venus_api/data/faq/`, com o mesmo modelo de embeddings.
- **A2A:** servidor em `/a2a` (chave no header); conversas A2A ficam no
  namespace `a2a:` do checkpointer, separadas das do app.

## Uma mensagem pelo grafo

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuário (app)
    participant API as API /v1/chat
    participant GE as Guardrail de entrada
    participant MEM as Memória (Mongo)
    participant ROT as Roteador
    participant ESP as Especialista
    participant J as Agente Juiz
    participant ORQ as Orquestrador
    participant GS as Guardrail de saída

    U->>API: mensagem + Bearer token
    API->>API: valida token, limite por uid, resolve user_id
    API->>GE: estado inicial
    alt mensagem bloqueada (injeção, flood, vazia)
        GE->>GS: resposta padrão de bloqueio
    else liberada
        GE->>MEM: carrega o perfil de longo prazo
        MEM->>ROT: mensagem + memória
        alt small talk ou fora de escopo
            ROT->>GS: resposta direta
        else rota produto / ingrediente / rotina / faq
            ROT->>ESP: pergunta + rota
            loop até aprovar ou esgotar as tentativas
                ESP->>ESP: agente ReAct chama as tools (Postgres, RAG, web)
                ESP->>J: JSON + evidências das tools
                J-->>ESP: reprovado + feedback (nova tentativa)
            end
            J->>ORQ: aprovado (ou tentativas esgotadas)
            ORQ->>GS: resposta em linguagem natural
        end
    end
    GS->>MEM: atualiza a memória (não em turno bloqueado)
    GS-->>API: resposta final
    API-->>U: 200 + resposta
```
