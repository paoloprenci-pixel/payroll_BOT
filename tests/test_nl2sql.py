"""
test_nl2sql.py — Test per il modulo nl2sql (con mock di OpenRouter API).
"""
import sys, os
import unittest.mock as mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from execution.nl2sql import resolve_month, generate_sql
from execution.errors import OutOfScopeError
from config import LAST_AVAILABLE_MONTH


def test_resolve_month_returns_default():
    """Senza periodo specificato → restituisce LAST_AVAILABLE_MONTH."""
    month = resolve_month("Quanti dipendenti ci sono a Milano?")
    assert month == LAST_AVAILABLE_MONTH


def test_resolve_month_returns_default_for_generic_question():
    """Anche domande generiche → default."""
    month = resolve_month("Qual è la RAL più alta?")
    assert month == LAST_AVAILABLE_MONTH


@mock.patch("execution.nl2sql.requests.post")
def test_generate_sql_returns_select(mock_post):
    """generate_sql deve restituire una stringa che inizia con SELECT."""
    mock_post.return_value = mock.Mock(
        status_code=200,
        json=lambda: {
            "choices": [{
                "message": {"content": "SELECT COUNT(*) FROM `hr_analytics.dipendenti_storico` WHERE mese_riferimento = '2026-02-01'"}
            }]
        }
    )
    mock_post.return_value.raise_for_status = lambda: None

    sql = generate_sql("Quanti dipendenti ci sono?", LAST_AVAILABLE_MONTH)
    assert sql.strip().upper().startswith("SELECT")


@mock.patch("execution.nl2sql.requests.post")
def test_generate_sql_strips_markdown_fences(mock_post):
    """generate_sql deve rimuovere i blocchi ```sql ... ``` se presenti."""
    mock_post.return_value = mock.Mock(
        status_code=200,
        json=lambda: {
            "choices": [{
                "message": {"content": "```sql\nSELECT COUNT(*) FROM `hr_analytics.dipendenti_storico`\n```"}
            }]
        }
    )
    mock_post.return_value.raise_for_status = lambda: None

    sql = generate_sql("Test", LAST_AVAILABLE_MONTH)
    assert "```" not in sql
    assert sql.strip().upper().startswith("SELECT")


@mock.patch("execution.nl2sql.requests.post")
def test_generate_sql_raises_on_non_select(mock_post):
    """generate_sql deve sollevare RuntimeError se il modello non restituisce SELECT."""
    mock_post.return_value = mock.Mock(
        status_code=200,
        json=lambda: {
            "choices": [{
                "message": {"content": "Non so rispondere."}
            }]
        }
    )
    mock_post.return_value.raise_for_status = lambda: None

    with pytest.raises(RuntimeError):
        generate_sql("Domanda impossibile", LAST_AVAILABLE_MONTH)


@mock.patch("execution.nl2sql.requests.post")
def test_generate_sql_raises_out_of_scope(mock_post):
    """generate_sql deve sollevare OutOfScopeError se il modello risponde OUT_OF_SCOPE."""
    mock_post.return_value = mock.Mock(
        status_code=200,
        json=lambda: {
            "choices": [{
                "message": {"content": "OUT_OF_SCOPE"}
            }]
        }
    )
    mock_post.return_value.raise_for_status = lambda: None

    with pytest.raises(OutOfScopeError):
        generate_sql("Che tempo fa a Roma?", LAST_AVAILABLE_MONTH)
