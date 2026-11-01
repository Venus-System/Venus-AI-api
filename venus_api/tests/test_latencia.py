import os

from venus_api.app.core.latencia import priorizar_modelos_rapidos


def test_prioriza_mistral_sem_remover_fallbacks(monkeypatch):
    monkeypatch.setenv("VENUS_PRIORIZAR_MODELOS_RAPIDOS", "1")
    monkeypatch.setenv(
        "LLM_CADEIA_ESPECIALISTA",
        "groq:openai/gpt-oss-20b,mistral:ministral-14b-latest,gemini:gemini-3.6-flash",
    )
    monkeypatch.setenv(
        "LLM_CADEIA_RAPIDO",
        "groq:openai/gpt-oss-20b,mistral:ministral-8b-latest",
    )

    priorizar_modelos_rapidos()

    assert os.environ["LLM_CADEIA_ESPECIALISTA"].startswith("mistral:ministral-14b-latest,")
    assert os.environ["LLM_CADEIA_RAPIDO"].startswith("mistral:ministral-8b-latest,")
    assert "groq:openai/gpt-oss-20b" in os.environ["LLM_CADEIA_ESPECIALISTA"]


def test_priorizacao_pode_ser_desativada(monkeypatch):
    monkeypatch.setenv("VENUS_PRIORIZAR_MODELOS_RAPIDOS", "0")
    monkeypatch.setenv(
        "LLM_CADEIA_RAPIDO",
        "groq:openai/gpt-oss-20b,mistral:ministral-8b-latest",
    )

    priorizar_modelos_rapidos()

    assert os.environ["LLM_CADEIA_RAPIDO"].startswith("groq:openai/gpt-oss-20b,")
