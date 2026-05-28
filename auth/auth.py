from __future__ import annotations

from dataclasses import dataclass

try:
    from jose import JWTError, jwt
except ImportError:  # pragma: no cover
    JWTError = Exception  # type: ignore[assignment]
    jwt = None  # type: ignore[assignment]


@dataclass(slots=True)
class AuthClaims:
    user_id: str
    subject: str | None = None
    raw: dict | None = None


class AuthError(Exception):
    pass


def validate_jwt_token(token: str, user_id: str, secret: str, algorithm: str) -> AuthClaims:
    if jwt is None:
        raise AuthError("JWT support is not installed")
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
    except JWTError as exc:  # pragma: no cover - runtime validation
        raise AuthError("Invalid or expired token") from exc

    subject = payload.get("sub") or payload.get("user_id")
    if subject != user_id:
        raise AuthError("Token subject does not match the requested user")
    return AuthClaims(user_id=user_id, subject=subject, raw=payload)
