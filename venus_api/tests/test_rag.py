from venus_api.app.core.config import settings
from venus_api.app.infra import rag


def test_indice_padrao_carrega_documentos_do_faq(monkeypatch):
	"""Sem FAQ_DIR, usa `venus_api/data/faq/` — que precisa existir e ter
	conteúdo, senão o agente FAQ fica sem ter onde buscar."""
	monkeypatch.setattr(settings, "faq_dir", None)

	indice = rag.criar_indice_faq()

	assert indice is not None
	achados = indice.buscar("como funciona o score", k=3)
	assert achados
	assert all(a["fonte"].endswith(".md") for a in achados)


def test_pasta_inexistente_nao_derruba_a_api(monkeypatch, tmp_path):
	monkeypatch.setattr(settings, "faq_dir", str(tmp_path / "nao-existe"))

	assert rag.criar_indice_faq() is None
