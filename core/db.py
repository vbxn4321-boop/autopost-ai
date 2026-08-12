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

    # 사용자 계정 테이블 (멀티테넌트: 사장님 1명당 계정 1개)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

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

    # OAuth 액세스 토큰 저장 테이블 (네이버/틱톡/메타/X 등 사용자 로그인 인증 결과)
    # 멀티테넌트 전환으로 PK가 platform 단일 → (user_id, platform) 복합키로 바뀌었으므로,
    # 구버전 스키마(platform PRIMARY KEY)가 감지되면 통째로 DROP 후 새로 만든다.
    # (Render 무료 플랜은 재배포 시 디스크가 초기화되는 비영구 파일시스템이라 실제 데이터 손실 영향 없음)
    cursor.execute("""
        SELECT sql FROM sqlite_master WHERE type='table' AND name='oauth_tokens'
    """)
    row = cursor.fetchone()
    if row and "user_id" not in row["sql"]:
        cursor.execute("DROP TABLE oauth_tokens")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oauth_tokens (
            user_id       INTEGER NOT NULL,
            platform      TEXT NOT NULL,
            access_token  TEXT NOT NULL,
            refresh_token TEXT,
            expires_at    DATETIME,
            extra_data    TEXT,
            updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, platform)
        )
    """)

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

    # 멀티테넌트 전환 — 예약글/원고 히스토리에 소유자(user_id) 컬럼 추가 (nullable, non-destructive)
    try:
        cursor.execute("ALTER TABLE scheduled_posts ADD COLUMN user_id INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE content_history ADD COLUMN user_id INTEGER")
    except sqlite3.OperationalError:
        pass

    # 브랜드 프로필 테이블 — 원래 사업장 1개 기준 싱글톤(id=1)이었으나 멀티테넌트 전환으로
    # 사용자당 1개(user_id UNIQUE)로 바뀌었다. 구버전 스키마 감지 시 DROP 후 재생성.
    cursor.execute("""
        SELECT sql FROM sqlite_master WHERE type='table' AND name='brand_profile'
    """)
    row = cursor.fetchone()
    if row and "user_id" not in row["sql"]:
        cursor.execute("DROP TABLE brand_profile")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brand_profile (
            user_id         INTEGER PRIMARY KEY,
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

def create_scheduled_post(user_id, platform, content, caption, hashtags,
                           scheduled_at, title=None, media_path=None, bgm_path=None,
                           timeline_data=None):
    """예약 발행 게시물 저장"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO scheduled_posts
            (user_id, platform, title, content, caption, hashtags, media_path, bgm_path, timeline_data, scheduled_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, platform, title, content, caption, hashtags, media_path, bgm_path, timeline_data, scheduled_at))
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


def get_all_scheduled_posts(user_id):
    """특정 사용자의 예약 게시물 조회 (대시보드용)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scheduled_posts WHERE user_id = ? ORDER BY scheduled_at DESC", (user_id,))
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

def delete_scheduled_post(post_id, user_id):
    """예약 게시물 삭제 (본인 소유 게시물만 삭제 가능 — 소유권 체크 겸함)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scheduled_posts WHERE id = ? AND user_id = ?", (post_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted



# ─── 원고 히스토리 CRUD ──────────────────────────────────────

def save_content_history(user_id, platform, topic, business_type, location,
                          title, caption, body, hashtags):
    """생성된 원고 히스토리 저장"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO content_history
            (user_id, platform, topic, business_type, location, title, caption, body, hashtags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, platform, topic, business_type, location, title, caption, body, hashtags))
    conn.commit()
    conn.close()


def get_recent_history(user_id, limit=20):
    """특정 사용자의 최근 원고 히스토리 조회"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM content_history
        WHERE user_id = ?
        ORDER BY created_at DESC LIMIT ?
    """, (user_id, limit))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


# ─── OAuth 토큰 CRUD (사용자별) ──────────────────────────────

def save_oauth_token(user_id, platform, access_token, refresh_token=None, expires_at=None, extra_data=None):
    """
    사용자×플랫폼별 OAuth 액세스 토큰 저장/갱신 (upsert)
    extra_data: 플랫폼별 부가 정보(JSON 문자열). 예) 메타의 page_id/ig_user_id, X의 access_token_secret
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO oauth_tokens (user_id, platform, access_token, refresh_token, expires_at, extra_data, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, platform) DO UPDATE SET
            access_token = excluded.access_token,
            refresh_token = excluded.refresh_token,
            expires_at = excluded.expires_at,
            extra_data = excluded.extra_data,
            updated_at = CURRENT_TIMESTAMP
    """, (user_id, platform, access_token, refresh_token, expires_at, extra_data))
    conn.commit()
    conn.close()


def get_oauth_token(user_id, platform):
    """사용자×플랫폼별 저장된 OAuth 토큰 조회 (없으면 None)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM oauth_tokens WHERE user_id = ? AND platform = ?", (user_id, platform))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# ─── 브랜드 프로필 CRUD (사용자당 1개) ───────────────────────

def get_brand_profile(user_id):
    """저장된 브랜드 프로필 조회 (아직 설정 전이면 None — 첫 방문 여부 판단에 사용)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM brand_profile WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_brand_profile(user_id, brand_name, business_type, location, tone,
                        description="", signature_items="", keywords=""):
    """브랜드 프로필 저장/수정 (upsert)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO brand_profile
            (user_id, brand_name, business_type, location, tone, description, signature_items, keywords, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            brand_name = excluded.brand_name,
            business_type = excluded.business_type,
            location = excluded.location,
            tone = excluded.tone,
            description = excluded.description,
            signature_items = excluded.signature_items,
            keywords = excluded.keywords,
            updated_at = CURRENT_TIMESTAMP
    """, (user_id, brand_name, business_type, location, tone, description, signature_items, keywords))
    conn.commit()
    conn.close()


# ─── 사용자 계정 CRUD ────────────────────────────────────────

def create_user(email, password_hash):
    """새 사용자 계정 생성, 생성된 user_id 반환"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (email, password_hash) VALUES (?, ?)
    """, (email, password_hash))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id


def get_user_by_email(email):
    """이메일로 사용자 조회 (없으면 None)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    """user_id로 사용자 조회 (없으면 None)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


if __name__ == "__main__":
    init_db()
