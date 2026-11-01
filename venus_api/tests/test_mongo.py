from venus_api.app.infra.mongo import mongodb_url_com_timeout_curto


def test_mongodb_url_adiciona_timeouts_de_socket_sem_trocar_credenciais():
	url = "mongodb+srv://usuario:senha@cluster.example/venus"
	resultado = mongodb_url_com_timeout_curto(url)

	assert resultado.startswith("mongodb+srv://usuario:senha@cluster.example/venus?")
	assert "socketTimeoutMS=2000" in resultado
	assert "waitQueueTimeoutMS=2000" in resultado


def test_mongodb_url_preserva_timeout_explicitamente_configurado():
	url = "mongodb://usuario:senha@localhost/venus?socketTimeoutMS=9000"
	resultado = mongodb_url_com_timeout_curto(url)

	assert "socketTimeoutMS=9000" in resultado
	assert "socketTimeoutMS=2000" not in resultado
