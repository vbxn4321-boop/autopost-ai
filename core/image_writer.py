"""
core/image_writer.py — 주제 텍스트 → 이미지 생성 프롬프트 → 실제 이미지 자동 생성
비용 0원 원칙에 따라, 이미지 생성은 API 키가 필요 없는 무료 공개 서비스인
Pollinations.ai(https://pollinations.ai)를 사용한다. (서드파티 무료 공개 서비스라
SLA가 없으므로 실패 시 사용자에게 명확한 에러를 반환하고, 가짜 이미지를 지어내지 않는다.)
"""
import sys
import uuid
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import GEMINI_API_KEY, GEMINI_MODEL, UPLOAD_DIR

POLLINATIONS_BASE_URL = "https://image.pollinations.ai/prompt"

MAX_IMAGE_DIMENSION = 2000  # 이보다 큰 사진(주로 휴대폰 원본 사진)은 줄여서 저장


def downscale_image_if_needed(image_path: str, max_dim: int = MAX_IMAGE_DIMENSION) -> None:
    """
    업로드/생성된 이미지가 너무 크면(특히 휴대폰 원본 사진은 4000px가 넘기도 함) 줄여서
    저장한다. 영상 합성(moviepy) 단계의 메모리 사용량을 크게 낮춰, 메모리가 작은
    서버(예: Render 무료 플랜 512MB)에서 서버가 다운되는 것을 방지하기 위함이다.
    실패해도 원본을 그대로 쓰면 되므로 예외를 삼키고 넘어간다.
    """
    from PIL import Image
    try:
        with Image.open(image_path) as img:
            if max(img.size) <= max_dim:
                return
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            img.convert("RGB").save(image_path, quality=88)
            print(f"[ImageWriter] 이미지 축소 완료: {image_path} -> {img.size}")
    except Exception as e:
        print(f"[ImageWriter] 이미지 축소 실패(원본 그대로 사용): {e}")


def generate_image_prompt(topic: str, platform: str = "instagram",
                           business_type: str = "", tone: str = "친근한") -> str:
    """
    Gemini로 '주제 텍스트'만 보고 이미지 생성용 영어 프롬프트를 만든다.
    (이미지 생성 모델은 대부분 영어 프롬프트에서 품질이 더 안정적이라 영어로 생성)
    """
    if not GEMINI_API_KEY:
        return f"a professional marketing photo related to: {topic}, {business_type}, high quality, clean composition"

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        instruction = (
            "너는 SNS 마케팅 이미지 생성 프롬프트 작가야. 아래 정보를 바탕으로 "
            "이미지 생성 AI(예: Stable Diffusion류)에 넣을 영어 프롬프트를 딱 한 줄로 작성해. "
            "마크다운, 굵은글씨(**), 글머리표, 콜론으로 구분된 항목 나열, 줄바꿈, 따옴표를 "
            "절대 쓰지 말고, 쉼표로 구분된 순수 영어 키워드/구절 나열 한 줄만 출력해."
        )
        user_prompt = f"주제: {topic}\n업종: {business_type}\n플랫폼: {platform}\n톤: {tone}"

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                temperature=0.9,
                max_output_tokens=200,
            ),
        )
        prompt = response.text.strip().strip('"')
        return prompt or topic
    except Exception as e:
        print(f"[ImageWriter] 프롬프트 생성 실패, 주제 텍스트 그대로 사용: {e}")
        return f"a professional marketing photo related to: {topic}, high quality, clean composition"


def generate_image(prompt: str, width: int = 1080, height: int = 1920) -> str:
    """
    Pollinations.ai 무료 이미지 생성 API를 호출해 이미지를 uploads/ 에 저장하고 로컬 경로를 반환한다.
    실패 시 예외를 던진다 (호출부에서 사용자에게 명확히 안내해야 함 — 가짜 이미지로 대체하지 않음).
    """
    url = f"{POLLINATIONS_BASE_URL}/{requests.utils.quote(prompt)}"
    params = {"width": width, "height": height, "nologo": "true"}

    resp = requests.get(url, params=params, timeout=60)
    if resp.status_code != 200 or not resp.content:
        raise RuntimeError(
            f"무료 이미지 생성 서비스(Pollinations.ai) 응답 실패 (status={resp.status_code}). "
            "잠시 후 다시 시도하거나 직접 사진을 업로드해주세요."
        )

    content_type = resp.headers.get("Content-Type", "")
    if "image" not in content_type:
        raise RuntimeError("이미지 생성 서비스가 이미지가 아닌 응답을 반환했습니다. 다시 시도해주세요.")

    filename = f"{uuid.uuid4().hex}_generated.jpg"
    save_path = UPLOAD_DIR / filename
    with open(save_path, "wb") as f:
        f.write(resp.content)

    downscale_image_if_needed(str(save_path))
    return str(save_path)


def generate_image_from_topic(topic: str, platform: str = "instagram",
                               business_type: str = "", tone: str = "친근한") -> dict:
    """주제 텍스트 하나로 프롬프트 생성 + 이미지 생성까지 한 번에 처리"""
    settings_map = {
        "instagram": (1080, 1350), "tiktok": (1080, 1920), "threads": (1080, 1350),
        "facebook": (1080, 1080), "x_twitter": (1200, 675), "naver_blog": (1280, 720),
    }
    width, height = settings_map.get(platform, (1080, 1350))

    prompt = generate_image_prompt(topic, platform, business_type, tone)
    image_path = generate_image(prompt, width=width, height=height)

    return {"image_path": image_path, "prompt_used": prompt}
