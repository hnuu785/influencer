from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import session_dependency
from app.models import GoogleConnection, User, utc_now


SESSION_COOKIE = "storilog_session"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class TokenSigner:
    def __init__(self, secret: str):
        self.secret = secret.encode()

    def sign(self, payload: dict[str, Any], expires_in_seconds: int) -> str:
        body = {
            **payload,
            "exp": int(time.time()) + expires_in_seconds,
        }
        encoded = _b64encode(
            json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
        )
        signature = _b64encode(
            hmac.new(self.secret, encoded.encode(), hashlib.sha256).digest()
        )
        return f"{encoded}.{signature}"

    def verify(self, token: str, expected_type: str) -> dict[str, Any]:
        try:
            encoded, signature = token.split(".", 1)
            expected_signature = _b64encode(
                hmac.new(self.secret, encoded.encode(), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(signature, expected_signature):
                raise ValueError("bad signature")
            payload = json.loads(_b64decode(encoded))
        except (ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 인증 정보입니다.",
            ) from exc
        if payload.get("type") != expected_type or payload.get("exp", 0) < time.time():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="인증 정보가 만료되었거나 올바르지 않습니다.",
            )
        return payload


class TokenCipher:
    def __init__(self, secret: str):
        digest = hashlib.sha256(secret.encode()).digest()
        self.fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, payload: dict[str, Any]) -> str:
        return self.fernet.encrypt(json.dumps(payload).encode()).decode()

    def decrypt(self, token: str) -> dict[str, Any]:
        try:
            return json.loads(self.fernet.decrypt(token.encode()))
        except (InvalidToken, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google 연결 정보를 확인할 수 없습니다.",
            ) from exc


def set_session_cookie(
    response: Response,
    settings: Settings,
    signer: TokenSigner,
    user_id: str,
) -> None:
    token = signer.sign({"type": "session", "user_id": user_id}, 60 * 60 * 24 * 30)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        secure=not settings.is_development,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


async def current_user(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    session: AsyncSession = Depends(session_dependency),
) -> User:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google 로그인이 필요합니다.",
        )
    signer = TokenSigner(request.app.state.settings.session_secret)
    payload = signer.verify(session_token, "session")
    user = await session.get(User, payload["user_id"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자 계정을 찾을 수 없습니다.",
        )
    user.last_active_at = utc_now()
    user.expires_at = utc_now() + timedelta(days=180)
    await session.commit()
    return user


def google_authorization_url(
    settings: Settings,
    *,
    redirect_uri: str,
    state: str,
    calendar: bool = False,
) -> str:
    scopes = ["openid", "email", "profile"]
    if calendar:
        scopes.append("https://www.googleapis.com/auth/calendar.readonly")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "include_granted_scopes": "true",
    }
    if calendar:
        params.update({"access_type": "offline", "prompt": "consent"})
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def exchange_google_code(
    settings: Settings,
    *,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
    if response.is_error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google 인증을 완료하지 못했습니다.",
        )
    return response.json()


async def google_userinfo(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.is_error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google 사용자 정보를 가져오지 못했습니다.",
        )
    return response.json()


async def refresh_google_token(
    settings: Settings,
    connection: GoogleConnection,
    cipher: TokenCipher,
) -> dict[str, Any]:
    if not connection.encrypted_token:
        raise HTTPException(status_code=409, detail="Calendar 연결이 필요합니다.")
    token = cipher.decrypt(connection.encrypted_token)
    expires_at = connection.token_expires_at
    if expires_at and expires_at > datetime.now(timezone.utc) + timedelta(minutes=2):
        return token
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=409, detail="Calendar를 다시 연결해 주세요.")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if response.is_error:
        raise HTTPException(status_code=409, detail="Calendar를 다시 연결해 주세요.")
    refreshed = response.json()
    token.update(refreshed)
    connection.encrypted_token = cipher.encrypt(token)
    connection.token_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=int(refreshed.get("expires_in", 3600))
    )
    return token


async def upsert_google_user(
    session: AsyncSession,
    userinfo: dict[str, Any],
) -> User:
    user = await session.scalar(
        select(User).where(User.google_subject == str(userinfo["sub"]))
    )
    if user is None:
        user = User(
            google_subject=str(userinfo["sub"]),
            email=userinfo.get("email", ""),
            name=userinfo.get("name") or userinfo.get("email", "스토리로그 사용자"),
            picture_url=userinfo.get("picture"),
            expires_at=utc_now() + timedelta(days=180),
        )
        session.add(user)
        await session.flush()
        session.add(GoogleConnection(user_id=user.id))
    else:
        user.email = userinfo.get("email", user.email)
        user.name = userinfo.get("name", user.name)
        user.picture_url = userinfo.get("picture", user.picture_url)
        user.last_active_at = utc_now()
        user.expires_at = utc_now() + timedelta(days=180)
    await session.commit()
    await session.refresh(user)
    return user
