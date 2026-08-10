# Project Context Handoff for Claude Code

## 1. 프로젝트 개요 (Project Overview)
- **프로젝트명**: 소상공인 SNS AI 자동 발행 시스템 (가칭)
- **목적**: 소상공인들이 텍스트 주제만 입력하면 AI가 SNS 플랫폼(네이버 블로그, 트위터, 틱톡, 인스타그램 등)에 맞는 원고를 작성하고, 즉시 발행 및 예약 발행을 할 수 있게 해주는 서비스.
- **기술 스택**: Python (Flask), Vanilla JS, HTML/CSS, Google Gemini API, 각종 SNS API.

## 2. 지금까지 완료된 작업 (Work Completed)

### [프론트엔드 (UI/UX)]
- `templates/index.html` 기반으로 반응형 웹 디자인 구현.
- 당근마켓(Danggeun) 플랫폼 지원 중단 결정에 따라 UI 및 로직에서 당근마켓 관련 코드 완벽히 제거.
- **[즉시 발행]** 버튼 클릭 시 가짜(Mock) 동작이 아닌 실제 백엔드 API(`/api/publish`)를 호출하도록 연동 완료.

### [백엔드 (API & 엔진)]
- **AI 원고 생성 엔진 (`core/ai_writer.py`)**:
  - 기존 유료 OpenAI(GPT)에서 **무료 Google Gemini API**로 완벽하게 교체 완료.
  - 최신 `google-genai` 라이브러리 사용 및 `gemini-flash-latest` 모델 적용.
  - 한국어 텍스트 길이에 의한 JSON 잘림(Truncation) 방지를 위해 `max_output_tokens`를 8192로 대폭 상향.
  - 마크다운 백틱(```json)이 섞여 들어와도 안전하게 파싱하도록 정규식(Regex) 파싱 로직 적용.
- **SNS 자동 발행 엔진 (`core/publisher.py`)**:
  - 기존 가상 2초 대기(Mock) 코드에서 **진짜 SNS API 호출 코드로 전면 개편**.
  - **네이버 블로그**: 네이버 OpenAPI 연동 완료 (REST API).
  - **X (트위터)**: OAuth 1.0a 기반 `tweepy` 라이브러리로 텍스트+해시태그 트윗 자동 발행 구현.
  - **틱톡 (TikTok)**: Content Posting API 연동 완료 (단, 틱톡은 영상이 필수이므로 영상 파일 경로가 없을 경우 안내 메시지 반환 처리).
  - *참고*: 인스타그램, 페이스북, 스레드는 현재 Meta 개발자 센터 앱 리뷰(인증) 대기 중이므로 임시로 차단(Stub) 상태.
- **환경 설정 (`config.py` & `.env`)**:
  - `.env`에 네이버, 트위터, 틱톡, 제미나이 API 키 셋업 완료.
  - `config.py`의 `FREE` 플랜 하루 제한 횟수를 3회에서 9999회(무제한)로 변경하여 테스트 편의성 확보.

## 3. 코드 구조 (Directory Structure)
- `app.py`: Flask 메인 서버 (라우팅, API 엔드포인트 `/api/publish`, `/api/generate` 등 포함).
- `config.py`: 전역 설정 및 환경 변수 매핑.
- `core/`
  - `ai_writer.py`: Gemini AI를 이용한 원고 자동 작성 로직.
  - `publisher.py`: 각 플랫폼별 실제 API 호출 및 발행 로직.
  - `scheduler.py`: 예약 발행을 위한 APScheduler 백그라운드 작업 로직.
  - `db.py`: SQLite 기반 게시물 DB 관리 로직.

## 4. 바로 다음으로 진행해야 할 작업 (Next Steps)
현재 기초적인 AI 원고 생성 및 즉시 발행이 성공적으로 테스트되었습니다. 다음 단계로 고려할 만한 작업들은 다음과 같습니다:
1. **틱톡 자동화 고도화**: 틱톡은 영상이 필수입니다. 텍스트만 있을 때 배경 음악이나 템플릿 비디오를 자동 합성해서 업로드하게 할지 논의 및 구현 필요.
2. **Meta Graph API 연동**: 인스타그램 및 페이스북 권한 승인이 완료되면 `core/publisher.py`의 더미 코드를 실제 Meta API 코드로 대체.
3. **예약 발행 연동**: 현재 즉시 발행만 테스트되었으므로, 프론트엔드의 캘린더/시간 설정과 백엔드의 `scheduler.py` 간 연동 강화.

---
**To Claude Code**: 위 맥락(Context)을 바탕으로 사용자의 다음 지시사항을 중복 없이, 충돌 없이 이어서 처리해주세요. 사용자는 현재 토큰 부족으로 이곳으로 넘어왔으며 작업은 100% 끊김 없이 이어져야 합니다.
