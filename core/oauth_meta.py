"""
core/oauth_meta.py — 메타(페이스북 로그인) OAuth2 인가 코드 흐름
인스타그램/페이스북 게시(media, feed 엔드포인트)는 앱 자격증명이 아니라
사용자가 로그인해서 연결한 페이스북 페이지의 "페이지 액세스 토큰"이 있어야 호출 가능하다.
장기(long-lived) 사용자 토큰에서 파생된 페이지 액세스 토큰은 만료되지 않으므로
네이버/틱톡과 달리 refresh_token 로직이 필요 없다.
"""
import sys
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import META_APP_ID, META_APP_SECRET, META_REDIRECT_URI

GRAPH_VERSION = "v19.0"
AUTHORIZE_URL = "https://www.facebook.com/v19.0/dialog/oauth"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
SCOPE = "pages_show_list,pages_read_engagement,pages_manage_posts,instagram_basic,instagram_content_publish,business_management"


def get_authorize_url(state: str) -> str:
    """사용자를 페이스북 로그인 동의 화면으로 보내는 URL 생성"""
    params = {
        "client_id": META_APP_ID,
        "redirect_uri": META_REDIRECT_URI,
        "state": state,
        "scope": SCOPE,
        "response_type": "code",
    }
    query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
    return f"{AUTHORIZE_URL}?{query}"


def exchange_code_for_token(code: str) -> str:
    """인가 코드를 단기(short-lived) 사용자 액세스 토큰으로 교환"""
    params = {
        "client_id": META_APP_ID,
        "client_secret": META_APP_SECRET,
        "redirect_uri": META_REDIRECT_URI,
        "code": code,
    }
    resp = requests.get(f"{GRAPH_BASE}/oauth/access_token", params=params, timeout=15)
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"메타 토큰 교환 실패: {data}")
    return data["access_token"]


def get_long_lived_token(short_token: str) -> str:
    """단기 사용자 토큰을 장기(약 60일) 사용자 토큰으로 교환"""
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": META_APP_ID,
        "client_secret": META_APP_SECRET,
        "fb_exchange_token": short_token,
    }
    resp = requests.get(f"{GRAPH_BASE}/oauth/access_token", params=params, timeout=15)
    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"메타 장기 토큰 교환 실패: {data}")
    return data["access_token"]


def get_page_and_ig_account(user_token: str) -> dict:
    """
    사용자 토큰으로 관리 중인 페이스북 페이지 목록을 조회해,
    인스타그램 비즈니스 계정이 연결된 첫 번째 페이지 정보를 반환.

    Returns:
        dict: { page_id, page_name, page_access_token, ig_user_id (없으면 None) }
    """
    resp = requests.get(
        f"{GRAPH_BASE}/me/accounts",
        params={"access_token": user_token, "fields": "id,name,access_token"},
        timeout=15,
    )
    data = resp.json()
    pages = data.get("data", [])
    if not pages:
        raise ValueError(f"연결된 페이스북 페이지를 찾을 수 없습니다: {data}")

    for page in pages:
        page_id = page["id"]
        page_access_token = page["access_token"]

        ig_resp = requests.get(
            f"{GRAPH_BASE}/{page_id}",
            params={"fields": "instagram_business_account", "access_token": page_access_token},
            timeout=15,
        )
        ig_data = ig_resp.json()
        ig_account = ig_data.get("instagram_business_account")

        if ig_account:
            return {
                "page_id": page_id,
                "page_name": page.get("name", ""),
                "page_access_token": page_access_token,
                "ig_user_id": ig_account["id"],
            }

    # 인스타그램이 연결된 페이지가 없으면, 첫 번째 페이지만이라도 반환 (페이스북 게시는 가능)
    first = pages[0]
    return {
        "page_id": first["id"],
        "page_name": first.get("name", ""),
        "page_access_token": first["access_token"],
        "ig_user_id": None,
    }
