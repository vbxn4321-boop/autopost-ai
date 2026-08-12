# AutoPost AI - Project Handoff & Context Document (최신 업데이트)

## 1. Project Overview
- **Project Name:** AutoPost AI (소상공인 SNS AI 자동 발행 시스템)
- **Goal:** A fully automated social media posting web application that generates videos/images using AI and posts them simultaneously to multiple platforms (Instagram, TikTok, Naver Blog, X/Twitter, Facebook, Threads).
- **Tech Stack:** Python (Flask), SQLite, HTML/Vanilla CSS/Vanilla JS.
- **Hosting:** Render (Web Service) `https://autopost-ai-bcwk.onrender.com`.

## 2. Chronological Development History & Today's Major Progress
1. **Initial Setup & Architecture:**
   - Flask backend & SQLite database (`posts.db`).
   - Modular structure (`app.py`, `config.py`, `core/` directory).
2. **UI/UX 전면 개편 & 미디어 에디터 신규 기능 (커밋: `736c1fc`):**
   - **레이아웃 구조화:** 상단 고정 액션바(다운로드/예약/발행) + 좌측 사이드바(환경설정) + 중앙 미디어 에디터 + 하단 원고 관리 구조로 재구성.
   - **신규 기능 4종 추가:**
     1. 프레임 캡처 기반 저비용 영상 스타일 분석
     2. 스타일 클론 (더미)
     3. 주제 -> 이미지 자동생성 (Pollinations.ai 무료 API 연동)
     4. 타임라인 에디터 (이미지 2초/영상 4초 기본 배치, BGM 합성)
   - **버그 수정:** 이미지 업로드 거부 버그, 한글 콘솔 크래시, Pillow 호환성 크래시 해결.
3. **배포 오류 사전 방지 (커밋: `5a0d8f3`):**
   - `openai-whisper` 최신 `setuptools` 빌드 실패 문제 해결 (Render 배포 시 빌드 실패 사전 차단).
4. **보안 & 주요 기능 5종 강화 (커밋: `a6d08b9`):**
   - `FLASK_DEBUG` 위험한 기본값 수정, 사용 않는 `.env` 키 정리.
   - 워터마크 기능 실제 구현 완료.
   - 예약 발행 실패 시 자동 재시도 로직 추가 (3회 / 5분 간격).
   - Gemini Vision 사진 자동 분석 기능 추가.
5. **Git 보안 조치:**
   - `data/posts.db` 및 캐시 파일들 Git 추적 해제 완료 (`git rm --cached`).

## 3. Codebase Structure
- `app.py`: Main Flask application, routing, API endpoints.
- `config.py`: Global configurations, environment variables, platform settings.
- `core/`: 
  - `publisher.py`: SNS API publishing handlers.
  - `ai_writer.py`: AI script generation.
  - `video_composer.py`, `video_processor.py`: Video rendering and processing.
  - `scheduler.py`: Background job scheduling.
- `templates/index.html`, `static/`: Modernized UI assets.
- `handoff_to_claude.md`: This context file.

## 4. Current Status & Next Steps for New Sessions
- **Status:** All core code cleanup, bug fixes, UI modernization, and security checks are completed.
- **GitHub Sync:** Changes are committed to local Git repository.
- **Next Session Instruction:** When starting a new session, run:
  `"handoff_to_claude.md 읽고 이전 작업 파악해 줘. 그리고 이어서 다음 작업 진행하자."`
