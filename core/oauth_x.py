"""
core/oauth_x.py — X(트위터) 3-legged OAuth 1.0a 사용자 로그인 흐름
기존에는 .env에 저장된 앱 전체 공용 access_token/secret 1개로만 발행했으나,
사장님마다 본인 계정으로 발행할 수 있도록 사용자별 OAuth 연결로 전환한다.
config.py에 이미 있는 X_API_KEY/X_API_SECRET(OAuth 1.0a 앱 등록 정보, consumer key/secret)를
그대로 재사용하므로, X 개발자 포털에서 새 앱을 만들 필요 없이 기존 앱의
"User authentication settings"에 콜백 URL만 등록하면 된다.
"""
import sys
from pathlib import Path

import tweepy

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import X_API_KEY, X_API_SECRET


def get_authorization_url_and_token(callback_url: str):
    """
    request_token을 발급받고, 사용자를 X 인증 동의 화면으로 보내는 URL을 반환.

    Returns:
        (auth_url, request_token): request_token은 세션에 저장해뒀다가
        콜백에서 exchange_verifier_for_token()에 그대로 넘겨야 한다.
    """
    handler = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET, callback=callback_url)
    auth_url = handler.get_authorization_url()
    request_token = {
        "oauth_token": handler.request_token["oauth_token"],
        "oauth_token_secret": handler.request_token["oauth_token_secret"],
    }
    return auth_url, request_token


def exchange_verifier_for_token(request_token: dict, verifier: str):
    """
    콜백에서 받은 oauth_verifier와, 로그인 시작 시 저장해둔 request_token으로
    사용자별 access_token/access_token_secret을 발급받는다.

    Returns:
        (access_token, access_token_secret)
    """
    handler = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET)
    handler.request_token = {
        "oauth_token": request_token["oauth_token"],
        "oauth_token_secret": request_token["oauth_token_secret"],
    }
    access_token, access_token_secret = handler.get_access_token(verifier)
    return access_token, access_token_secret
