"""Item 6 da revisão técnica: build reprodutível e só dependência de produção
na imagem."""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _linhas(arquivo: str) -> list[str]:
	return [
		linha.strip() for linha in (RAIZ / arquivo).read_text(encoding="utf-8").splitlines()
		if linha.strip() and not linha.strip().startswith("#")
	]


def test_sdk_fixado_por_tag_ou_commit_e_nao_por_branch():
	[sdk] = [linha for linha in _linhas("venus_api/requirements.txt") if "Venus-AI-Sdk" in linha]
	referencia = sdk.rsplit("@", 1)[1]
	assert referencia not in {"develop", "main"}
	assert re.fullmatch(r"v\d+\.\d+\.\d+|[0-9a-f]{7,40}", referencia)


def test_ferramentas_de_teste_ficam_fora_da_producao():
	producao = " ".join(_linhas("venus_api/requirements.txt"))
	assert "pytest" not in producao and "httpx" not in producao
	desenvolvimento = _linhas("venus_api/requirements-dev.txt")
	assert "-r requirements.txt" in desenvolvimento
	assert any(linha.startswith("pytest") for linha in desenvolvimento)
	assert any(linha.startswith("httpx") for linha in desenvolvimento)


def test_imagem_instala_so_producao_e_ci_instala_desenvolvimento():
	dockerfile = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
	assert "requirements-dev" not in dockerfile and "venus_api/requirements.txt" in dockerfile
	ci = (RAIZ / ".github/workflows/ci.yaml").read_text(encoding="utf-8")
	assert "venus_api/requirements-dev.txt" in ci


def test_ci_instala_o_sdk_pelo_requirements_e_nunca_editavel():
	# Um `pip install -e` de um checkout local do SDK esconderia a tag errada
	# no requirements.txt (foi o que aconteceu com a v0.1.0).
	for arquivo in (".github/workflows/ci.yaml", "venus_api/requirements.txt", "venus_api/requirements-dev.txt"):
		texto = (RAIZ / arquivo).read_text(encoding="utf-8")
		assert not re.search(r"(^|\s)(-e|--editable)\s", texto), arquivo


def test_imagem_leva_o_modelo_do_fastembed_e_nao_usa_rede_para_ele():
	# Sem o modelo na imagem, o índice local do FAQ baixa ~220 MB no startup
	# (ou cai no EmbeddingsHash se não houver rede).
	dockerfile = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
	estagio_de_build, estagio_final = dockerfile.split("\nFROM ")[1:3]
	assert "get_embed_model()" in estagio_de_build  # baixado no build, não no startup
	assert "ENV FASTEMBED_CACHE_PATH=" in estagio_final and "HF_HUB_OFFLINE=1" in estagio_final
	assert "COPY --from=dependencias /modelos" in estagio_final
