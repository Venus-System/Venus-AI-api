from venus_api.app import main
from venus_api.app.core.config import settings

# A mesma origem que o conftest fixa em CORS_ORIGENS_PERMITIDAS.
ORIGEM_DA_WEB = "http://localhost:5173"


def _preflight(client, origem: str, metodo: str = "POST", url: str = "/v1/chat"):
	return client.options(
		url,
		headers={
			"Origin": origem,
			"Access-Control-Request-Method": metodo,
			"Access-Control-Request-Headers": "authorization, content-type",
		},
	)


def test_preflight_da_web_e_liberado(client):
	resposta = _preflight(client, ORIGEM_DA_WEB)

	assert resposta.status_code == 200
	assert resposta.headers["access-control-allow-origin"] == ORIGEM_DA_WEB
	metodos = {m.strip() for m in resposta.headers["access-control-allow-methods"].split(",")}
	assert {"GET", "POST", "DELETE"} <= metodos
	cabecalhos = resposta.headers["access-control-allow-headers"].lower()
	assert "authorization" in cabecalhos and "content-type" in cabecalhos


def test_preflight_do_delete_da_agenda_e_liberado(client):
	resposta = _preflight(client, ORIGEM_DA_WEB, metodo="DELETE", url="/v1/integracoes/google-calendar")

	assert resposta.status_code == 200
	assert resposta.headers["access-control-allow-origin"] == ORIGEM_DA_WEB


def test_preflight_de_origem_desconhecida_e_recusado(client):
	resposta = _preflight(client, "https://atacante.example")

	assert resposta.status_code == 400
	assert "access-control-allow-origin" not in resposta.headers


def test_resposta_para_a_web_expoe_o_retry_after(client):
	"""Sem o Retry-After exposto, o JS da web não lê a espera do 429."""
	resposta = client.get("/v1/health", headers={"Origin": ORIGEM_DA_WEB})

	assert resposta.status_code == 200
	assert resposta.headers["access-control-allow-origin"] == ORIGEM_DA_WEB
	assert resposta.headers["access-control-expose-headers"] == "Retry-After"


def test_chamada_sem_origin_nao_recebe_cabecalho_cors(client, auth_headers):
	"""O app mobile não manda Origin: a resposta segue como antes."""
	resposta = client.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)

	assert resposta.status_code == 200
	assert "access-control-allow-origin" not in resposta.headers


def test_preflight_nao_vira_metrica(client, metricas):
	"""O CORS fica por fora do middleware de métricas: o OPTIONS do navegador
	é respondido antes e não polui a taxa de erro."""
	_preflight(client, ORIGEM_DA_WEB)

	assert metricas.documentos == []


def test_origens_cors_ignora_espaco_item_vazio_e_barra_final(monkeypatch):
	monkeypatch.setattr(
		settings, "cors_origens_permitidas", " http://localhost:5173/ , ,https://venus-web-application.vercel.app"
	)

	assert main._origens_cors() == ["http://localhost:5173", "https://venus-web-application.vercel.app"]


def test_sem_a_variavel_nenhuma_origem_e_liberada(monkeypatch):
	monkeypatch.setattr(settings, "cors_origens_permitidas", None)

	assert main._origens_cors() == []
