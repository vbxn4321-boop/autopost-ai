"""
app.py — Flask 메인 애플리케이션
소상공인 올인원 SNS 원고 & 동영상 AI 자동 발행 시스템
"""

import os
import json
import uuid
import time
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect
from werkzeug.utils import secure_filename

from config import (
    FLASK_SECRET_KEY, FLASK_DEBUG,
    UPLOAD_DIR, OUTPUT_DIR,
    ALLOWED_VIDEO_EXTENSIONS, ALLOWED_IMAGE_EXTENSIONS,
    MAX_UPLOAD_SIZE_MB, PLATFORM_SETTINGS, PLANS,
)
from core.db import init_db, create_scheduled_post, get_all_scheduled_posts, delete_scheduled_post, save_oauth_token
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
    return ext in ALLOWED_IMAGE_EXTENSIONS


def save_upload(file) -> str:
    """업로드 파일 저장 및 경로 반환"""
    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    save_path = UPLOAD_DIR / unique_name
    file.save(str(save_path))
    return str(save_path)


# ─── 라우트 ──────────────────────────────────────────────────

@app.route("/")
def index():
    """메인 UI 페이지"""
    return render_template("index.html", platforms=PLATFORM_SETTINGS)


# ─── API: 원고 생성 ──────────────────────────────────────────

@app.route("/api/generate", methods=["POST"])
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

        result = generate_content(
            topic=topic,
            platform=platform,
            business_type=business_type,
            location=location,
            keywords=keywords,
            tone=tone,
        )

        # 횟수 증가
        session["usage_count"] = usage_count + 1

        return jsonify({"success": True, "data": result})

    except Exception as e:
        print(f"[API /generate 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── API: 틱톡 도메인 인증 라우트 ───────────────────────────────────

@app.route("/tiktoks7SekCpH6YGzzbvFLHt2U8wbRZVqkOCv.txt", methods=["GET"])
def tiktok_verification():
    """틱톡 Web 플랫폼 도메인 인증(Signature file) 전용 라우트"""
    return "tiktok-developers-site-verification=s7SekCpH6YGzzbvFLHt2U8wbRZVqkOCv"

# ─── API: 영상 업로드 ─────────────────────────────────────────

@app.route("/api/upload-video", methods=["POST"])
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

    if not allowed_file(file.filename, "video"):
        return jsonify({"success": False, "error": "지원하지 않는 파일 형식입니다 (mp4, mov, avi, mkv, webm)"}), 400

    try:
        file_path = save_upload(file)
        response = {"success": True, "file_path": file_path, "transcript": ""}

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


# ─── API: 영상 처리 ───────────────────────────────────────────

@app.route("/api/process-video", methods=["POST"])
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

        post_id = create_scheduled_post(
            platform=platform,
            title=data.get("title", ""),
            content=content,
            caption=data.get("caption", ""),
            hashtags=hashtags_str,
            scheduled_at=scheduled_at_str,
            media_path=data.get("media_path"),
        )

        return jsonify({"success": True, "post_id": post_id})

    except Exception as e:
        print(f"[API /schedule 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/scheduled-posts", methods=["GET"])
def api_scheduled_posts():
    """예약 발행 목록 조회"""
    posts = get_all_scheduled_posts()
    return jsonify({"success": True, "data": posts})


@app.route("/api/schedule/<int:post_id>", methods=["DELETE"])
def api_delete_schedule(post_id):
    """예약 발행 취소(삭제)"""
    try:
        success = delete_scheduled_post(post_id)
        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "해당 예약 게시물이 존재하지 않습니다."}), 404
    except Exception as e:
        print(f"[API DELETE /schedule 오류] {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ─── API: 즉시 발행 ───────────────────────────────────────────

@app.route("/api/publish", methods=["POST"])
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
def auth_naver_login():
    from core.oauth_naver import get_authorize_url
    state = secrets.token_urlsafe(16)
    session["naver_oauth_state"] = state
    return redirect(get_authorize_url(state))


@app.route("/auth/naver/callback")
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
def auth_tiktok_login():
    from core.oauth_tiktok import get_authorize_url, generate_pkce_pair
    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = generate_pkce_pair()
    session["tiktok_oauth_state"] = state
    session["tiktok_code_verifier"] = code_verifier
    return redirect(get_authorize_url(state, code_challenge))


@app.route("/auth/tiktok/callback")
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
            "tiktok",
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            expires_at=expires_at,
        )
        return "✅ 틱톡 연결 완료! 이 창을 닫고 발행을 진행하세요."
    except Exception as e:
        print(f"[TikTok OAuth Callback 오류] {e}")
        return f"틱톡 로그인 처리 중 오류가 발생했습니다: {e}", 500


# ─── 정적 파일 서빙 ──────────────────────────────────────────

@app.route("/outputs/<path:filename>")
def serve_output(filename):
    """처리된 영상 파일 다운로드/스트리밍"""
    return send_from_directory(str(OUTPUT_DIR), filename)


# ─── 앱 실행 ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 소상공인 SNS AI 자동 발행 시스템")
    print("   http://localhost:5000")
    print("=" * 50)
    app.run(debug=FLASK_DEBUG, host="0.0.0.0", port=5000)
