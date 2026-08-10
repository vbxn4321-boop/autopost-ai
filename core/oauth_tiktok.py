"""
core/oauth_tiktok.py — 틱톡 로그인(OAuth2 + PKCE) 인가 코드 흐름
Content Posting API(video/init)는 CLIENT_KEY/SECRET이 아니라
사용자가 로그인 후 발급되는 access_token(Bearer, scope=video.publish)이 있어야 호출 가능하다.
틱톡 v2 로그인은 PKCE(code_verifier/code_challenge)가 필수 요건이다.
"""
import sys
import base64
import hashlib
import secrets
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REDIRECT_URI

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
SCOPE = "video.publish"


def generate_pkce_pair() -> tuple[str, str]:
    """code_verifier와 그에 대응하는 code_challenge(S256) 생성"""
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return code_verifier, code_challenge


def get_authorize_url(state: str, code_challenge: str) -> str:
    """사용자를 틱톡 로그인 동의 화면으로 보내는 URL 생성"""
    params = {
        "client_key": TIKTOK_CLIENT_KEY,
        "scope": SCOPE,
        "response_type": "code",
        "redirect_uri": TIKTOK_REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return f"{AUTHORIZE_URL}?{query}"


def exchange_code_for_token(code: str, code_verifier: str) -> dict:
    """인가 코드를 access_token으로 교환"""
    payload = {
        "client_key": TIKTOK_CLIENT_KEY,
        "client_secret": TIKTOK_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": TIKTOK_REDIRECT_URI,
        "code_verifier": code_verifier,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=15)
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"틱톡 토큰 교환 실패: {data}")
    return data


def refresh_access_token(refresh_token: str) -> dict:
    """만료된 access_token을 refresh_token으로 갱신"""
    payload = {
        "client_key": TIKTOK_CLIENT_KEY,
        "client_secret": TIKTOK_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=15)
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"틱톡 토큰 갱신 실패: {data}")
    return data
