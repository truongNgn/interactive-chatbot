from app.auth import issue_dev_token, resolve_auth_context
from app.conversation_store import hash_password, verify_password


def test_password_hash_roundtrip() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_issued_auth_token_resolves_user() -> None:
    token = issue_dev_token("auth-user")
    auth = resolve_auth_context(authorization=f"Bearer {token}")

    assert auth.user_id == "auth-user"
    assert auth.mode == "jwt"
