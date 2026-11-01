# Observabilidade e SRE — Venus

Relatório de medição de 30/10/2026, feito para o requisito de observabilidade/SRE da disciplina de Inteligência Artificial (página 11 do documento de requisitos).

**[Abrir o relatório completo (PDF, 14 páginas)](observabilidade.pdf)**

## Os cinco números do requisito

| O que o requisito pede | Resultado | Origem |
|---|---|---|
| Custo para **100** usuários semanais | **US$ 11 por mês** (faixa de US$ 3 a US$ 50, conforme o ritmo de uso) | Estimado: 8,2 turnos por usuário por semana (medido) × US$ 0,0032 por turno (medido) |
| Custo para **1.000** usuários semanais | **US$ 112 por mês** (faixa de US$ 28 a US$ 495) | Estimado, mesma conta |
| **Latência** total e entre agentes | **p50 5,2 s e p95 29,3 s** por turno; só 0,6 s fica entre os agentes (o tempo está nos especialistas, de 10 a 19 s) | Medido em produção (139 turnos reais) |
| **Índice de erros** | **0 de 143** requisições com HTTP 5xx; **0 de 139** turnos com erro | Medido em produção |
| **Custo por resolução** e **ROI** | **US$ 0,0047 por resolução**; ROI de **106×** com US$ 0,50 por resolução | Estimado; o valor por resolução é uma premissa |

O relatório traz ainda o desenho de arquitetura de alto nível com a camada de observabilidade (seção 9), as premissas com fontes (seção 6), as metas de SRE comparadas ao medido (seção 7) e as evidências do Langfuse (seção 10).

## Leia com cuidado

- **Os custos são estimativas.** Os provedores de IA usados são gratuitos; o custo é "quanto custaria" com um preço pago de referência. O ROI depende do valor assumido por resolução, que não foi medido, e não inclui infraestrutura nem manutenção.
- **Nem todas as metas de SRE foram atingidas.** A latência p95 ficou em 29 s contra a meta de 20 s, e 73% das chamadas ao modelo principal do Groq (plano gratuito) falham, com o fallback absorvendo. A lista completa está na seção 7 do relatório.
- **A amostra é pequena:** 7 usuários do período de testes, em 17 dias.
- **O código e os scripts de medição citados no relatório ainda não estão neste repositório.** Este PR traz só o relatório.
