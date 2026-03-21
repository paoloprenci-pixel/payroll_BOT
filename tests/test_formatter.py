"""
test_formatter.py — Test per il modulo formatter (con mock di OpenRouter API).
"""
import sys, os
import unittest.mock as mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from execution.formatter import format_response, _format_month


def test_format_month_italian():
    """_format_month converte correttamente in italiano."""
    assert _format_month("2026-02-01") == "febbraio 2026"
    assert _format_month("2025-01-01") == "gennaio 2025"
    assert _format_month("2025-12-01") == "dicembre 2025"


def test_format_response_empty_result():
    """Risultato vuoto → messaggio di nessun dato trovato."""
    response = format_response("Quanti dipendenti a Milano?", "2026-02-01", [])
    assert "nessun dato" in response.lower() or "nessun" in response.lower()


@mock.patch("execution.formatter.requests.post")
def test_format_response_includes_month(mock_post):
    """La risposta deve contenere riferimento al mese."""
    mock_post.return_value = mock.Mock(
        status_code=200,
        json=lambda: {
            "choices": [{
                "message": {"content": "A febbraio 2026 ci sono 12 dipendenti a Milano."}
            }]
        }
    )
    mock_post.return_value.raise_for_status = lambda: None

    result = [{"num_dipendenti": 12}]
    response = format_response("Quanti dipendenti a Milano?", "2026-02-01", result)
    assert "2026" in response or "febbraio" in response.lower()


@mock.patch("execution.formatter.requests.post")
def test_format_response_raises_on_api_error(mock_post):
    """Errore API → RuntimeError."""
    import requests as req
    mock_post.side_effect = req.RequestException("timeout")

    with pytest.raises(RuntimeError):
        format_response("Test", "2026-02-01", [{"ral_media": 45000}])
