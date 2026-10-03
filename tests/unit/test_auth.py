import pytest
from api.auth import create_access_token, decode_token
from jose import JWTError


def test_create_and_decode_token():
    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"


def test_invalid_token_raises():
    with pytest.raises(JWTError):
        decode_token("not.a.valid.token")


def test_token_contains_expiry():
    token = create_access_token("user-456")
    payload = decode_token(token)
    assert "exp" in payload
