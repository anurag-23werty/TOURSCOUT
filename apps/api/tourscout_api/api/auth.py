"""Signed-in users: verify the Neon Auth (managed Better Auth) access token the web app sends as `Authorization: Bearer`.

The browser gets a 15-minute EdDSA JWT from `authClient.token()`; we check its signature against Neon Auth's JWKS
(`<NEON_AUTH_URL>/.well-known/jwks.json`), plus `iss` and `aud` (both the auth URL's origin) and `exp`. No cookies reach
this API, so the API and the site can live on different domains.

    NEON_AUTH_URL=https://ep-xxx.neonauth.<region>.aws.neon.tech/neondb/auth   → sign-in enabled
    unset                                                                    → guests only
"""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import anyio
import httpx
import jwt


class AuthError(Exception):
    """The token is missing, malformed, expired, forged or for another app."""


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str
    email_verified: bool


class JwtVerifier:
    def __init__(self, auth_url: str, key_for: Callable[[str], Any] | None = None, leeway_s: int = 30) -> None:
        auth_url = auth_url.rstrip("/")
        parts = urlsplit(auth_url)
        self.issuer = f"{parts.scheme}://{parts.netloc}"
        self.leeway_s = leeway_s
        if key_for is None:
            # Keys are cached in memory; an unknown `kid` (Neon rotated its key) triggers one refetch.
            jwks = jwt.PyJWKClient(f"{auth_url}/.well-known/jwks.json", cache_keys=True, lifespan=600, timeout=10)
            key_for = lambda token: jwks.get_signing_key_from_jwt(token).key  # noqa: E731
        self.key_for = key_for

    @classmethod
    def from_env(cls) -> "JwtVerifier | None":
        url = os.getenv("NEON_AUTH_URL", "").strip()
        return cls(url) if url else None

    async def verify(self, token: str) -> User:
        try:
            key = await anyio.to_thread.run_sync(self.key_for, token)  # may fetch the JWKS over the network
            claims = jwt.decode(token, key, algorithms=["EdDSA"], issuer=self.issuer, audience=self.issuer,
                                leeway=self.leeway_s, options={"require": ["exp", "iss", "aud", "sub"]})
        except (jwt.PyJWTError, ValueError) as exc:
            raise AuthError(str(exc)) from None
        if claims.get("banned"):
            raise AuthError("this account is suspended")
        return User(id=str(claims["sub"]), email=str(claims.get("email") or ""), name=str(claims.get("name") or ""),
                    email_verified=bool(claims.get("emailVerified")))


class AccountDeleter:
    """Removes a login from Neon Auth (self-service /delete-user is off in managed Neon Auth, so the API does it).

    Needs a Neon API key with access to the project, plus the project and branch ids (Neon console → Settings).
    """

    API = "https://console.neon.tech/api/v2"

    def __init__(self, api_key: str, project_id: str, branch_id: str, http: httpx.AsyncClient | None = None) -> None:
        self.url = f"{self.API}/projects/{project_id}/branches/{branch_id}/auth/users"
        self.headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        self.http = http

    @classmethod
    def from_env(cls) -> "AccountDeleter | None":
        key, project, branch = (os.getenv(n, "").strip() for n in ("NEON_API_KEY", "NEON_PROJECT_ID", "NEON_BRANCH_ID"))
        return cls(key, project, branch) if key and project and branch else None

    async def delete(self, user_id: str) -> None:
        async with (httpx.AsyncClient(timeout=15) if self.http is None else nullcontext(self.http)) as http:
            r = await http.delete(f"{self.url}/{user_id}", headers=self.headers)
        if r.status_code not in (200, 202, 204, 404):  # 404: already gone
            raise RuntimeError(f"Neon API answered {r.status_code}")

