import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from venus_api.app.core import security
from venus_api.app.core.config import settings


def _json_de_conta_de_servico() -> dict:
	"""Conta de serviço de mentira, mas com uma chave RSA de verdade — a
	biblioteca do Firebase lê a chave ao montar a credencial."""
	chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
	pem = chave.private_bytes(
		serialization.Encoding.PEM,
		serialization.PrivateFormat.PKCS8,
		serialization.NoEncryption(),
	).decode()
	return {
		"type": "service_account",
		"project_id": "projeto-de-teste",
		"private_key_id": "abc123",
		"private_key": pem,
		"client_email": "teste@projeto-de-teste.iam.gserviceaccount.com",
		"client_id": "1",
		"token_uri": "https://oauth2.googleapis.com/token",
	}


def test_aceita_o_conteudo_do_json(monkeypatch):
	monkeypatch.setattr(settings, "firebase_credentials", json.dumps(_json_de_conta_de_servico()))

	credencial = security._montar_credencial()

	assert credencial.project_id == "projeto-de-teste"


def test_aceita_o_caminho_do_arquivo(monkeypatch, tmp_path):
	arquivo = tmp_path / "firebase.json"
	arquivo.write_text(json.dumps(_json_de_conta_de_servico()), encoding="utf-8")
	monkeypatch.setattr(settings, "firebase_credentials", str(arquivo))

	assert security._montar_credencial().project_id == "projeto-de-teste"


def test_sem_credencial_usa_a_padrao_do_ambiente(monkeypatch):
	monkeypatch.setattr(settings, "firebase_credentials", None)

	assert isinstance(security._montar_credencial(), security.credentials.ApplicationDefault)


@pytest.mark.parametrize(
	"valor",
	[
		'{"type": "service_account", "project_id": ',  # JSON cortado
		'{"type": "outra_coisa"}',  # JSON válido, mas não é conta de serviço
	],
)
def test_credencial_quebrada_nao_e_value_error(monkeypatch, valor):
	"""`deps.py` transforma `ValueError` em 401. Se a credencial quebrada
	levantasse `ValueError`, um erro de configuração do servidor se passaria
	por token inválido."""
	monkeypatch.setattr(settings, "firebase_credentials", valor)

	with pytest.raises(RuntimeError) as erro:
		security._montar_credencial()

	assert not isinstance(erro.value, ValueError)


def test_chat_com_credencial_quebrada_devolve_500_e_nao_401(client_http, monkeypatch, auth_headers):
	monkeypatch.setattr(settings, "firebase_credentials", '{"type": "service_account", "project')
	# Usa a montagem real da credencial; o resto da inicialização é o que o
	# `conftest` já troca por uma versão falsa.
	monkeypatch.setattr(security, "_inicializar_firebase", security._montar_credencial)

	response = client_http.post("/v1/chat", json={"mensagem": "oi"}, headers=auth_headers)

	assert response.status_code == 500
