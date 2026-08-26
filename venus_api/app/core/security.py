# Contrato de autenticação da API.
#
# Usuario: dado mínimo do usuário autenticado (id).
# validar_token: valida o token (JWT/API key) recebido no header
# Authorization e devolve o Usuario correspondente. Implementação real fica
# a cargo do time; app/api/deps.py depende só dessa assinatura.
