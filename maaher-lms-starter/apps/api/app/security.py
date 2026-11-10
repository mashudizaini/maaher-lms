"""Authorization primitives independent of transport and storage."""
from dataclasses import dataclass
from hashlib import sha256
import secrets
from uuid import UUID


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    role: str


def token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def authorize(principal: Principal, allowed: set[str]) -> bool:
    return principal.role in {"student", "teacher", "admin"} & allowed
