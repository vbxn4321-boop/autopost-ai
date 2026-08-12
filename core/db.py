"""
core/db.py — SQLite 데이터베이스 초기화 및 CRUD 유틸리티
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys

# config.py에서 DB 경로 가져오기
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH


def get_connection():
    """SQLite 연결 반환 (Row 팩토리 포함)"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """DB 테이블 초기화 — 앱 시작 시 1회 실행"""
    conn = get_connection()
    cursor = conn.cursor()

    # 예약 발행 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            platform      TEXT    NOT NULL,
            title         TEXT,
            content       TEXT    NOT NULL,
            caption       TEXT,
            hashtags      TEXT,
            media_path    TEXT,
            bgm_path      TEXT,
            timeline_data TEXT,
            scheduled_at  DATETIME NOT NULL,
            status        TEXT    DEFAULT 'pending',
            error_msg     TEXT,
            retry_count   INTEGER DEFAULT 0,
            last_attempt_at DATETIME,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            published_at  DATETIME
        )
    """)

    # 생성된 원고 히스토리 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            platform      TEXT,
            topic         TEXT,
            business_type TEXT,
            location      TEXT,
            title         TEXT,
            caption       TEXT,
            body          TEXT,
            hashtags      TEXT,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # OAuth 액세스 토큰 저장 테이블 (네이버/틱톡/메타 등 사용자 로그인 인증 결과)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oauth_tokens (
            platform      TEXT PRIMARY KEY,
            access_token  TEXT NOT NULL,
            refresh_token TEXT,
            expires_at    DATETIME,
            extra_data    TEXT,
            updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 기존 DB(마이그레이션 전)에는 extra_data 컬럼이 없을 수 있으므로 안전하게 추가 시도
    try:
        cursor.execute("ALTER TABLE oauth_tokens ADD COLUMN extra_data TEXT")
    except sqlite3.OperationalError:
        pass  # 이미 컬럼이 존재하는 경우

    # 타임라인 에디터 도입 이전 DB에는 timeline_data 컬럼이 없을 수 있으므로 안전하게 추가 시도
    try:
        cursor.execute("ALTER TABLE scheduled_posts ADD COLUMN timeline_data TEXT")
    except sqlite3.OperationalError:
        pass  # 이미 컬럼이 존재하는 경우

    # 재시도 로직 도입 이전 DB에는 retry_count/last_attempt_at 컬럼이 없을 수 있으므로 안전하게 추가 시도
    try:
        cursor.execute("ALTER TABLE scheduled_posts ADD COLUMN retry_count INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE scheduled_posts ADD COLUMN last_attempt_at DATETIME")
    except sqlite3.OperationalError:
        pass

    # 브랜드 프로필 테이블 — 사업장 1개 기준 싱글톤(id=1). 최초 1회 입력해두면
    # 이후 모든 원고 생성 시 이 정보(가게 이름·소개·대표 메뉴 등)를 자동으로 반영한다.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brand_profile (
            id              INTEGER PRIMARY KEY CHECK (id = 1),
            brand_name      TEXT,
            business_type   TEXT,
            location        TEXT,
            tone            TEXT,
            description     TEXT,
            signature_items TEXT,
            keywords        TEXT,
            updated_at      DATETIME
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] 초기화 완료:", DB_PATH)


# ─── 예약 발행 CRUD ──────────────────────────────────────────

def create_scheduled_post(platform, content, caption, hashtags,
                           scheduled_at, title=None, media_path=None, bgm_path=None,
                           timeline_data=None):
    """예약 발행 게시물 저장"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO scheduled_posts
            (platform, title, content, caption, hashtags, media_path, bgm_path, timeline_data, scheduled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (platform, title, content, caption, hashtags, media_path, bgm_path, timeline_data, scheduled_at))
    post_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return post_id


MAX_RETRY_COUNT = 3
RETRY_INTERVAL_MINUTES = 5


def get_pending_posts():
    """
    발행 대기 중인 게시물 + 재시도 대상(실패했지만 재시도 횟수가 남았고,
    마지막 시도로부터 RETRY_INTERVAL_MINUTES가 지난) 게시물을 함께 조회
    """
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    retry_cutoff = (datetime.now() - timedelta(minutes=RETRY_INTERVAL_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        SELECT * FROM scheduled_posts
        WHERE (status = 'pending' AND scheduled_at <= ?)
           OR (status = 'failed' AND retry_count < ?
               AND (last_attempt_at IS NULL OR last_attempt_at <= ?))
        ORDER BY scheduled_at ASC
    """, (now, MAX_RETRY_COUNT, retry_cutoff))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_all_scheduled_posts():
    """모든 예약 게시물 조회 (대시보드용)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scheduled_posts ORDER BY scheduled_at DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def update_post_status(post_id, status, error_msg=None):
    """
    게시물 상태 업데이트. status='failed'일 때는 last_attempt_at을 찍고
    retry_count를 1 증가시켜 다음 재시도 시점(RETRY_INTERVAL_MINUTES 후)을 계산할 수 있게 한다.
    """
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    published_at = now_str if status == "published" else None

    if status == "failed":
        cursor.execute("""
            UPDATE scheduled_posts
            SET status = ?, error_msg = ?, published_at = ?,
                last_attempt_at = ?, retry_count = retry_count + 1
            WHERE id = ?
        """, (status, error_msg, published_at, now_str, post_id))
    else:
        cursor.execute("""
            UPDATE scheduled_posts
            SET status = ?, error_msg = ?, published_at = ?, last_attempt_at = ?
            WHERE id = ?
        """, (status, error_msg, published_at, now_str, post_id))

    conn.commit()
    conn.close()

def delete_scheduled_post(post_id):
    """예약 게시물 삭제"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scheduled_posts WHERE id = ?", (post_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted



# ─── 원고 히스토리 CRUD ──────────────────────────────────────

def save_content_history(platform, topic, business_type, location,
                          title, caption, body, hashtags):
    """생성된 원고 히스토리 저장"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO content_history
            (platform, topic, business_type, location, title, caption, body, hashtags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (platform, topic, business_type, location, title, caption, body, hashtags))
    conn.commit()
    conn.close()


def get_recent_history(limit=20):
    """최근 원고 히스토리 조회"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM content_history
        ORDER BY created_at DESC LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


# ─── OAuth 토큰 CRUD ─────────────────────────────────────────

def save_oauth_token(platform, access_token, refresh_token=None, expires_at=None, extra_data=None):
    """
    플랫폼별 OAuth 액세스 토큰 저장/갱신 (upsert)
    extra_data: 플랫폼별 부가 정보(JSON 문자열). 예) 메타의 page_id/ig_user_id
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO oauth_tokens (platform, access_token, refresh_token, expires_at, extra_data, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(platform) DO UPDATE SET
            access_token = excluded.access_token,
            refresh_token = excluded.refresh_token,
            expires_at = excluded.expires_at,
            extra_data = excluded.extra_data,
            updated_at = CURRENT_TIMESTAMP
    """, (platform, access_token, refresh_token, expires_at, extra_data))
    conn.commit()
    conn.close()


def get_oauth_token(platform):
    """플랫폼별 저장된 OAuth 토큰 조회 (없으면 None)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM oauth_tokens WHERE platform = ?", (platform,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ─── 브랜드 프로필 CRUD (싱글톤, id=1) ───────────────────────

def get_brand_profile():
    """저장된 브랜드 프로필 조회 (아직 설정 전이면 None — 첫 방문 여부 판단에 사용)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM brand_profile WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_brand_profile(brand_name, business_type, location, tone,
                        description="", signature_items="", keywords=""):
    """브랜드 프로필 저장/수정 (upsert)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO brand_profile
            (id, brand_name, business_type, location, tone, description, signature_items, keywords, updated_at)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            brand_name = excluded.brand_name,
            business_type = excluded.business_type,
            location = excluded.location,
            tone = excluded.tone,
            description = excluded.description,
            signature_items = excluded.signature_items,
            keywords = excluded.keywords,
            updated_at = CURRENT_TIMESTAMP
    """, (brand_name, business_type, location, tone, description, signature_items, keywords))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
