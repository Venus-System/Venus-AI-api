# O .env.example acompanha o Settings: variável nova sem linha no exemplo
# some da vista de quem vai configurar a API.

import re
from pathlib import Path

from venus_api.app.core.config import Settings

_EXEMPLO = Path(__file__).resolve().parents[2] / ".env.example"


def _variaveis_do_exemplo() -> set[str]:
	"""Nomes com linha no exemplo, comentada ou não (`# CHAT_LIMITE_POR_DIA=300`
	documenta a variável e o padrão)."""
	nomes = set()
	for linha in _EXEMPLO.read_text(encoding="utf-8").splitlines():
		nome, sinal, _ = linha.lstrip("# ").partition("=")
		if sinal and nome.isupper() and nome.replace("_", "").isalnum():
			nomes.add(nome)
	return nomes


def test_env_example_tem_todas_as_variaveis_do_settings():
	faltando = {campo.upper() for campo in Settings.model_fields} - _variaveis_do_exemplo()

	assert not faltando, f"Faltam no .env.example: {sorted(faltando)}"


def test_env_example_tem_todas_as_variaveis_da_tabela_do_readme():
	"""A tabela "Configuração" do README também lista as que só o SDK lê
	(chaves dos modelos, Google, Neo4j...), que o Settings não conhece."""
	readme = (_EXEMPLO.parent / "README.md").read_text(encoding="utf-8")
	da_tabela = {
		nome
		for linha in readme.splitlines()
		if linha.startswith("| `")
		for nome in re.findall(r"`([A-Z][A-Z0-9_]+)`", linha.split("|")[1])
	}

	assert da_tabela, "A tabela de variáveis do README mudou de formato"
	faltando = da_tabela - _variaveis_do_exemplo()
	assert not faltando, f"Faltam no .env.example: {sorted(faltando)}"


def test_env_example_copiado_como_esta_carrega_sem_erro():
	"""Valor vazio num campo numérico derrubaria a API no startup; por isso os
	números ficam comentados no exemplo."""
	Settings(_env_file=_EXEMPLO)
