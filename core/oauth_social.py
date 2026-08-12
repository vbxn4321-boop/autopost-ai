import requests
from config import (
    KAKAO_CLIENT_ID, KAKAO_REDIRECT_URI,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
)

def get_kakao_auth_url(state: str) -> str:
    if not KAKAO_CLIENT_ID:
        return "/?error=KAKAO_CLIENT_ID_NOT_SET"
    return f"https://kauth.kakao.com/oauth/authorize?client_id={KAKAO_CLIENT_ID}&redirect_uri={KAKAO_REDIRECT_URI}&response_type=code&state={state}"

def get_kakao_user_info(code: str) -> dict:
    # 1. Exchange code for token
    token_url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_CLIENT_ID,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code
    }
    res = requests.post(token_url, data=data)
    if not res.ok:
        raise Exception(f"Kakao token fetch failed: {res.text}")
    
    access_token = res.json().get("access_token")
    
    # 2. Get user info
    user_url = "https://kapi.kakao.com/v2/user/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    user_res = requests.get(user_url, headers=headers)
    
    if not user_res.ok:
        raise Exception(f"Kakao user info fetch failed: {user_res.text}")
        
    user_data = user_res.json()
    kakao_account = user_data.get("kakao_account", {})
    email = kakao_account.get("email")
    if not email:
        # Fallback pseudo-email if kakao didn't provide one
        email = f"kakao_{user_data.get('id')}@kakao.local"
        
    return {"email": email, "id": user_data.get("id")}


def get_google_auth_url(state: str) -> str:
    if not GOOGLE_CLIENT_ID:
        return "/?error=GOOGLE_CLIENT_ID_NOT_SET"
    return f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&response_type=code&scope=email profile&state={state}"

def get_google_user_info(code: str) -> dict:
    # 1. Exchange code for token
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "code": code
    }
    res = requests.post(token_url, data=data)
    if not res.ok:
        raise Exception(f"Google token fetch failed: {res.text}")
    
    access_token = res.json().get("access_token")
    
    # 2. Get user info
    user_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    user_res = requests.get(user_url, headers=headers)
    
    if not user_res.ok:
        raise Exception(f"Google user info fetch failed: {user_res.text}")
        
    user_data = user_res.json()
    email = user_data.get("email")
    if not email:
        email = f"google_{user_data.get('id')}@google.local"
        
    return {"email": email, "id": user_data.get("id")}
