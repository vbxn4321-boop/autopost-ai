"""
app.py — Flask 메인 애플리케이션
소상공인 올인원 SNS 원고 & 동영상 AI 자동 발행 시스템
"""

import os
import sys
import json
import uuid
import time
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Windows 한글 콘솔(cp949)은 이모지를 인코딩하지 못해 print()에서 그대로 죽는다 —
# 표준출력을 UTF-8로 강제해 어떤 콘솔 코드페이지에서도 안전하게 로그를 찍도록 한다.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from config import (
    FLASK_SECRET_KEY, FLASK_DEBUG,
    UPLOAD_DIR, OUTPUT_DIR,
    ALLOWED_VIDEO_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_AUDIO_EXTENSIONS,
    MAX_UPLOAD_SIZE_MB, PLATFORM_SETTINGS, PLANS,
)
from core.db import (
    init_db, create_scheduled_post, get_all_scheduled_posts, delete_scheduled_post,
    save_oauth_token, get_oauth_token, get_brand_profile, save_brand_profile,
    create_user, get_user_by_email, get_user_by_id,
)
from core.ai_writer import generate_content

# ─── Flask 앱 초기화 ──────────────────────────────────────────
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# DB 초기화
init_db()

# 스케줄러 시작 (WEEK 5)
from core.scheduler import PostScheduler
post_scheduler = PostScheduler()
post_scheduler.start()


# ─── 유틸 함수 ───────────────────────────────────────────────

def allowed_file(filename: str, file_type: str = "video") -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if file_type == "video":
        return ext in ALLOWED_VIDEO_EXTENSIONS
    if file_type == "audio":
        return ext in ALLOWED_AUDIO_EXTENSIONS
    return ext in ALLOWED_IMAGE_EXTENSIONS


def save_upload(file) -> str:
    """업로드 파일 저장 및 경로 반환"""
    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    save_path = UPLOAD_DIR / unique_name
    file.save(str(save_path))
    return str(save_path)


def login_required(f):
    """
    로그인(세션에 user_id 저장) 여부를 확인하는 데코레이터.
    fetch()로 호출되는 /api/* 라우트는 401 JSON을, 브라우저가 직접 이동하는
    /auth/*/login 라우트는 홈으로 리다이렉트해 각각 프론트/사용자가 처리할 수 있게 한다.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/auth/"):
                return redirect("/")
            return jsonify({"success": False, "error": "로그인이 필요합니다"}), 401
        return f(*args, **kwargs)
    return decorated


# ─── 라우트 ──────────────────────────────────────────────────

@app.route("/")
def index():
    """메인 UI 페이지"""
    return render_template("index.html", platforms=PLATFORM_SETTINGS)


# ─── API: 계정 (회원가입 / 로그인 / 로그아웃) ────────────────

@app.route("/api/signup", methods=["POST"])
def api_signup():
    """이메일+비밀번호 회원가입. 이메일 인증/비밀번호 재설정은 이번 범위 밖."""
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        if not email or "@" not in email:
            return jsonify({"success": False, "error": "올바른 이메일을 입력해주세요"}), 400
        if len(password) < 8:
            return jsonify({"success": False, "error": "비밀번호는 8자 이상이어야 합니다"}), 400
        if get_user_by_email(email):
            return jsonify({"success": False, "error": "이미 가입된 이메일입니다"}), 400

        user_id = create_user(email, generate_password_hash(password))
        session["user_id"] = user_id
        return jsonify({"success": True, "email": email})

    except Exception as e:
        print(f"[API /signup 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/login", methods=["POST"])
def api_login():
    """이메일+비밀번호 로그인"""
    try:
        data = request.get_json() or {}
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        user = get_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"success": False, "error": "이메일 또는 비밀번호가 올바르지 않습니다"}), 401

        session["user_id"] = user["id"]
        return jsonify({"success": True, "email": user["email"]})

    except Exception as e:
        print(f"[API /login 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/me", methods=["GET"])
def api_me():
    """현재 로그인 상태 조회 — 프론트 초기 진입 시 최우선으로 호출"""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": True, "logged_in": False})

    user = get_user_by_id(user_id)
    if not user:
        # 세션은 있으나 계정이 사라진 경우(DB 초기화 등) — 세션 정리
        session.clear()
        return jsonify({"success": True, "logged_in": False})

    return jsonify({"success": True, "logged_in": True, "email": user["email"]})


# ─── API: 브랜드 프로필 (최초 1회 설정, 이후 모든 원고 생성에 자동 반영) ────

@app.route("/api/brand-profile", methods=["GET"])
@login_required
def api_get_brand_profile():
    """저장된 브랜드 프로필 조회. 없으면 data: null (프론트에서 최초 방문 여부 판단에 사용)"""
    profile = get_brand_profile(session["user_id"])
    return jsonify({"success": True, "data": profile})


@app.route("/api/brand-profile", methods=["POST"])
@login_required
def api_save_brand_profile():
    """브랜드 프로필 저장/수정"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "JSON 데이터가 필요합니다"}), 400

        brand_name = data.get("brand_name", "").strip()
        if not brand_name:
            return jsonify({"success": False, "error": "가게 이름을 입력해주세요"}), 400

        save_brand_profile(
            user_id=session["user_id"],
            brand_name=brand_name,
            business_type=data.get("business_type", "카페"),
            location=data.get("location", "서울"),
            tone=data.get("tone", "친근한"),
            description=data.get("description", ""),
            signature_items=data.get("signature_items", ""),
            keywords=data.get("keywords", ""),
        )

        return jsonify({"success": True, "data": get_brand_profile(session["user_id"])})

    except Exception as e:
        print(f"[API /brand-profile 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── API: 원고 생성 ──────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
@login_required
def api_generate():
    """
    AI 원고 생성 API
    
    Request JSON:
        topic: str          - 게시물 주제
        platform: str       - 플랫폼 ('instagram' | 'tiktok' | 'danggeun' | 'naver_blog' 등)
        business_type: str  - 업종 (선택)
        location: str       - 지역 (선택)
        keywords: str       - SEO 키워드 (선택)
        tone: str           - 톤앤매너 (선택)
    
    Response JSON:
        success: bool
        data: { title, caption, body, hashtags, full_post }
    """
    try:
        # --- 수익 모델 가상 로직 (세션 기반 무료 횟수 차감) ---
        usage_count = session.get("usage_count", 0)
        max_free_uses = PLANS["FREE"]["max_generations_per_day"]
        
        if usage_count >= max_free_uses:
            return jsonify({"success": False, "error": "LIMIT_EXCEEDED"}), 403
            
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "JSON 데이터가 필요합니다"}), 400

        topic = data.get("topic", "").strip()
        platform = data.get("platform", "instagram")
        business_type = data.get("business_type", "음식점")
        location = data.get("location", "서울")
        keywords = data.get("keywords", "")
        tone = data.get("tone", "친근한")

        if not topic:
            return jsonify({"success": False, "error": "주제를 입력해주세요"}), 400

        # 브랜드 프로필이 설정되어 있으면 가게 이름/소개/대표 메뉴를 자동으로 반영,
        # 키워드는 요청에 없을 때만 프로필 값으로 보충
        brand = get_brand_profile(session["user_id"]) or {}
        keywords = keywords or brand.get("keywords", "")

        result = generate_content(
            topic=topic,
            platform=platform,
            business_type=business_type,
            location=location,
            keywords=keywords,
            tone=tone,
            brand_name=brand.get("brand_name", ""),
            description=brand.get("description", ""),
            signature_items=brand.get("signature_items", ""),
            user_id=session["user_id"],
        )

        # 횟수 증가
        session["usage_count"] = usage_count + 1

        return jsonify({"success": True, "data": result})

    except Exception as e:
        print(f"[API /generate 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/refine-content", methods=["POST"])
@login_required
def api_refine_content():
    """
    AI 원고 다듬기 (요술봉) API
    
    Request JSON:
        content: str
        instruction: str
    """
    try:
        data = request.get_json()
        content = data.get("content", "").strip()
        instruction = data.get("instruction", "").strip()
        
        if not content or not instruction:
            return jsonify({"success": False, "error": "원고와 다듬기 지시사항이 필요합니다."}), 400
            
        from core.ai_writer import refine_content
        refined = refine_content(content, instruction)
        
        return jsonify({"success": True, "data": {"content": refined}})
        
    except Exception as e:
        print(f"[API /refine-content 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── API: 틱톡 도메인 인증 라우트 ───────────────────────────────────

@app.route("/tiktoks7SekCpH6YGzzbvFLHt2U8wbRZVqkOCv.txt", methods=["GET"])
def tiktok_verification():
    """틱톡 Web 플랫폼 도메인 인증(Signature file) 전용 라우트"""
    return "tiktok-developers-site-verification=s7SekCpH6YGzzbvFLHt2U8wbRZVqkOCv"

# ─── API: 영상 업로드 ─────────────────────────────────────────

@app.route("/api/upload-video", methods=["POST"])
@login_required
def api_upload_video():
    """
    영상 파일 업로드 + 선택적 Whisper STT 처리
    
    Form Data:
        video: File         - 영상 파일
        run_stt: bool       - STT 실행 여부 (기본 false)
    
    Response JSON:
        success: bool
        file_path: str      - 저장된 파일 경로
        transcript: str     - STT 결과 (run_stt=true일 때)
    """
    if "video" not in request.files:
        return jsonify({"success": False, "error": "영상 파일이 없습니다"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"success": False, "error": "파일을 선택해주세요"}), 400

    # 타임라인 에디터는 영상/이미지를 모두 이 엔드포인트로 업로드하므로 둘 다 허용
    if not (allowed_file(file.filename, "video") or allowed_file(file.filename, "image")):
        return jsonify({
            "success": False,
            "error": "지원하지 않는 파일 형식입니다 (영상: mp4/mov/avi/mkv/webm, 이미지: jpg/jpeg/png/gif/webp)",
        }), 400

    try:
        file_path = save_upload(file)
        response = {"success": True, "file_path": file_path, "transcript": ""}

        # 휴대폰 원본 사진처럼 지나치게 큰 이미지는 줄여서 저장 — 영상 합성 시
        # 메모리 사용량을 낮춰 메모리가 작은 서버에서 다운되는 것을 방지
        if allowed_file(file.filename, "image"):
            from core.image_writer import downscale_image_if_needed
            downscale_image_if_needed(file_path)

        # STT 실행 요청이 있으면 Whisper로 음성 추출
        run_stt = request.form.get("run_stt", "false").lower() == "true"
        if run_stt:
            from core.video_processor import VideoProcessor
            vp = VideoProcessor()
            stt_result = vp.extract_audio_transcript(file_path)
            response["transcript"] = stt_result["text"]

        return jsonify(response)

    except Exception as e:
        print(f"[API /upload-video 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── API: BGM 업로드 (사용자 직접 업로드) ─────────────────────
# static/assets/bgm/ 프리셋 음원 파일이 아직 준비되지 않아, 사용자가 직접
# 보유한 BGM 파일을 업로드해 타임라인 합성에 쓸 수 있도록 하는 경로.

@app.route("/api/upload-bgm", methods=["POST"])
@login_required
def api_upload_bgm():
    if "bgm" not in request.files:
        return jsonify({"success": False, "error": "BGM 파일이 없습니다"}), 400

    file = request.files["bgm"]
    if file.filename == "":
        return jsonify({"success": False, "error": "파일을 선택해주세요"}), 400

    if not allowed_file(file.filename, "audio"):
        return jsonify({"success": False, "error": "지원하지 않는 파일 형식입니다 (mp3, wav, m4a)"}), 400

    try:
        file_path = save_upload(file)
        return jsonify({"success": True, "file_path": file_path})
    except Exception as e:
        print(f"[API /upload-bgm 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── API: 영상 처리 ───────────────────────────────────────────

@app.route("/api/process-video", methods=["POST"])
@login_required
def api_process_video():
    """
    영상 합성 처리 (자막 + BGM + 리사이즈)
    
    Request JSON:
        video_path: str     - 업로드된 영상 경로
        subtitle_text: str  - 자막 텍스트
        platform: str       - 플랫폼
        bgm_path: str       - BGM 파일 경로 (선택)
        subtitle_options: dict - 자막 옵션 (선택)
    """
    try:
        data = request.get_json()
        video_path = data.get("video_path")
        subtitle_text = data.get("subtitle_text", "")
        platform = data.get("platform", "instagram")
        bgm_path = data.get("bgm_path")
        subtitle_options = data.get("subtitle_options", {})

        if not video_path or not Path(video_path).exists():
            return jsonify({"success": False, "error": "영상 파일을 찾을 수 없습니다"}), 400

        from core.video_processor import VideoProcessor
        vp = VideoProcessor()
        result = vp.process_video(
            video_path=video_path,
            subtitle_text=subtitle_text,
            platform=platform,
            bgm_path=bgm_path,
            subtitle_options=subtitle_options,
        )

        return jsonify({"success": result.get("success", False), "data": result})

    except Exception as e:
        print(f"[API /process-video 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── API: 미디어 에디터 신규 기능 (프레임분석 / 스타일클론 / 이미지생성 / 타임라인합성) ──

@app.route("/api/analyze-style", methods=["POST"])
@login_required
def api_analyze_style():
    """
    영상 진행 중간중간 프레임 몇 장만 캡처해 Gemini Vision으로 분석,
    자막 위치/폰트크기/색상을 추천받는다 (영상 전체를 분석하지 않아 비용 절감).
    """
    try:
        data = request.get_json()
        video_path = data.get("video_path")

        if not video_path or not Path(video_path).exists():
            return jsonify({"success": False, "error": "영상 파일을 찾을 수 없습니다"}), 400

        from core.video_style_analyzer import analyze_style
        result = analyze_style(video_path)

        return jsonify({"success": True, "data": result})

    except Exception as e:
        print(f"[API /analyze-style 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/analyze-photo", methods=["POST"])
@login_required
def api_analyze_photo():
    """
    사진을 Gemini Vision으로 자동 분석해 사진 설명 문장을 반환한다.
    (기존엔 사용자가 '사진 내용 설명'을 직접 입력해야 했는데, 이 API로 자동화 가능)
    """
    try:
        data = request.get_json()
        image_path = data.get("image_path")

        if not image_path or not Path(image_path).exists():
            return jsonify({"success": False, "error": "이미지 파일을 찾을 수 없습니다"}), 400

        from core.ai_writer import analyze_photo
        description = analyze_photo(image_path)

        return jsonify({"success": True, "data": {"description": description}})

    except Exception as e:
        print(f"[API /analyze-photo 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/style-clone", methods=["POST"])
@login_required
def api_style_clone():
    """
    타겟 URL을 입력받아 스타일(폰트/색상/톤)을 추천 — 데모용 더미 매칭(실제 URL 접속 없음)
    """
    try:
        data = request.get_json()
        target_url = data.get("target_url", "")

        from core.style_clone import clone_style_from_url
        result = clone_style_from_url(target_url)

        return jsonify({"success": True, "data": result})

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        print(f"[API /style-clone 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/generate-image", methods=["POST"])
@login_required
def api_generate_image():
    """
    주제 텍스트만으로 이미지 생성 프롬프트를 만들고, 무료 이미지 생성 서비스로 실제 이미지를 생성한다.
    """
    try:
        data = request.get_json()
        topic = data.get("topic", "").strip()
        platform = data.get("platform", "instagram")
        business_type = data.get("business_type", "")
        tone = data.get("tone", "친근한")

        if not topic:
            return jsonify({"success": False, "error": "주제를 입력해주세요"}), 400

        from core.image_writer import generate_image_from_topic
        result = generate_image_from_topic(topic, platform, business_type, tone)

        return jsonify({"success": True, "data": result})

    except Exception as e:
        print(f"[API /generate-image 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/compose-timeline", methods=["POST"])
@login_required
def api_compose_timeline():
    """
    타임라인 에디터에 배치된 클립들(이미지 기본 2초/영상 기본 4초)을 순서대로 이어붙이고
    자막/BGM까지 합성해 최종 영상을 만든다.

    Request JSON:
        clips: [{path, type, duration}, ...]
        platform: str
        subtitle_text: str (선택)
        subtitle_options: dict (선택)
        bgm_path: str (선택)
    """
    try:
        data = request.get_json()
        clips = data.get("clips", [])
        platform = data.get("platform", "instagram")
        subtitle_text = data.get("subtitle_text", "")
        subtitle_options = data.get("subtitle_options", {})
        bgm_path = data.get("bgm_path")

        if not clips:
            return jsonify({"success": False, "error": "타임라인에 클립이 없습니다"}), 400

        from core.video_composer import VideoComposer
        composer = VideoComposer()
        output_path = composer.compose_timeline(
            clips=clips,
            platform=platform,
            subtitle_text=subtitle_text,
            subtitle_options=subtitle_options,
            bgm_path=bgm_path,
        )

        return jsonify({"success": True, "data": {"output_path": output_path}})

    except Exception as e:
        print(f"[API /compose-timeline 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/connection-status", methods=["GET"])
@login_required
def api_connection_status():
    """네이버/틱톡/메타(인스타/페북)/X(트위터) OAuth 연결 상태 조회 — 좌측 설정 패널 표시용"""
    platforms = ["naver_blog", "tiktok", "instagram", "facebook", "x_twitter"]
    status = {p: get_oauth_token(session["user_id"], p) is not None for p in platforms}
    return jsonify({"success": True, "data": status})


@app.route("/api/download/<filename>", methods=["GET"])
def api_download(filename):
    """
    완성된 영상 파일 다운로드
    """
    try:
        return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)
    except Exception as e:
        return jsonify({"success": False, "error": f"파일을 찾을 수 없습니다: {e}"}), 404


# ─── API: 예약 발행 ───────────────────────────────────────────

@app.route("/api/schedule", methods=["POST"])
@login_required
def api_schedule():
    """
    예약 발행 등록
    
    Request JSON:
        platform: str
        title: str
        content: str
        caption: str
        hashtags: list[str]
        media_path: str (선택)
        scheduled_at: str (ISO format: 'YYYY-MM-DD HH:MM')
    """
    try:
        data = request.get_json()

        platform = data.get("platform")
        content = data.get("content", "")
        scheduled_at_str = data.get("scheduled_at")

        if not all([platform, content, scheduled_at_str]):
            return jsonify({"success": False, "error": "플랫폼, 원고, 예약 시간은 필수입니다"}), 400

        hashtags_list = data.get("hashtags", [])
        hashtags_str = " ".join(hashtags_list) if isinstance(hashtags_list, list) else hashtags_list

        timeline = data.get("timeline")
        timeline_json = json.dumps(timeline, ensure_ascii=False) if timeline else None

        post_id = create_scheduled_post(
            user_id=session["user_id"],
            platform=platform,
            title=data.get("title", ""),
            content=content,
            caption=data.get("caption", ""),
            hashtags=hashtags_str,
            scheduled_at=scheduled_at_str,
            media_path=data.get("media_path"),
            timeline_data=timeline_json,
        )

        return jsonify({"success": True, "post_id": post_id})

    except Exception as e:
        print(f"[API /schedule 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/scheduled-posts", methods=["GET"])
@login_required
def api_scheduled_posts():
    """예약 발행 목록 조회 (본인 것만)"""
    posts = get_all_scheduled_posts(session["user_id"])
    return jsonify({"success": True, "data": posts})


@app.route("/api/schedule/<int:post_id>", methods=["DELETE"])
@login_required
def api_delete_schedule(post_id):
    """예약 발행 취소(삭제) — 본인 소유 게시물만 삭제 가능"""
    try:
        success = delete_scheduled_post(post_id, session["user_id"])
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "해당 예약 게시물이 존재하지 않습니다."}), 404
    except Exception as e:
        print(f"[API DELETE /schedule 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── API: 즉시 발행 ───────────────────────────────────────────

@app.route("/api/publish", methods=["POST"])
@login_required
def api_publish():
    """
    선택한 플랫폼으로 즉시 발행

    Request JSON:
        platform: str       - 플랫폼 ('naver_blog' | 'x_twitter' | 'tiktok' 등)
        title: str          - 제목
        content: str        - 본문
        caption: str        - 캡션 (선택)
        hashtags: str       - 해시태그 (선택)
        media_path: str     - 미디어 파일 경로 (선택)

    Response JSON:
        success: bool
        data: { url, platform, ... }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "JSON 데이터가 필요합니다"}), 400

        platform = data.get("platform", "")
        content = data.get("content", "")

        if not platform or not content:
            return jsonify({"success": False, "error": "플랫폼과 원고 내용은 필수입니다"}), 400

        hashtags_data = data.get("hashtags", "")
        hashtags_str = " ".join(hashtags_data) if isinstance(hashtags_data, list) else hashtags_data

        from core.publisher import Publisher
        publisher = Publisher()

        post_data = {
            "id": f"instant_{int(time.time())}",
            "user_id": session["user_id"],
            "platform": platform,
            "title": data.get("title", ""),
            "content": content,
            "caption": data.get("caption", ""),
            "hashtags": hashtags_str,
            "media_path": data.get("media_path", ""),
        }

        result = publisher.publish_post(post_data)

        return jsonify({
            "success": result.get("success", False),
            "data": result,
        })

    except Exception as e:
        print(f"[API /publish 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── OAuth 로그인 연동 (네이버 블로그 / 틱톡) ───────────────────
# writePost.json / video/init 같은 "글쓰기" 계열 API는 앱 자격증명(Client ID/Secret,
# Client Key/Secret)만으로는 호출할 수 없고, 사용자가 로그인해서 동의한 뒤 발급되는
# access_token(Bearer)이 있어야 한다. 아래 4개 라우트가 그 최초 1회 로그인을 처리한다.

@app.route("/auth/naver/login")
@login_required
def auth_naver_login():
    from core.oauth_naver import get_authorize_url
    state = secrets.token_urlsafe(16)
    session["naver_oauth_state"] = state
    return redirect(get_authorize_url(state))


@app.route("/auth/naver/callback")
@login_required
def auth_naver_callback():
    from core.oauth_naver import exchange_code_for_token
    code = request.args.get("code")
    state = request.args.get("state")

    if not code or not state or state != session.get("naver_oauth_state"):
        return "네이버 로그인 인증에 실패했습니다 (state 불일치 또는 code 없음).", 400

    try:
        token_data = exchange_code_for_token(code, state)
        expires_at = None
        if token_data.get("expires_in"):
            expires_at = (datetime.now() + timedelta(seconds=int(token_data["expires_in"]))).strftime("%Y-%m-%d %H:%M:%S")

        save_oauth_token(
            session["user_id"],
            "naver_blog",
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=expires_at,
        )
        return "✅ 네이버 블로그 연결 완료! 이 창을 닫고 발행을 진행하세요."
    except Exception as e:
        print(f"[Naver OAuth Callback 오류] {e}")
        return f"네이버 로그인 처리 중 오류가 발생했습니다: {e}", 500


@app.route("/auth/tiktok/login")
@login_required
def auth_tiktok_login():
    from core.oauth_tiktok import get_authorize_url, generate_pkce_pair
    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = generate_pkce_pair()
    session["tiktok_oauth_state"] = state
    session["tiktok_code_verifier"] = code_verifier
    return redirect(get_authorize_url(state, code_challenge))


@app.route("/auth/tiktok/callback")
@login_required
def auth_tiktok_callback():
    from core.oauth_tiktok import exchange_code_for_token
    code = request.args.get("code")
    state = request.args.get("state")
    code_verifier = session.get("tiktok_code_verifier")

    if not code or not state or state != session.get("tiktok_oauth_state") or not code_verifier:
        return "틱톡 로그인 인증에 실패했습니다 (state 불일치 또는 code 없음).", 400

    try:
        token_data = exchange_code_for_token(code, code_verifier)
        expires_at = None
        if token_data.get("expires_in"):
            expires_at = (datetime.now() + timedelta(seconds=int(token_data["expires_in"]))).strftime("%Y-%m-%d %H:%M:%S")

        save_oauth_token(
            session["user_id"],
            "tiktok",
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=expires_at,
        )
        return "✅ 틱톡 연결 완료! 이 창을 닫고 발행을 진행하세요."
    except Exception as e:
        print(f"[TikTok OAuth Callback 오류] {e}")
        return f"틱톡 로그인 처리 중 오류가 발생했습니다: {e}", 500


@app.route("/auth/meta/login")
@login_required
def auth_meta_login():
    from core.oauth_meta import get_authorize_url
    state = secrets.token_urlsafe(16)
    session["meta_oauth_state"] = state
    return redirect(get_authorize_url(state))


@app.route("/auth/meta/callback")
@login_required
def auth_meta_callback():
    from core.oauth_meta import exchange_code_for_token, get_long_lived_token, get_page_and_ig_account
    code = request.args.get("code")
    state = request.args.get("state")

    if not code or not state or state != session.get("meta_oauth_state"):
        return "메타(페이스북) 로그인 인증에 실패했습니다 (state 불일치 또는 code 없음).", 400

    try:
        short_token = exchange_code_for_token(code)
        long_token = get_long_lived_token(short_token)
        page_info = get_page_and_ig_account(long_token)
        user_id = session["user_id"]

        page_extra = json.dumps({"page_id": page_info["page_id"], "page_name": page_info["page_name"]})
        save_oauth_token(user_id, "facebook", access_token=page_info["page_access_token"], extra_data=page_extra)

        if page_info.get("ig_user_id"):
            ig_extra = json.dumps({"ig_user_id": page_info["ig_user_id"], "page_id": page_info["page_id"]})
            save_oauth_token(user_id, "instagram", access_token=page_info["page_access_token"], extra_data=ig_extra)
            return f"✅ 페이스북 '{page_info['page_name']}' 페이지 + 연결된 인스타그램 계정 연결 완료! 이 창을 닫고 발행을 진행하세요."

        return f"✅ 페이스북 '{page_info['page_name']}' 페이지 연결 완료! (연결된 인스타그램 비즈니스 계정은 찾지 못했습니다.) 이 창을 닫고 발행을 진행하세요."
    except Exception as e:
        print(f"[Meta OAuth Callback 오류] {e}")
        return f"메타 로그인 처리 중 오류가 발생했습니다: {e}", 500


@app.route("/auth/x/login")
@login_required
def auth_x_login():
    from core.oauth_x import get_authorization_url_and_token
    from config import PUBLIC_BASE_URL
    callback_url = f"{PUBLIC_BASE_URL}/auth/x/callback"
    try:
        auth_url, request_token = get_authorization_url_and_token(callback_url)
        session["x_request_token"] = request_token
        return redirect(auth_url)
    except Exception as e:
        print(f"[X OAuth Login 오류] {e}")
        return f"X(트위터) 로그인 시작에 실패했습니다: {e}", 500


@app.route("/auth/x/callback")
@login_required
def auth_x_callback():
    from core.oauth_x import exchange_verifier_for_token
    verifier = request.args.get("oauth_verifier")
    request_token = session.get("x_request_token")

    if not verifier or not request_token:
        return "X(트위터) 로그인 인증에 실패했습니다 (verifier 또는 request_token 없음).", 400

    try:
        access_token, access_token_secret = exchange_verifier_for_token(request_token, verifier)
        save_oauth_token(
            session["user_id"],
            "x_twitter",
            access_token=access_token,
            extra_data=json.dumps({"access_token_secret": access_token_secret}),
        )
        return "✅ X(트위터) 계정 연결 완료! 이 창을 닫고 발행을 진행하세요."
    except Exception as e:
        print(f"[X OAuth Callback 오류] {e}")
        return f"X(트위터) 로그인 처리 중 오류가 발생했습니다: {e}", 500


# ─── 정적 파일 서빙 ──────────────────────────────────────────

@app.route("/outputs/<path:filename>")
def serve_output(filename):
    """처리된 영상 파일 다운로드/스트리밍"""
    return send_from_directory(str(OUTPUT_DIR), filename)


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    """업로드된 원본 이미지/영상 서빙 (인스타그램 등 공개 URL이 필요한 발행에 사용)"""
    return send_from_directory(str(UPLOAD_DIR), filename)


# ─── 앱 실행 ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 소상공인 SNS AI 자동 발행 시스템")
    print("   http://localhost:5000")
    print("=" * 50)
    app.run(debug=FLASK_DEBUG, host="0.0.0.0", port=5000)
