from venus_api.app.core.config import settings
from venus_api.app.infra import rag


def test_indice_padrao_carrega_documentos_do_faq(monkeypatch):
	"""Sem FAQ_DIR, usa os documentos empacotados no SDK — que precisam
	existir e ter conteúdo, senão o agente FAQ fica sem ter onde buscar."""
	monkeypatch.setattr(settings, "faq_dir", None)

	indice = rag.criar_indice_faq()

	assert indice is not None
	achados = indice.buscar("como funciona o score", k=3)
	assert achados
	assert all(a["fonte"].endswith(".md") for a in achados)


def test_pasta_inexistente_nao_derruba_a_api(monkeypatch, tmp_path):
	monkeypatch.setattr(settings, "faq_dir", str(tmp_path / "nao-existe"))

	assert rag.criar_indice_faq() is None


# --- Revisão técnica 2, item 2: o log diz qual índice e embedding subiram ----

import logging  # noqa: E402

import pytest  # noqa: E402
from venus_sdk.rag import faq as faq_do_sdk  # noqa: E402


class _ModeloFastEmbedFalso:
	"""Faz o papel do modelo do FastEmbed sem baixar nada."""

	def get_text_embedding_batch(self, textos):
		return [[float(len(texto)), 1.0] for texto in textos]

	def get_query_embedding(self, texto):
		return [float(len(texto)), 1.0]


def _mensagens(caplog, nivel):
	return [r.getMessage() for r in caplog.records if r.name == rag.logger.name and r.levelno == nivel]


def test_log_diz_embeddings_hash_quando_o_fastembed_esta_indisponivel(monkeypatch, caplog):
	monkeypatch.setattr(settings, "faq_dir", None)
	monkeypatch.setattr(faq_do_sdk, "_embeddings_semanticos", lambda: None)  # FastEmbed indisponível
	caplog.set_level(logging.INFO)

	assert rag.criar_indice_faq() is not None
	assert any("IndiceRAG/EmbeddingsHash" in m for m in _mensagens(caplog, logging.INFO))


def test_log_diz_fastembed_quando_o_modelo_carrega(monkeypatch, caplog):
	monkeypatch.setattr(settings, "faq_dir", None)
	monkeypatch.setattr(faq_do_sdk, "_embeddings_semanticos",
	                    lambda: faq_do_sdk.EmbeddingsFastEmbed(_ModeloFastEmbedFalso()))
	caplog.set_level(logging.INFO)

	rag.criar_indice_faq()
	assert any("IndiceRAG/FastEmbed" in m for m in _mensagens(caplog, logging.INFO))
	assert not _mensagens(caplog, logging.ERROR)


def test_hash_em_producao_vira_error(monkeypatch, caplog):
	monkeypatch.setattr(settings, "faq_dir", None)
	monkeypatch.setattr(settings, "ambiente", "producao")
	monkeypatch.setattr(faq_do_sdk, "_embeddings_semanticos", lambda: None)

	rag.criar_indice_faq()
	assert any("IndiceRAG/EmbeddingsHash" in m for m in _mensagens(caplog, logging.ERROR))


@pytest.mark.parametrize("ambiente", ["desenvolvimento", "qa"])
def test_hash_fora_de_producao_nao_e_error(monkeypatch, caplog, ambiente):
	monkeypatch.setattr(settings, "faq_dir", None)
	monkeypatch.setattr(settings, "ambiente", ambiente)
	monkeypatch.setattr(faq_do_sdk, "_embeddings_semanticos", lambda: None)

	rag.criar_indice_faq()
	assert not _mensagens(caplog, logging.ERROR)


def test_log_do_qdrant(monkeypatch, caplog):
	monkeypatch.setattr(rag, "criar_indice_do_sdk", lambda pasta: faq_do_sdk.IndiceQdrant(cliente=object()))
	caplog.set_level(logging.INFO)

	rag.criar_indice_faq()
	assert any("IndiceQdrant" in m for m in _mensagens(caplog, logging.INFO))


# --- Revisão técnica 2, item 5: o FAQ vem do SDK, sem cópia na API ------------

from pathlib import Path  # noqa: E402

from venus_sdk.config.settings import FAQ_DIR as FAQ_DO_SDK  # noqa: E402


def test_indice_sem_faq_dir_usa_os_documentos_empacotados_no_sdk(monkeypatch):
	pastas = []
	monkeypatch.setattr(settings, "faq_dir", None)
	monkeypatch.setattr(rag, "criar_indice_do_sdk", lambda pasta: pastas.append(Path(pasta)) or object())

	rag.criar_indice_faq()
	assert pastas == [Path(FAQ_DO_SDK)]


def test_api_nao_tem_mais_copia_dos_documentos_do_faq():
	raiz_da_api = Path(rag.__file__).resolve().parents[2]
	assert not (raiz_da_api / "data" / "faq").exists()
	assert sorted(Path(FAQ_DO_SDK).glob("*.md")), "o SDK instalado precisa trazer os .md do FAQ"


def test_faq_dir_da_api_continua_sobrepondo(monkeypatch, tmp_path):
	(tmp_path / "proprio.md").write_text("# Próprio\n\nConteúdo da pasta escolhida.", encoding="utf-8")
	monkeypatch.setattr(settings, "faq_dir", str(tmp_path))

	achados = rag.criar_indice_faq().buscar("conteúdo da pasta escolhida", k=1, score_minimo=0)
	assert achados[0]["fonte"] == "proprio.md"
