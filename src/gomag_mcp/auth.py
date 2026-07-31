"""OAuth access-token verification for the remote MCP transport."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken

logger = logging.getLogger(__name__)


class JWTTokenVerifier:
    """Validate RS256 access tokens issued by an OAuth/OIDC provider."""

    def __init__(self, *, issuer: str, audience: str, jwks_url: str) -> None:
        self._issuer = issuer
        self._audience = audience
        self._jwks = PyJWKClient(jwks_url, cache_keys=True)

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return MCP access information for a valid token, otherwise ``None``."""
        try:
            claims = await asyncio.to_thread(self._decode, token)
        except jwt.PyJWTError as exc:
            # Never log the token or its claims.
            logger.warning("Rejected OAuth access token: %s", type(exc).__name__)
            return None
        except Exception as exc:
            logger.warning("OAuth token verification unavailable: %s", type(exc).__name__)
            return None

        scopes = _extract_scopes(claims)
        subject = claims.get("sub")
        client_id = claims.get("azp") or claims.get("client_id") or subject or "oauth-client"
        return AccessToken(
            token=token,
            client_id=str(client_id),
            scopes=scopes,
            expires_at=_optional_int(claims.get("exp")),
            resource=self._audience,
            subject=str(subject) if subject is not None else None,
            claims=claims,
        )

    def _decode(self, token: str) -> dict[str, Any]:
        signing_key = self._jwks.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self._audience,
            issuer=self._issuer,
            options={"require": ["exp", "iat", "iss", "sub"]},
        )


def _extract_scopes(claims: dict[str, Any]) -> list[str]:
    scopes: list[str] = []
    scope = claims.get("scope")
    if isinstance(scope, str):
        scopes.extend(value for value in scope.split() if value)
    permissions = claims.get("permissions")
    if isinstance(permissions, list):
        scopes.extend(
            value
            for value in permissions
            if isinstance(value, str) and value not in scopes
        )
    return scopes


def _optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) else None
