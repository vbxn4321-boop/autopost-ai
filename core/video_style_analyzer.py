"""
core/video_style_analyzer.py — 프레임 캡처 기반 저비용 영상 스타일 분석
영상 전체를 API로 분석하지 않고, ffmpeg로 몇 개의 프레임만 캡처해
Gemini Vision에 이미지로 전달함으로써 분석 비용을 절감한다.
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import GEMINI_API_KEY, GEMINI_MODEL, OUTPUT_DIR

DEFAULT_STYLE = {
    "subtitle_position": "bottom",
    "font_size_ratio": 0.04,
    "subtitle_color": "white",
    "stroke_color": "black",
    "stroke_width": 2,
    "bg_color": "transparent",
    "reasoning": "분석 실패 또는 API 키 없음 — 기본 스타일 적용",
}


def capture_frames(video_path: str, num_frames: int = 4) -> list[str]:
    """
    영상 전체가 아니라 균등 간격의 프레임 N장만 캡처한다 (비용 절감 핵심 로직).
    반환값: 캡처된 임시 jpg 파일 경로 리스트
    """
    import ffmpeg

    probe = ffmpeg.probe(video_path)
    duration = float(probe["format"]["duration"])

    frame_dir = OUTPUT_DIR / f"_frames_{uuid.uuid4().hex[:8]}"
    frame_dir.mkdir(exist_ok=True)

    frame_paths = []
    for i in range(num_frames):
        # 영상 맨 처음/끝은 암전 구간일 수 있어 5%~95% 구간에서만 균등 추출
        ts = duration * (0.05 + 0.9 * i / max(num_frames - 1, 1))
        out_path = frame_dir / f"frame_{i}.jpg"
        (
            ffmpeg
            .input(video_path, ss=ts)
            .output(str(out_path), vframes=1, loglevel="quiet")
            .overwrite_output()
            .run(quiet=True)
        )
        if out_path.exists():
            frame_paths.append(str(out_path))

    return frame_paths


def analyze_style(video_path: str, num_frames: int = 4) -> dict:
    """
    영상에서 캡처한 프레임 몇 장만 Gemini Vision에 보내 자막 스타일(위치/폰트크기비율/색상)을 추천받는다.
    실패 시 무난한 기본값(DEFAULT_STYLE)을 반환한다.
    """
    if not GEMINI_API_KEY:
        return DEFAULT_STYLE

    frame_paths = []
    try:
        frame_paths = capture_frames(video_path, num_frames)
        if not frame_paths:
            return DEFAULT_STYLE

        from google import genai
        from google.genai import types
        from PIL import Image
        import json
        import re

        client = genai.Client(api_key=GEMINI_API_KEY)
        images = [Image.open(p) for p in frame_paths]

        prompt = (
            "다음은 짧은 SNS 영상에서 균등 간격으로 캡처한 프레임들입니다. "
            "영상의 밝기/구도/기존 텍스트 유무를 보고, 이 영상 위에 자막을 얹을 때 "
            "가장 잘 어울리는 스타일을 JSON으로만 답하세요.\n"
            '형식: {"subtitle_position": "top|center|bottom", '
            '"font_size_ratio": 0.03~0.06 사이 숫자, '
            '"subtitle_color": "white|black|yellow 등 CSS 색상명", '
            '"stroke_color": "CSS 색상명", "stroke_width": 1~4 정수, '
            '"bg_color": "transparent 또는 CSS 색상명", '
            '"reasoning": "왜 이렇게 추천했는지 한국어 한 문장"}'
        )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt, *images],
            config=types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=1024,
                response_mime_type="application/json",
            ),
        )

        raw = response.text.strip()
        if raw.startswith("```"):
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
            raw = match.group(1).strip() if match else raw

        result = json.loads(raw)
        merged = {**DEFAULT_STYLE, **result}
        return merged

    except Exception as e:
        print(f"[VideoStyleAnalyzer] 분석 실패, 기본값 사용: {e}")
        return DEFAULT_STYLE
    finally:
        # 캡처한 임시 프레임 파일 정리
        for p in frame_paths:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass
        if frame_paths:
            try:
                Path(frame_paths[0]).parent.rmdir()
            except Exception:
                pass
