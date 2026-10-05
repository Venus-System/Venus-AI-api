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
	# O SDK 0.3.0 limita o download a 15 s; no build o limite precisa ser maior.
	assert re.search(r"VENUS_FASTEMBED_TIMEOUT_SEGUNDOS=\d{3,}", estagio_de_build)
	assert "ENV FASTEMBED_CACHE_PATH=" in estagio_final and "HF_HUB_OFFLINE=1" in estagio_final
	assert "COPY --from=dependencias /modelos" in estagio_final


def test_sdk_instalado_com_os_extras_do_calendar_e_do_neo4j():
	[sdk] = [linha for linha in _linhas("venus_api/requirements.txt") if "Venus-AI-Sdk" in linha]
	extras = set(sdk.split("[", 1)[1].split("]", 1)[0].split(","))
	assert {"google_calendar", "neo4j"} <= extras


def test_sincronizacao_do_neo4j_so_roda_a_mao():
	workflow = (RAIZ / ".github/workflows/sincronizar-neo4j.yaml").read_text(encoding="utf-8")
	assert "workflow_dispatch" in workflow and "schedule" not in workflow
	assert "python -m venus_sdk.checkup.sincronizar" in workflow
	for segredo in ("DATABASE_URL", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"):
		assert f"secrets.{segredo}" in workflow


def test_imagem_instala_o_servidor_mcp_da_tavily_com_versao_fixada():
	dockerfile = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
	estagio_de_build, estagio_final = dockerfile.split("\nFROM ")[1:3]
	versao = re.search(r"ARG TAVILY_MCP_VERSAO=(\S+)", estagio_de_build)
	assert versao and re.fullmatch(r"\d+\.\d+\.\d+", versao.group(1))
	assert "tavily-mcp@${TAVILY_MCP_VERSAO}" in estagio_de_build
	assert "npx" not in dockerfile and "@latest" not in dockerfile
	assert "COPY --from=dependencias /opt/tavily-mcp" in estagio_final and "nodejs" in estagio_final
