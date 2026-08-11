"""
core/ai_writer.py — AI 원고 자동 생성 엔진 (Google Gemini 무료 기반)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import GEMINI_API_KEY, GEMINI_MODEL
from core.platform_prompts import SYSTEM_PROMPT, get_prompt
from core.db import save_content_history


def generate_content(
    topic: str,
    platform: str,
    business_type: str = "음식점",
    location: str = "서울",
    keywords: str = "",
    tone: str = "친근한",
) -> dict:
    """
    AI 원고 생성 메인 함수 (Google Gemini 사용)

    Args:
        topic: 게시물 주제 (사용자 입력)
        platform: 플랫폼 ('instagram' | 'tiktok' | 'naver_blog' 등)
        business_type: 업종 (예: '카페', '미용실', '헬스장')
        location: 지역 (예: '강남구', '부산 해운대')
        keywords: 추가 SEO 키워드
        tone: 톤앤매너 (예: '친근한', '전문적인')

    Returns:
        dict: { title, caption, body, hashtags, full_post, platform }
    """
    if not GEMINI_API_KEY:
        return _fallback_response(platform, topic)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        user_prompt = get_prompt(
            platform=platform,
            topic=topic,
            business_type=business_type,
            location=location,
            keywords=keywords,
            tone=tone,
        )

        # JSON 형식으로 응답 요청
        full_prompt = user_prompt + "\n\n반드시 JSON 형식으로만 응답해주세요. 다른 텍스트 없이 JSON만."

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.8,
                max_output_tokens=8192,
                response_mime_type="application/json",
            )
        )

        raw = response.text.strip()

        # 마크다운 찌꺼기 제거 (안전하게)
        if raw.startswith("```"):
            import re
            # 백틱 3개로 둘러싸인 내용만 추출
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
            if match:
                raw = match.group(1).strip()
            else:
                # 닫는 백틱이 없으면 시작 백틱만 제거
                raw = re.sub(r'^```(?:json)?\s*', '', raw).strip()

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[AI Writer JSON Parse Error] {e}")
            print(f"[Raw Output] {raw}")
            raise ValueError(f"AI가 올바른 JSON 형식을 반환하지 않았습니다. 다시 시도해주세요. (에러: {e})")

        # 공통 필드 정규화
        normalized = _normalize_result(result, platform)
        normalized["platform"] = platform

        # 히스토리 저장
        save_content_history(
            platform=platform,
            topic=topic,
            business_type=business_type,
            location=location,
            title=normalized.get("title", ""),
            caption=normalized.get("caption", ""),
            body=normalized.get("body", ""),
            hashtags=", ".join(normalized.get("hashtags", [])),
        )

        return normalized

    except Exception as e:
        print(f"[AI Writer Error] {e}")
        return _fallback_response(platform, topic, error=str(e))


def analyze_photo(image_path: str) -> str:
    """
    사진을 Gemini Vision으로 분석해 원고 작성에 참고할 한국어 설명 문장을 반환한다.
    (PROJECT_PLAN.md에서 계획했던 '사진 자동 분석' 기능 — 기존에는 사용자가 사진 설명을
    직접 입력해야 했는데, 이 함수는 그 설명을 AI가 대신 만들어준다.)
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 설정되지 않아 사진 자동 분석을 사용할 수 없습니다")

    from google import genai
    from google.genai import types
    from PIL import Image

    client = genai.Client(api_key=GEMINI_API_KEY)
    img = Image.open(image_path)

    prompt = (
        "이 사진에 무엇이 보이는지 SNS 마케팅 원고 작성에 참고할 수 있도록 "
        "한국어 1~2문장으로 설명해줘. 다른 말 없이 설명 문장만 출력해."
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[prompt, img],
        config=types.GenerateContentConfig(temperature=0.4, max_output_tokens=300),
    )
    return response.text.strip()


def _normalize_result(result: dict, platform: str) -> dict:
    """플랫폼별로 다른 JSON 구조를 공통 구조로 정규화"""
    normalized = {
        "title": result.get("title", ""),
        "caption": result.get("caption", ""),
        "body": "",
        "hashtags": result.get("hashtags", []),
        "full_post": result.get("full_post", ""),
    }

    if platform == "naver_blog":
        sections = result.get("sections", [])
        body_parts = []
        for s in sections:
            body_parts.append(f"## {s.get('subtitle', '')}\n{s.get('content', '')}")
        normalized["body"] = "\n\n".join(body_parts)
        normalized["caption"] = result.get("intro", "")
        normalized["cta"] = result.get("cta", "")

        if not normalized["full_post"]:
            parts = [normalized["title"], result.get("intro", "")]
            parts.extend([f"## {s['subtitle']}\n{s['content']}" for s in sections])
            parts.append(result.get("cta", ""))
            normalized["full_post"] = "\n\n".join(filter(None, parts))

    else:
        # Instagram / TikTok / X / Threads / Facebook
        normalized["body"] = result.get("caption", "")
        if platform == "tiktok":
            normalized["hook_line"] = result.get("hook_line", "")

    # 해시태그 정리 (# 없으면 추가)
    normalized["hashtags"] = [
        tag if tag.startswith("#") else f"#{tag}"
        for tag in normalized.get("hashtags", [])
    ]

    return normalized


def _fallback_response(platform: str, topic: str, error: str = None) -> dict:
    """API 키 없거나 오류 시 fallback 응답"""
    msg = f"[데모] {topic}에 관한 {platform} 원고를 여기에 작성하세요.\n\nGemini API 키를 설정하면 AI가 자동으로 생성합니다."
    if error:
        msg += f"\n\n[오류: {error}]"
    return {
        "title": f"{topic} - {platform} 게시물",
        "caption": msg,
        "body": msg,
        "hashtags": ["#소상공인", "#마케팅", "#자동발행"],
        "full_post": msg,
        "platform": platform,
        "is_fallback": True,
    }


if __name__ == "__main__":
    result = generate_content(
        topic="오늘 신메뉴 아메리카노 출시! 2천원 할인 이벤트",
        platform="instagram",
        business_type="카페",
        location="강남구",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
