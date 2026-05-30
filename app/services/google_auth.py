from typing import Any
from urllib.parse import urlencode

import requests

from app.core.errors import AppError
from app.schemas import AuthUserResponse


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = "openid email profile"


class GoogleAuthService:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def build_authorization_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": GOOGLE_SCOPES,
            "state": state,
            "include_granted_scopes": "true",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        try:
            response = requests.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=20,
            )
        except requests.RequestException as exc:
            raise AppError(
                status_code=502,
                code="google_token_request_failed",
                message="Google token request failed.",
            ) from exc

        if response.status_code != 200:
            raise AppError(
                status_code=502,
                code="google_token_exchange_failed",
                message=self._extract_google_error(response),
            )
        return response.json()

    def get_user_info(self, access_token: str) -> AuthUserResponse:
        try:
            response = requests.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=20,
            )
        except requests.RequestException as exc:
            raise AppError(
                status_code=502,
                code="google_userinfo_request_failed",
                message="Google userinfo request failed.",
            ) from exc

        if response.status_code != 200:
            raise AppError(
                status_code=502,
                code="google_userinfo_failed",
                message=self._extract_google_error(response),
            )

        data = response.json()
        return AuthUserResponse(
            google_sub=data.get("sub", ""),
            email=data.get("email", ""),
            name=data.get("name"),
            picture=data.get("picture"),
            email_verified=bool(data.get("email_verified", False)),
        )

    def _extract_google_error(self, response: requests.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return "Google OAuth request failed."

        error = data.get("error_description") or data.get("error")
        if error:
            return f"Google OAuth request failed: {error}"
        return "Google OAuth request failed."
