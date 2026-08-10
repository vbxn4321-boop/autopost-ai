"""
core/oauth_naver.py — 네이버 로그인(OAuth2) 인가 코드 흐름
블로그 글쓰기(writePost.json)는 Client ID/Secret 헤더가 아니라
사용자가 로그인 후 발급되는 access_token(Bearer)이 있어야 호출 가능하다.
"""
import sys
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_REDIRECT_URI

AUTHORIZE_URL = "https://nid.naver.com/oauth2.0/authorize"
TOKEN_URL = "https://nid.naver.com/oauth2.0/token"


def get_authorize_url(state: str) -> str:
    """사용자를 네이버 로그인 동의 화면으로 보내는 URL 생성"""
    params = {
        "response_type": "code",
        "client_id": NAVER_CLIENT_ID,
        "redirect_uri": NAVER_REDIRECT_URI,
        "state": state,
    }
    query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return f"{AUTHORIZE_URL}?{query}"


def exchange_code_for_token(code: str, state: str) -> dict:
    """인가 코드를 access_token으로 교환"""
    params = {
        "grant_type": "authorization_code",
        "client_id": NAVER_CLIENT_ID,
        "client_secret": NAVER_CLIENT_SECRET,
        "code": code,
        "state": state,
    }
    resp = requests.get(TOKEN_URL, params=params, timeout=15)
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"네이버 토큰 교환 실패: {data}")
    return data


def refresh_access_token(refresh_token: str) -> dict:
    """만료된 access_token을 refresh_token으로 갱신"""
    params = {
        "grant_type": "refresh_token",
        "client_id": NAVER_CLIENT_ID,
        "client_secret": NAVER_CLIENT_SECRET,
        "refresh_token": refresh_token,
    }
    resp = requests.get(TOKEN_URL, params=params, timeout=15)
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"네이버 토큰 갱신 실패: {data}")
    return data
