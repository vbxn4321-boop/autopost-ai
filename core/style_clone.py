"""
core/style_clone.py — 스타일 클론(템플릿) 기능, 더미(Mock) 구현
사용자가 입력한 타겟 URL을 서버가 실제로 가져오지(fetch) 않는다.
(임의의 외부 URL을 서버가 요청하는 것은 SSRF 위험이 있고, 이번 기능은 데모 목적이므로
 URL을 해시해 미리 준비된 프리셋 스타일 중 하나를 결정적으로 골라 돌려주는 방식으로 구현한다.)
"""
import hashlib

STYLE_PRESETS = [
    {
        "name": "미니멀 화이트",
        "subtitle_font": "NanumGothic",
        "subtitle_color": "#FFFFFF",
        "subtitle_bg": "transparent",
        "stroke_color": "#000000",
        "stroke_width": 2,
        "subtitle_position": "bottom",
        "tone": "깔끔한",
    },
    {
        "name": "포인트 옐로우",
        "subtitle_font": "NanumSquareRound",
        "subtitle_color": "#FFE100",
        "subtitle_bg": "#000000",
        "stroke_color": "#000000",
        "stroke_width": 1,
        "subtitle_position": "center",
        "tone": "발랄한",
    },
    {
        "name": "프리미엄 블랙",
        "subtitle_font": "NanumMyeongjo",
        "subtitle_color": "#FFFFFF",
        "subtitle_bg": "#1a1a1a",
        "stroke_color": "#8b5cf6",
        "stroke_width": 1,
        "subtitle_position": "bottom",
        "tone": "전문적인",
    },
    {
        "name": "레트로 팝",
        "subtitle_font": "NanumPen",
        "subtitle_color": "#FF3B7F",
        "subtitle_bg": "transparent",
        "stroke_color": "#FFFFFF",
        "stroke_width": 3,
        "subtitle_position": "top",
        "tone": "유머러스한",
    },
]


def clone_style_from_url(target_url: str) -> dict:
    """
    target_url을 실제로 요청하지 않고, URL 문자열을 해시해 프리셋 중 하나를
    결정적으로(같은 URL → 항상 같은 프리셋) 선택해 반환한다.
    """
    if not target_url or not target_url.strip():
        raise ValueError("타겟 URL을 입력해주세요")

    digest = hashlib.sha256(target_url.strip().encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(STYLE_PRESETS)
    preset = STYLE_PRESETS[index]

    return {
        **preset,
        "source_url": target_url,
        "note": "이 기능은 데모용 더미 스타일 매칭입니다 — 실제로 대상 사이트에 접속하지 않고 "
                "입력하신 URL을 기반으로 준비된 스타일 프리셋 중 하나를 추천합니다.",
    }
