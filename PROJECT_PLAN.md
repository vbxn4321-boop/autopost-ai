# 📋 AutoPost AI (오토포스트 AI) — 소상공인 7개 SNS 통합 자동 발행 솔루션
## PROJECT_PLAN.md — 대표님 제출용 구체화 기획서 (v2.0)

> **작성일**: 2026-08-07 | **버전**: v2.0 (대표님 피드백 반영)
> **개발 환경**: 로컬(Local) 우선, 서버 파이썬 처리, 최소 비용 구조

---

## 1. 서비스 개요 (Service Overview)

### 1-1. 한 줄 정의
> 소상공인이 **사진·영상 업로드 + 주제 한 줄 입력**만으로,  
> **인스타그램·틱톡·당근마켓·블로그·페이스북·X(트위터)·스레드** 등 7개 SNS에 최적화된 원고와 영상을 자동 생성하고  
> **MP4 파일로 다운로드 or 예약 발행**까지 원스톱으로 처리하는 올인원 AI 마케팅 도구

### 1-2. 핵심 철학 — "비용 0원 영상 처리"
> ❌ 고비용 AI 영상 생성 API (Runway, Pika, Sora 등) 미사용  
> ✅ 사용자가 올린 미디어 + 파이썬(FFmpeg) 서버 결합 → **영상 처리 비용 = $0/월**  
> ✅ 텍스트 생성만 최저가 LLM(Gemini 1.5 Flash / GPT-4o-mini) 활용

### 1-3. 해결하는 문제

| 현재 소상공인의 고통 | 우리 시스템이 해결하는 방식 | 절감 효과 |
|---|---|---|
| 매일 SNS 올리기 힘들다 | AI 원고 자동 생성 + 예약 발행 | 시간 90% 절약 |
| 영상 편집 툴을 모른다 | 캡컷 스타일 웹 에디터 + 자동 결합 | 편집 비용 0원 |
| 플랫폼마다 규칙이 다르다 | 플랫폼별 SEO 캡션 자동 추출 | 전략 수립 불필요 |
| 마케팅 예산이 없다 | 로컬 FFmpeg 처리, LLM 최저가 | 월 $1~5 수준 |

### 1-4. 타겟 고객

- **1차 타겟**: 직원 1~5명 소상공인 (카페, 식당, 미용실, 헬스장, 베이커리 등)
- **2차 타겟**: SNS 마케팅 대행 1인 마케터 / 소규모 에이전시
- **페르소나**: "사진은 있는데 올릴 시간도 없고 편집도 못하는 사장님"

---

## 2. 핵심 사용 흐름 — 3단계 UX

```
┌─────────────────────────────────────────────────────────────┐
│                    3단계 사용 흐름                            │
├──────────────────┬──────────────────┬───────────────────────┤
│   STEP 1         │   STEP 2         │   STEP 3              │
│   업로드 & 입력   │   편집 & 커스텀  │   완성 & 발행          │
│                  │                  │                       │
│  📸 사진/영상 업로드│  ✏️ AI 원고 수정  │  📥 MP4 다운로드       │
│  📝 주제 한 줄 입력│  🎬 자막 위치·폰트│  📅 예약 발행          │
│  🏢 플랫폼 선택   │  🎵 BGM 선택     │  📋 캡션 복사          │
│                  │  📐 해상도 설정   │  🚀 즉시 발행          │
└──────────────────┴──────────────────┴───────────────────────┘
```

---

## 3. 주요 기능 명세서 (Feature Specification)

### 기능 A — 미디어 업로드 & AI 원고 생성 엔진

#### A-1. 입력 방식 (3가지)

**[방법 1] 주제 텍스트 입력 (무료 플랜)**
```
입력: "오늘 신메뉴 아메리카노 출시 / 2천원 할인 이벤트"
출력: 플랫폼별 원고 + 해시태그 + 영상 자막 텍스트
```

**[방법 2] 사진 업로드 + 주제 입력 (무료/유료 공통)**
```
[무료] 사진 업로드 + 주제 텍스트 직접 입력
       → Vision API 미사용, 비용 0원
       → 사용자 입력 텍스트 기반 원고 생성

[유료 구독] 사진 업로드만
       → Gemini Vision (gemini-1.5-flash 멀티모달) 자동 분석
       → 사진 내용 자동 인식 → 원고 자동 생성
       → 구독제 차별화 핵심 기능
```

**[방법 3] 영상 파일 업로드 (무료/유료 공통)**
```
영상 업로드 → FFmpeg 메타데이터 추출
           → Whisper 로컬 STT (음성→텍스트, 비용 0원)
           → 텍스트 기반 AI 원고 생성
           → 자막 자동 생성 제안
```

> **핵심 비용 설계**: Vision API는 유료 구독 기능으로만 제공하여  
> 무료 플랜 비용을 0에 수렴하고, 구독 전환 유인을 강화합니다.

#### A-2. LLM 비용 최적화 구조

| 용도 | 모델 | 입력 1K 토큰 비용 | 월 예상 비용 |
|---|---|---|---|
| 원고 생성 (기본) | Gemini 1.5 Flash | $0.000075 | **~$0.1~1** |
| 원고 생성 (대안) | GPT-4o-mini | $0.000150 | **~$0.3~2** |
| Vision 분석 (유료전용) | Gemini 1.5 Flash (멀티모달) | $0.000075 + 이미지 | 구독료로 충당 |
| 음성→텍스트 | Whisper 로컬 | $0 | $0 |

```python
# core/llm_client.py — LLM 모델 우선순위 선택

def get_llm_client(prefer_free=True):
    """
    Gemini 1.5 Flash 우선 → GPT-4o-mini 폴백
    API 키 상황에 따라 자동 선택
    """
    if GEMINI_API_KEY:
        return GeminiClient(model="gemini-1.5-flash")  # 최저가
    elif OPENAI_API_KEY:
        return OpenAIClient(model="gpt-4o-mini")        # 차선가
    else:
        raise ValueError("LLM API 키가 설정되지 않았습니다")
```

---

### 기능 B — 캡컷 스타일 웹 에디터

> **핵심 UX 목표**: "영상 편집 앱 설치 없이, 브라우저에서 캡컷처럼"

#### B-1. 에디터 레이아웃

```
┌─────────────────────────────────────────────────────────────┐
│  [타임라인 바]  ──────────────────────────────── 00:15 / 00:30│
├──────────────────────────┬──────────────────────────────────┤
│                          │  📝 원고 에디터                    │
│   📹 영상 미리보기         │  ┌────────────────────────────┐  │
│   (실시간 자막 오버레이)    │  │ 생성된 원고가 여기에         │  │
│                          │  │ 자동으로 삽입됩니다.          │  │
│   [자막 드래그 가능]       │  │ 자유롭게 수정하세요          │  │
│                          │  └────────────────────────────┘  │
│                          │  [재생성] [원문복구] [복사]        │
├──────────────────────────┴──────────────────────────────────┤
│  🎨 자막 설정    🎵 BGM    📐 해상도    🏷️ 해시태그           │
│                                                             │
│  폰트: [나눔고딕▼]  크기: [40px]  색상: [■흰색]  위치: [하단▼]│
│  외곽선: [■검정] 두께: [2px]  배경박스: [□ 사용]             │
└─────────────────────────────────────────────────────────────┘
```

#### B-2. 자막 커스텀 기능 (캡컷 스타일)

| 설정 항목 | 옵션 | 구현 방법 |
|---|---|---|
| 폰트 | 나눔고딕, 나눔바른, 고딕체, 손글씨체 등 | 서버에 TTF 폰트 번들 |
| 크기 | 슬라이더 (20px ~ 80px) | MoviePy fontsize 파라미터 |
| 색상 | 컬러 피커 (RGB/HEX) | MoviePy color 파라미터 |
| 위치 | 상단/중단/하단 + 드래그 조정 | MoviePy position 파라미터 |
| 외곽선 | 색상 + 두께 슬라이더 | MoviePy stroke_color/width |
| 배경박스 | 반투명 박스 on/off | MoviePy bg_color 파라미터 |
| 타이밍 | 자막 시작/끝 시간 조정 | 세그먼트별 타이밍 설정 |

#### B-3. 실시간 미리보기 전략

```
[클라이언트 미리보기 (즉시)]
Canvas API로 영상 위에 자막 CSS 오버레이 표시
→ 설정 변경 시 실시간 반영 (서버 요청 없음)

[서버 최종 렌더링]
"영상 완성하기" 버튼 클릭 시에만 FFmpeg 렌더링 실행
→ 처리 시간 30초~3분 (백그라운드)
→ 완료 후 다운로드 링크 제공
```

---

### 기능 C — 파이썬(FFmpeg) 기반 영상 결합 파이프라인

> **핵심 원칙**: 영상 처리 비용 = $0. 모든 결합은 서버 내부 Python에서 처리

#### C-1. 핵심 파이프라인 (사용자 미디어 → MP4 출력)

```
┌─────────────────────────────────────────────────────────────┐
│               영상 결합 파이프라인                             │
│                                                             │
│  [사용자 입력]                                               │
│  📸 사진 파일(들) + 📹 영상 파일                              │
│  📝 AI 생성 자막 텍스트                                       │
│  🎵 선택한 BGM                                               │
│  ⚙️ 에디터 설정 (폰트/크기/위치/색상)                          │
│                         ↓                                   │
│  [STEP 1] FFmpeg — 미디어 전처리                              │
│  - 사진 → 이미지 시퀀스 (각 3~5초 자동 슬라이드)              │
│  - 영상 → 포맷 정규화 (H.264, AAC)                           │
│  - 플랫폼별 해상도 변환 (9:16 / 1:1)                         │
│                         ↓                                   │
│  [STEP 2] MoviePy — 자막 오버레이                            │
│  - Whisper STT 결과 → 세그먼트별 타이밍 자막                  │
│  - 에디터 설정값 그대로 반영 (폰트/크기/위치/색상/외곽선)       │
│                         ↓                                   │
│  [STEP 3] FFmpeg — BGM 믹싱 & 최종 인코딩                    │
│  - 원본 오디오 + BGM 볼륨 믹싱                               │
│  - MP4 (H.264 + AAC) 최종 출력                              │
│  - 파일 크기 최적화 (50MB 이하)                               │
│                         ↓                                   │
│  [OUTPUT] 완성 MP4 파일 다운로드 링크 제공                     │
└─────────────────────────────────────────────────────────────┘
```

#### C-2. 사진 슬라이드쇼 자동 결합 (주요 신규 기능)

```python
# core/video_composer.py

def compose_from_photos(image_paths: list, subtitle_text: str,
                         bgm_path: str, platform: str,
                         subtitle_config: dict) -> str:
    """
    사진 여러 장 → 슬라이드쇼 영상 자동 결합
    
    - 사진당 표시 시간: 3초 (기본) / 사용자 조정 가능
    - 전환 효과: 페이드인/아웃 (FFmpeg xfade 필터)
    - 자막: 전체 영상에 오버레이 or 슬라이드별 다른 자막
    - BGM: 슬라이드쇼 길이에 맞춰 자동 루프
    """
    clips = []
    for img_path in image_paths:
        clip = ImageClip(img_path, duration=3)
        clip = clip.resize(PLATFORM_RESOLUTIONS[platform])
        clips.append(clip)
    
    # 페이드 전환으로 연결
    final = concatenate_videoclips(clips, method="compose")
    
    # 자막 오버레이
    final = add_subtitle(final, subtitle_text, subtitle_config)
    
    # BGM 추가
    if bgm_path:
        final = mix_bgm(final, bgm_path)
    
    output_path = OUTPUT_DIR / f"slideshow_{uuid4().hex}.mp4"
    final.write_videofile(str(output_path), codec="libx264")
    return str(output_path)
```

#### C-3. 플랫폼별 해상도 & 스펙

| 플랫폼 | 해상도 | 비율 | 권장 길이 | 최대 파일 크기 |
|---|---|---|---|---|
| 인스타그램 릴스 | 1080 × 1920 | 9:16 | 15~90초 | 100MB |
| 틱톡 | 1080 × 1920 | 9:16 | 15~60초 | 50MB |
| 당근마켓 | 1080 × 1080 | 1:1 | 제한없음 | 100MB |
| 네이버 블로그 | 1280 × 720 | 16:9 | 제한없음 | 100MB |

---

### 기능 D — 플랫폼별 SEO 맞춤 캡션 시스템

#### D-1. 지원 플랫폼 및 생성 항목

| 플랫폼 | 생성 항목 | 특징 |
|---|---|---|
| 인스타그램 | 캡션 + 해시태그 30개 | 이모지 3~5개, 줄바꿈 최적화 |
| 틱톡 | 짧은 캡션 + 트렌드 해시태그 | MZ 세대 말투, 훅 첫 문장 |
| 당근마켓 | 제목(20자) + 본문(200~300자) | 이웃 말투, 과장 금지 |
| 블로그(네이버) | 제목 + 소제목3 + 본문(800~1200자) | SEO 키워드, CTA 포함 |
| 페이스북 | 캡션 + 해시태그 3~5개 | 이웃 친화적, CTA 포함 |
| X (트위터) | 280자 이내 캡션 + 해시태그 2~3개 | 위트 있고 임팩트 있는 단문 |
| 스레드 (Threads) | 캐주얼 캡션 (200자 이내) | 일상적 대화체, 질문형 Hook |

#### D-2. 플랫폼별 프롬프트 변수 구조 (경쟁사 장점 흡수)

- **오토케/뤼튼/카피클 장점 통합**: 사용자가 원하는 **톤앤매너**를 직접 선택하고, 결과물에 항상 **후킹(Hook) 첫 문장**과 **CTA(행동유도)**가 자동 삽입되도록 프롬프트 설계.

```python
# core/platform_prompts.py
PROMPT_VARIABLES = {
    "topic":         "게시물 주제 (필수)",
    "business_type": "업종 (카페/식당/미용실 등)",
    "location":      "지역 (강남구/부산 해운대 등)",
    "keywords":      "SEO 핵심 키워드",
    "tone":          "톤앤매너 (친근한, 전문적인, 유머러스한 등)",
    "image_desc":    "사진/영상 내용 설명 (무료: 사용자 입력, 유료: Vision 자동)",
}
```

---

### 기능 E — BGM 시스템

#### E-1. 무료 BGM (기본 제공)

```
static/assets/bgm/
├── upbeat/     ☀️ 활기찬 — 카페, 음식점, 할인 이벤트
├── calm/       🌊 잔잔한 — 뷰티, 인테리어, 브랜딩
└── seasonal/   🌸 계절별 — 이벤트, 시즌 마케팅
```

> 라이선스: Pixabay Music / Free Music Archive (CC0)

#### E-2. 프리미엄 BGM (유료 구독 전용)

- Epidemic Sound API 연동 (구독 시 100만+ 트랙)
- 사용자 BGM 직접 업로드 (MP3 최대 50MB)
- BGM 웨이브폼 시각화 + 구간 선택

---

### 기능 F — 예약 발행 시스템

#### F-1. 아키텍처

```
[사용자: 날짜/시간 선택 → 발행 예약]
        ↓
[SQLite DB: scheduled_posts 저장]
  status: pending / processing / published / failed
        ↓
[APScheduler: 1분 간격 체크]
        ↓
[플랫폼별 발행 처리]
  인스타그램 → Meta Graph API (미디어 + 캡션 + 해시태그)
  블로그     → 네이버 Open API
  당근마켓   → 반자동: 클립보드 복사 + 앱 딥링크 알림
  틱톡       → 수동 안내 (API 정책 제한)
```

#### F-2. DB 스키마

```sql
CREATE TABLE scheduled_posts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    platform      TEXT    NOT NULL,
    title         TEXT,
    content       TEXT    NOT NULL,
    caption       TEXT,
    hashtags      TEXT,
    media_path    TEXT,
    output_video  TEXT,           -- FFmpeg 최종 결합 영상 경로
    bgm_path      TEXT,
    subtitle_config TEXT,         -- JSON: 폰트/크기/위치/색상
    scheduled_at  DATETIME NOT NULL,
    status        TEXT    DEFAULT 'pending',
    error_msg     TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    published_at  DATETIME
);
```

---

## 4. 시스템 아키텍처 (System Architecture)

### 4-1. 전체 아키텍처 다이어그램

```
┌──────────────────────────────────────────────────────────────┐
│                    클라이언트 (브라우저)                        │
│                                                              │
│  [STEP 1] 업로드 & 입력                                       │
│  사진/영상 드래그앤드롭 → 주제 텍스트 → 플랫폼 선택             │
│                                                              │
│  [STEP 2] 캡컷 스타일 에디터                                   │
│  Canvas 미리보기 | 원고 에디터 | 자막/BGM/해상도 설정           │
│                                                              │
│  [STEP 3] 발행 선택                                           │
│  MP4 다운로드 | 예약 발행 | 즉시 발행 | 클립보드 복사            │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP API (Flask REST)
┌────────────────────────▼─────────────────────────────────────┐
│                    서버 (Python Flask)                         │
│                                                              │
│  /api/generate     → LLM 원고 생성 (Gemini Flash / GPT-mini)  │
│  /api/upload       → 미디어 파일 저장                          │
│  /api/compose      → 영상 결합 (FFmpeg + MoviePy)            │
│  /api/schedule     → 예약 발행 등록                           │
│  /api/download/<id>→ 완성 영상 다운로드                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ LLM Client   │  │ VideoComposer│  │ Scheduler          │ │
│  │ Gemini Flash │  │ FFmpeg       │  │ APScheduler        │ │
│  │ GPT-4o-mini  │  │ MoviePy      │  │ SQLite             │ │
│  │ (텍스트 생성) │  │ Whisper(STT) │  │ (예약 관리)        │ │
│  └──────────────┘  └──────────────┘  └────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 4-2. 데이터 흐름

```
사용자 미디어 파일
        ↓ [업로드]
/uploads/{uuid}/original.*          ← 원본 저장
        ↓ [FFmpeg 전처리]
/uploads/{uuid}/normalized.mp4      ← 정규화된 영상
        ↓ [Whisper STT (영상의 경우)]
/uploads/{uuid}/transcript.txt      ← 음성→텍스트
        ↓ [LLM 원고 생성]
DB: content_history                 ← 생성 히스토리 저장
        ↓ [에디터에서 확인/수정]
subtitle_config (JSON)              ← 자막 설정값
        ↓ [FFmpeg 최종 결합]
/outputs/{uuid}/final_{platform}.mp4← 완성 영상
        ↓ [다운로드 or 발행]
DB: scheduled_posts                 ← 예약 발행 등록
```

---

## 5. 기술 스택 (Tech Stack)

### 백엔드

| 영역 | 기술 | 비용 | 선택 이유 |
|---|---|---|---|
| 웹 서버 | Python Flask | $0 | 경량, 로컬 실행 최적 |
| AI 원고 (1순위) | Gemini 1.5 Flash | $0.075/1M tok | **업계 최저가 LLM** |
| AI 원고 (2순위) | GPT-4o-mini | $0.15/1M tok | Gemini 대안 |
| Vision 분석 (유료) | Gemini 1.5 Flash Multimodal | 구독료 충당 | 비전 기능 차별화 |
| 로컬 STT | Whisper (로컬) | $0 | API 비용 없음 |
| 영상 처리 | FFmpeg + MoviePy | $0 | 서버 비용 Zero |
| 예약 스케줄러 | APScheduler | $0 | Flask 통합 |
| 데이터베이스 | SQLite | $0 | 로컬 파일 DB |

### 프론트엔드

| 영역 | 기술 | 선택 이유 |
|---|---|---|
| UI 구조 | Vanilla HTML/CSS/JS | 빠른 개발, 의존성 최소 |
| 영상 미리보기 | Canvas API + Video API | 실시간 자막 오버레이 |
| 파일 업로드 | Dropzone.js | 드래그앤드롭 UX |
| 에디터 | Quill.js | 리치텍스트 편집 |
| 스타일 | 커스텀 CSS (다크모드 + 글라스모피즘) | 프리미엄 UX |

### 월 예상 비용 (하루 10건 기준)

| 항목 | 비용 | 비고 |
|---|---|---|
| Gemini 1.5 Flash (원고) | **~$0.1~1/월** | 입력 평균 500토큰 × 300건 |
| Whisper (STT) | **$0** | 로컬 실행 |
| FFmpeg (영상 처리) | **$0** | 로컬 실행 |
| 서버 | **$0** | 로컬 환경 |
| **총합** | **$0.1~1/월** | 기존 대비 98% 절감 |

---

## 6. 수익 모델 (Monetization)

### 6-1. 플랜 구조

```
┌─────────────────────┬─────────────────────┬────────────────────┐
│      FREE 플랜       │    PRO 플랜          │  AGENCY 플랜       │
│      (무료 체험)      │    (월 9,900원)     │  (월 29,900원)    │
├─────────────────────┼─────────────────────┼────────────────────┤
│ 일일 원고 생성: 3건   │ 일일 원고 생성: 무제한│ 모든 PRO 기능      │
│ 영상 결합: 3건/일     │ 영상 결합: 무제한    │ 멀티 계정 5개      │
│ BGM: 무료 6곡        │ BGM: 프리미엄 100곡  │ 팀 협업 기능       │
│ 해상도: 720p         │ 해상도: 1080p Full   │ 우선 처리 큐       │
│ Vision 분석: ✗       │ Vision 분석: ✅      │ API 직접 연동      │
│ 워터마크: ✅          │ 워터마크: ✗         │ 전담 지원          │
│ 예약 발행: 1건        │ 예약 발행: 무제한    │ 예약 발행: 무제한  │
└─────────────────────┴─────────────────────┴────────────────────┘
```

### 6-2. 무료→유료 전환 전략

```
[무료 사용자 전환 유도 시나리오]

1. 일일 한도 도달 시
   → "오늘 3건을 모두 사용했어요. PRO 플랜으로 업그레이드하면 무제한으로!"

2. 사진 업로드 시
   → "지금은 주제를 직접 입력하고 있어요. PRO에서는 사진만 올리면 AI가 자동 분석해요!"
   (Vision 기능 미리보기 → 유료 전환 유도)

3. 영상 완성 시 워터마크
   → "PRO에서는 워터마크 없이 깔끔하게 다운로드!"
```

### 6-3. 수익 목표

| 단계 | MAU | 전환율 | 월 수익 |
|---|---|---|---|
| 베타 (1~3개월) | 100명 | 5% | ~50,000원 |
| 초기 (4~6개월) | 500명 | 8% | ~400,000원 |
| 성장 (7~12개월) | 2,000명 | 10% | ~2,000,000원 |

---

## 7. 프로젝트 디렉토리 구조

```
week-project/
├── PROJECT_PLAN.md              기획서 (이 파일)
├── README.md                    설치 가이드
├── requirements.txt             Python 패키지
├── .env.example                 환경변수 예시
├── start.bat                    Windows 실행 스크립트
│
├── app.py                       Flask 메인 앱
├── config.py                    설정 (플랜, API, 경로)
│
├── core/
│   ├── llm_client.py            LLM 클라이언트 (Gemini/GPT 자동 선택)
│   ├── ai_writer.py             AI 원고 생성 엔진
│   ├── platform_prompts.py      플랫폼별 SEO 프롬프트
│   ├── video_composer.py        영상 결합 파이프라인 (사진→MP4)
│   ├── video_processor.py       영상 처리 (자막/BGM/리사이즈)
│   ├── scheduler.py             예약 발행 스케줄러
│   └── db.py                    SQLite CRUD
│
├── static/
│   ├── css/style.css            스타일시트
│   ├── js/
│   │   ├── main.js              메인 로직
│   │   ├── editor.js            캡컷 스타일 에디터
│   │   └── preview.js           Canvas 실시간 미리보기
│   └── assets/
│       ├── bgm/                 무료 BGM (CC0)
│       │   ├── upbeat/
│       │   ├── calm/
│       │   └── seasonal/
│       └── fonts/               한국어 TTF 폰트
│
├── templates/
│   ├── index.html               메인 UI (3단계 플로우)
│   └── dashboard.html           예약 발행 대시보드
│
├── uploads/                     사용자 업로드 (gitignore)
├── outputs/                     FFmpeg 결합 결과 (gitignore)
└── data/
    └── posts.db                 SQLite DB (gitignore)
```

---

## 8. 6주 개발 로드맵 (v2.0 업데이트)

### WEEK 1 — 기초 구조 & 3단계 UI 구축
- [ ] Flask 앱 기본 구조 + SQLite 초기화
- [ ] 3단계 UX 흐름 메인 UI (index.html)
  - STEP 1: 드래그앤드롭 업로드 + 주제 입력 + 플랫폼 선택
  - STEP 2: 캡컷 스타일 에디터 레이아웃
  - STEP 3: 다운로드/예약/발행 버튼
- [ ] config.py (플랜별 제한 설정 포함)
- [ ] .env 구조 (Gemini API Key + OpenAI API Key)

### WEEK 2 — AI 원고 생성 엔진 (LLM 최저가 구조)
- [ ] core/llm_client.py: Gemini 1.5 Flash 우선, GPT-4o-mini 폴백
- [ ] core/platform_prompts.py: 플랫폼별 SEO 프롬프트 딕셔너리
- [ ] core/ai_writer.py: 원고 생성 + 히스토리 저장
- [ ] 무료 플랜 일일 한도 체크 미들웨어
- [ ] 에디터 자동 삽입 + 재생성/복사 버튼

### WEEK 3 — 영상 결합 파이프라인 (핵심!)
- [ ] FFmpeg + MoviePy 환경 세팅
- [ ] core/video_composer.py: 사진 슬라이드쇼 → MP4 결합
- [ ] core/video_processor.py: 자막 오버레이 (폰트/크기/위치/색상)
- [ ] Whisper 로컬 STT 한국어 테스트
- [ ] BGM 믹싱 + 플랫폼별 해상도 변환
- [ ] 완성 MP4 다운로드 API (/api/download/<id>)

### WEEK 4 — 캡컷 스타일 에디터 UI 구현
- [ ] static/js/editor.js: 자막 설정 패널 (폰트/크기/색상/위치)
- [ ] static/js/preview.js: Canvas API 실시간 미리보기
- [ ] BGM 선택 + 미리듣기 + 볼륨 슬라이더
- [ ] "영상 완성하기" 버튼 → 서버 렌더링 → 진행률 표시 → 다운로드

### WEEK 5 — 예약 발행 + 플랫폼 API 연동
- [ ] APScheduler 예약 발행 시스템
- [ ] Meta Graph API 인스타그램 발행
- [ ] 네이버 Open API 블로그 발행
- [ ] 발행 상태 대시보드 (dashboard.html)
- [ ] 에러 핸들링 + 재시도 로직

### WEEK 6 — 수익 모델 구현 + 배포 준비
- [ ] 플랜별 기능 제한 로직 (FREE/PRO/AGENCY)
- [ ] 무료→유료 전환 UI (한도 초과 시 업그레이드 모달)
- [ ] 유료 기능: Vision 자동 분석 (Gemini 멀티모달)
- [ ] 유료 기능: 워터마크 on/off
- [ ] start.bat 완성 + README 설치 가이드
- [ ] 배포 준비 (선택: Render.com 무료 플랜)

---

## 9. 단계별 실행 프롬프트 가이드 (Antigravity IDE용)

> 아래 프롬프트를 순서대로 Antigravity IDE에 입력하면
> 각 주차별 개발을 차근차근 진행할 수 있습니다.

---

### STEP 1 — 환경 세팅 및 Flask 기초 구조

```
Flask 기반 소상공인 SNS 자동 발행 시스템의 기초 구조를 설정해줘.

핵심 요구사항:
1. requirements.txt 생성:
   flask, google-generativeai, openai, moviepy, openai-whisper,
   apscheduler, python-dotenv, ffmpeg-python, Pillow

2. app.py 생성 (REST API 엔드포인트):
   - POST /api/generate     — AI 원고 생성
   - POST /api/upload       — 미디어 파일 업로드
   - POST /api/compose      — FFmpeg 영상 결합 (백그라운드)
   - GET  /api/status/<id>  — 영상 처리 상태 조회
   - GET  /api/download/<id>— 완성 영상 다운로드
   - POST /api/schedule     — 예약 발행 등록
   - GET  /api/scheduled-posts — 예약 목록 조회
   - GET  /                 — 메인 UI

3. config.py:
   - GEMINI_API_KEY, OPENAI_API_KEY (둘 다 지원)
   - FREE_PLAN_DAILY_LIMIT = 3 (일일 무료 한도)
   - 플랫폼별 해상도/스펙 딕셔너리

4. core/db.py:
   - scheduled_posts 테이블
   - content_history 테이블
   - compose_jobs 테이블 (영상 처리 작업 상태 추적)
```

---

### STEP 2 — LLM 최저가 원고 생성 엔진

```
core/llm_client.py 와 core/ai_writer.py 를 구현해줘.

핵심 요구사항:
1. llm_client.py:
   - Gemini 1.5 Flash 우선 사용 (google-generativeai)
   - GEMINI_API_KEY 없으면 GPT-4o-mini 자동 폴백
   - generate_text(prompt, system_prompt) → str 공통 인터페이스
   - Vision 분석: analyze_image(image_path, prompt) → str
     (is_premium=True 일 때만 실행, 아니면 ValueError)

2. ai_writer.py:
   - generate_content(topic, platform, business_type, location,
                      image_path=None, is_premium=False)
   - 무료: topic 텍스트만으로 원고 생성
   - 유료: image_path가 있으면 Gemini Vision으로 사진 분석 후 원고 생성
   - 반환: {"title", "caption", "body", "hashtags", "full_post"}
   - 일일 한도 체크 (FREE_PLAN_DAILY_LIMIT=3)
```

---

### STEP 3 — FFmpeg 영상 결합 파이프라인

```
core/video_composer.py 와 core/video_processor.py 를 구현해줘.

핵심 요구사항:
1. video_composer.py (사진/영상 → MP4 결합):
   compose_from_photos(image_paths, subtitle_text, bgm_path,
                        platform, subtitle_config) → output_path
   - 사진 여러 장 → 슬라이드쇼 (각 3초, 페이드 전환)
   - MoviePy ImageClip → concatenate_videoclips
   - 자막 오버레이 (subtitle_config 설정 반영)
   
   compose_from_video(video_path, subtitle_text, bgm_path,
                       platform, subtitle_config) → output_path
   - 기존 영상에 자막+BGM 합성

2. video_processor.py:
   - subtitle_config: {font, size, color, position, stroke_color, stroke_width}
   - add_subtitle(clip, text, config) → clip
   - mix_bgm(clip, bgm_path, volume=0.3) → clip  
   - resize_for_platform(clip, platform) → clip
   - 출력: MP4 (H.264, AAC), 50MB 이하 최적화

3. Whisper STT:
   - extract_transcript(video_path) → {"text", "segments"}
   - segments: [{start, end, text}] — 세그먼트별 자막 타이밍용
```

---

### STEP 4 — 캡컷 스타일 에디터 UI

```
templates/index.html 과 static/js/editor.js 를 구현해줘.

핵심 요구사항:
3단계 UX 플로우로 구성:

STEP 1 패널: 업로드 & 입력
- 드래그앤드롭 멀티파일 업로드 (사진 여러 장 or 영상 1개)
- 주제 텍스트 입력 textarea
- 플랫폼 선택 탭 (인스타/틱톡/당근/블로그)
- 업종/지역 입력 (선택)
- "AI 원고 생성" 버튼

STEP 2 패널: 캡컷 스타일 에디터
- 왼쪽: 영상/사진 Canvas 미리보기 (자막 실시간 오버레이)
- 오른쪽: 원고 에디터 (재생성/복구/복사)
- 하단 탭: 자막설정(폰트/크기/색상/위치) | BGM선택(미리듣기+볼륨) | 해상도
- "영상 완성하기" 버튼 → 서버 렌더링 → 진행률 표시

STEP 3 패널: 발행
- MP4 다운로드 버튼 (완성 후 활성화)
- 예약 발행 (날짜/시간 선택 + 예약 버튼)
- 즉시 발행 (인스타그램)
- 클립보드 복사 + 앱 이동 (당근마켓)
- 예약 목록 테이블

다크모드 글라스모피즘 디자인 적용
Canvas API로 자막 실시간 미리보기 구현
```

---

### STEP 5 — 예약 발행 + 플랫폼 API 연동

```
core/scheduler.py 와 플랫폼 발행 로직을 구현해줘.

핵심 요구사항:
1. APScheduler 1분 간격 pending 게시물 체크
2. publishers/ 폴더 구조:
   - instagram.py: Meta Graph API (영상 릴스 + 캡션)
   - naver_blog.py: 네이버 Open API (텍스트 포스팅)
   - danggeun.py: 클립보드 복사 + 알림 (반자동)
3. 발행 실패 시 재시도 (최대 3회, 5분 간격)
4. templates/dashboard.html: 예약 목록 대시보드 (상태별 필터)
```

---

### STEP 6 — 수익 모델 구현 + 마무리

```
수익 모델 로직과 최종 배포 준비를 해줘.

핵심 요구사항:
1. 플랜 제한 미들웨어:
   - FREE: 일일 3건 한도, 워터마크 추가, Vision 차단
   - PRO: 무제한, 워터마크 없음, Vision 허용, 프리미엄 BGM
   - 한도 초과 시 업그레이드 모달 UI 표시

2. 유료 기능 구현:
   - Vision 자동 분석 (Gemini 멀티모달, 유료 전용)
   - 영상 워터마크 on/off (FFmpeg drawtext 필터)
   - 프리미엄 BGM 폴더 접근 권한

3. 배포 준비:
   - start.bat (더블클릭 실행)
   - .env.example (Gemini/OpenAI 키 가이드)
   - README.md (설치/실행/API 키 발급 가이드)
```

---

## 10. 리스크 및 대응 방안

| 리스크 | 심각도 | 대응 방안 |
|---|---|---|
| FFmpeg 로컬 설치 어려움 | 중 | 설치 가이드 스크립트 + winget 자동화 |
| Whisper STT 처리 시간 | 중 | 백그라운드 비동기 처리 + 진행률 표시 |
| MoviePy 영상 렌더링 시간 | 중 | 백그라운드 큐 + 완료 알림 토스트 |
| Gemini API 정책 변경 | 중 | GPT-4o-mini 자동 폴백 구조 |
| 인스타그램 API 정책 변경 | 높 | 반자동(클립보드) 병행 항상 유지 |
| 유료 전환율 저조 | 높 | Vision 기능 무료 1회 체험 제공 후 유료 유도 |

---

## 11. 향후 확장 로드맵 (V2+)

- [ ] **클라우드 배포**: Render.com / Railway (소규모 트래픽, 무료 플랜 가능)
- [ ] **SaaS 전환**: Supabase Auth + 구독 결제 (토스페이먼츠/Stripe)
- [ ] **틱톡 API**: 자동 업로드 완전 자동화
- [ ] **AI 이미지 생성**: 사진 없을 때 Stable Diffusion으로 대체 이미지 생성
- [ ] **성과 분석**: 좋아요/댓글/도달 수 통계 대시보드
- [ ] **멀티 계정**: 여러 SNS 계정 동시 관리
- [ ] **템플릿 마켓**: 업종별 원고 템플릿 공유 플랫폼

---

*문서 끝 — PROJECT_PLAN.md v2.0*
*업데이트: 2026-08-07 | 대표님 피드백 반영 버전*