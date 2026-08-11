"""
core/db.py — SQLite 데이터베이스 초기화 및 CRUD 유틸리티
"""

import sqlite3
from datetime import datetime
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


def get_pending_posts():
    """발행 대기 중인 게시물 조회"""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        SELECT * FROM scheduled_posts
        WHERE status = 'pending' AND scheduled_at <= ?
        ORDER BY scheduled_at ASC
    """, (now,))
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
    """게시물 상태 업데이트"""
    conn = get_connection()
    cursor = conn.cursor()
    published_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "published" else None
    cursor.execute("""
        UPDATE scheduled_posts
        SET status = ?, error_msg = ?, published_at = ?
        WHERE id = ?
    """, (status, error_msg, published_at, post_id))
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


if __name__ == "__main__":
    init_db()
