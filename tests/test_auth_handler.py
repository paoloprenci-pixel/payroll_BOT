"""
test_auth_handler.py — Test per il modulo auth_handler.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from execution.auth_handler import (
    is_authenticated,
    try_authenticate,
    reset_session,
    authenticated_sessions,
)

CHAT_ID_OK = 111111
CHAT_ID_BAD = 222222


@pytest.fixture(autouse=True)
def cleanup():
    """Pulisce le sessioni prima e dopo ogni test."""
    reset_session(CHAT_ID_OK)
    reset_session(CHAT_ID_BAD)
    yield
    reset_session(CHAT_ID_OK)
    reset_session(CHAT_ID_BAD)


def test_not_authenticated_by_default():
    assert is_authenticated(CHAT_ID_OK) is False


def test_correct_email_authenticates():
    result = try_authenticate(CHAT_ID_OK, "paoloprenci@gmail.com")
    assert result is True
    assert is_authenticated(CHAT_ID_OK) is True


def test_wrong_email_does_not_authenticate():
    result = try_authenticate(CHAT_ID_BAD, "hacker@evil.com")
    assert result is False
    assert is_authenticated(CHAT_ID_BAD) is False


def test_email_case_insensitive():
    result = try_authenticate(CHAT_ID_OK, "PaoloPreNci@Gmail.COM")
    assert result is True


def test_email_with_spaces_stripped():
    result = try_authenticate(CHAT_ID_OK, "  paoloprenci@gmail.com  ")
    assert result is True


def test_reset_session_clears_auth():
    try_authenticate(CHAT_ID_OK, "paoloprenci@gmail.com")
    assert is_authenticated(CHAT_ID_OK) is True
    reset_session(CHAT_ID_OK)
    assert is_authenticated(CHAT_ID_OK) is False
