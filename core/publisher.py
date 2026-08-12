"""
core/publisher.py — 실제 SNS 자동 발행 엔진
네이버 블로그, X(트위터), 틱톡에 실제로 글을 게시합니다.
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.db import get_oauth_token, save_oauth_token


class Publisher:
    """각 플랫폼 API를 호출하여 실제 게시물을 발행하는 엔진"""

    def __init__(self):
        from config import (
            NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_BLOG_ID,
            X_API_KEY, X_API_SECRET,
            TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET,
        )
        # Naver
        self.naver_client_id = NAVER_CLIENT_ID
        self.naver_client_secret = NAVER_CLIENT_SECRET
        self.naver_blog_id = NAVER_BLOG_ID

        # X (Twitter) — consumer key/secret은 앱 식별용(공용), 실제 발행용
        # access_token/secret은 사용자별로 oauth_tokens에서 조회한다 (아래 _publish_x_twitter 참고)
        self.x_api_key = X_API_KEY
        self.x_api_secret = X_API_SECRET

        # TikTok
        self.tiktok_client_key = TIKTOK_CLIENT_KEY
        self.tiktok_client_secret = TIKTOK_CLIENT_SECRET

    # ─────────────────────────────────────────────────────────
    # 메인 디스패처
    # ─────────────────────────────────────────────────────────
    def publish_post(self, post: dict) -> dict:
        """
        포스트 데이터를 받아 해당 플랫폼으로 실제 전송
        post keys: id, platform, title, content, caption, hashtags, media_path
        """
        platform = post.get("platform", "")
        print(f"[Publisher] 🚀 '{platform}'으로 실제 전송 시작 (Post ID: {post.get('id')})")

        dispatch = {
            "naver_blog": self._publish_naver_blog,
            "x_twitter":  self._publish_x_twitter,
            "tiktok":     self._publish_tiktok,
            "instagram":  self._publish_instagram,
            "facebook":   self._publish_facebook,
            "threads":    self._publish_threads,
        }

        handler = dispatch.get(platform)
        if not handler:
            return {"success": False, "error": f"지원하지 않는 플랫폼: {platform}"}

        try:
            result = handler(post)
            if result["success"]:
                print(f"[Publisher] ✅ '{platform}' 전송 완료!")
            else:
                print(f"[Publisher] ❌ '{platform}' 전송 실패: {result.get('error')}")
            return result
        except Exception as e:
            print(f"[Publisher] ❌ '{platform}' 전송 중 예외: {e}")
            return {"success": False, "error": str(e)}

    # ─────────────────────────────────────────────────────────
    # OAuth 토큰 조회 (필요 시 refresh_token으로 자동 갱신)
    # ─────────────────────────────────────────────────────────
    def _get_valid_access_token(self, user_id: int, platform: str, refresh_fn) -> str:
        """
        DB에 저장된 access_token을 반환. 만료 시각이 지났으면 refresh_fn으로
        갱신을 시도하고 새 토큰을 저장한 뒤 반환한다. 저장된 토큰이 없으면 None.
        """
        token_row = get_oauth_token(user_id, platform)
        if not token_row:
            return None

        expires_at = token_row.get("expires_at")
        if expires_at:
            try:
                expired = datetime.now() >= datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                expired = False

            if expired and token_row.get("refresh_token"):
                try:
                    new_token = refresh_fn(token_row["refresh_token"])
                    new_expires_at = None
                    if new_token.get("expires_in"):
                        new_expires_at = (
                            datetime.now() + timedelta(seconds=int(new_token["expires_in"]))
                        ).strftime("%Y-%m-%d %H:%M:%S")

                    save_oauth_token(
                        user_id,
                        platform,
                        access_token=new_token["access_token"],
                        refresh_token=new_token.get("refresh_token", token_row.get("refresh_token")),
                        expires_at=new_expires_at,
                    )
                    return new_token["access_token"]
                except Exception as e:
                    print(f"[OAuth Refresh Error] {platform}: {e} — 기존 토큰으로 재시도")

        return token_row["access_token"]

    # ─────────────────────────────────────────────────────────
    # 1. 네이버 블로그 발행
    # ─────────────────────────────────────────────────────────
    def _publish_naver_blog(self, post: dict) -> dict:
        """
        네이버 블로그 반자동 발행.

        네이버는 외부 개발자에게 공식 블로그 글쓰기 API를 제공하지 않는다
        (openapi.naver.com/blog/writePost.json 호출 시 "API does not exist" 반환, 실제 확인됨).
        따라서 서버가 직접 글을 올리는 대신, 완성된 원고와 글쓰기 페이지 URL을 돌려주고
        프론트엔드가 클립보드 복사 + 새 창 열기로 사용자의 마지막 붙여넣기/발행만 남기는
        반자동 방식을 사용한다.
        """
        title = post.get("title", "")
        content = post.get("content", "")
        hashtags = post.get("hashtags", "")

        full_text = content
        if hashtags:
            full_text += f"\n\n{hashtags}"

        if self.naver_blog_id:
            write_url = f"https://blog.naver.com/PostWriteForm.naver?blogId={self.naver_blog_id}"
            blog_url = f"https://blog.naver.com/{self.naver_blog_id}"
        else:
            write_url = "https://blog.naver.com/"
            blog_url = "https://blog.naver.com/"

        return {
            "success": True,
            "manual_required": True,
            "url": blog_url,
            "write_url": write_url,
            "platform": "naver_blog",
            "prepared_title": title,
            "prepared_content": full_text,
            "note": "네이버는 공식 자동 글쓰기 API가 없어 자동 게시가 불가능합니다. "
                    "원고가 클립보드에 복사됩니다 — 새로 열리는 글쓰기 창에 붙여넣기 후 직접 발행해주세요.",
        }

    # ─────────────────────────────────────────────────────────
    # 2. X (트위터) 발행
    # ─────────────────────────────────────────────────────────
    def _publish_x_twitter(self, post: dict) -> dict:
        """
        X (Twitter) API v2를 통해 트윗 발행
        tweepy 라이브러리 사용. access_token/secret은 사용자별로 3-legged OAuth 1.0a로
        연결된 값을 oauth_tokens에서 조회한다(core/oauth_x.py 참고).
        """
        if not self.x_api_key or not self.x_api_secret:
            return {"success": False, "error": "X(트위터) 앱 키가 설정되지 않았습니다. .env 파일을 확인해주세요."}

        token_row = get_oauth_token(post.get("user_id"), "x_twitter")
        if not token_row:
            return {
                "success": False,
                "error": "X(트위터) 계정 연결이 필요합니다. 브라우저에서 /auth/x/login 에 접속해 먼저 로그인해주세요.",
            }

        extra = json.loads(token_row.get("extra_data") or "{}")
        access_token_secret = extra.get("access_token_secret")
        if not access_token_secret:
            return {"success": False, "error": "X(트위터) 연결 정보가 손상되었습니다. /auth/x/login 을 다시 진행해주세요."}

        try:
            import tweepy

            # OAuth 1.0a 인증 (User Context) — 사용자별 access_token 사용
            client = tweepy.Client(
                consumer_key=self.x_api_key,
                consumer_secret=self.x_api_secret,
                access_token=token_row["access_token"],
                access_token_secret=access_token_secret,
            )

            content = post.get("content", "")
            hashtags = post.get("hashtags", "")
            title = post.get("title", "")

            # 트윗 텍스트 구성 (280자 제한)
            tweet_text = ""
            if title:
                tweet_text = f"{title}\n\n"

            tweet_text += content

            if hashtags:
                tweet_text += f"\n\n{hashtags}"

            # 280자 초과 시 자르기
            if len(tweet_text) > 280:
                tweet_text = tweet_text[:277] + "..."

            # 트윗 게시
            response = client.create_tweet(text=tweet_text)

            if response and response.data:
                tweet_id = response.data.get("id", "")
                tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"
                print(f"[X/Twitter] ✅ 트윗 발행 성공! ID: {tweet_id}")
                return {
                    "success": True,
                    "url": tweet_url,
                    "platform": "x_twitter",
                    "tweet_id": tweet_id,
                }
            else:
                return {"success": False, "error": "트윗 발행 응답이 비어있습니다"}

        except tweepy.errors.Forbidden as e:
            return {"success": False, "error": f"X API 권한 오류 (Free 플랜에서는 v2 쓰기가 제한될 수 있습니다): {str(e)}"}
        except tweepy.errors.Unauthorized as e:
            return {"success": False, "error": f"X API 인증 실패 - 키를 다시 확인해주세요: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"X(트위터) 발행 실패: {str(e)}"}

    # ─────────────────────────────────────────────────────────
    # 3. 틱톡 발행
    # ─────────────────────────────────────────────────────────
    def _publish_tiktok(self, post: dict) -> dict:
        """
        TikTok Content Posting API를 통해 게시 (사용자 로그인 access_token 필요)
        참고: 틱톡은 동영상 전용 플랫폼이므로, 텍스트만 있을 경우
        '포토 모드(이미지 슬라이드)' 형태로 게시하거나 알림만 반환
        """
        from core.oauth_tiktok import refresh_access_token
        access_token = self._get_valid_access_token(post.get("user_id"), "tiktok", refresh_access_token)

        if not access_token:
            return {
                "success": False,
                "error": "틱톡 계정 연결이 필요합니다. 브라우저에서 /auth/tiktok/login 에 접속해 먼저 로그인해주세요.",
            }

        content = post.get("content", "")
        hashtags = post.get("hashtags", "")
        media_path = post.get("media_path", "")

        # 틱톡은 영상이 필수 — 영상 없으면 안내 메시지 반환
        if not media_path or not Path(media_path).exists():
            caption = content
            if hashtags:
                caption += f" {hashtags}"

            return {
                "success": True,
                "url": "",
                "platform": "tiktok",
                "note": "틱톡은 영상 파일이 필수입니다. 원고가 준비되었으니, 영상을 첨부하여 다시 발행해주세요.",
                "prepared_caption": caption[:2200],
            }

        # 영상이 있는 경우: TikTok Content Posting API 호출
        try:
            caption = content
            if hashtags:
                caption += f" {hashtags}"

            # Step 1: 업로드 초기화
            init_url = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            }
            init_payload = {
                "post_info": {
                    "title": caption[:150],
                    "privacy_level": "SELF_ONLY",  # 초기에는 비공개로 게시
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": os.path.getsize(media_path),
                    "chunk_size": os.path.getsize(media_path),
                    "total_chunk_count": 1,
                }
            }

            resp = requests.post(init_url, headers=headers, json=init_payload, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                publish_id = data.get("data", {}).get("publish_id", "")
                upload_url = data.get("data", {}).get("upload_url", "")

                if upload_url:
                    # Step 2: 영상 업로드
                    with open(media_path, "rb") as video_file:
                        upload_resp = requests.put(
                            upload_url,
                            headers={
                                "Content-Range": f"bytes 0-{os.path.getsize(media_path) - 1}/{os.path.getsize(media_path)}",
                                "Content-Type": "video/mp4",
                            },
                            data=video_file,
                            timeout=120,
                        )

                    if upload_resp.status_code in [200, 201]:
                        print(f"[TikTok] ✅ 영상 업로드 및 게시 완료! Publish ID: {publish_id}")
                        return {
                            "success": True,
                            "url": f"https://www.tiktok.com",
                            "platform": "tiktok",
                            "publish_id": publish_id,
                        }

                return {
                    "success": False,
                    "error": f"틱톡 업로드 초기화 실패: {data}",
                }
            else:
                return {"success": False, "error": f"틱톡 API 오류 ({resp.status_code}): {resp.text}"}

        except Exception as e:
            return {"success": False, "error": f"틱톡 발행 실패: {str(e)}"}

    # ─────────────────────────────────────────────────────────
    # 메타(페이스북/인스타그램) 공통 헬퍼
    # ─────────────────────────────────────────────────────────
    def _build_public_media_url(self, media_path: str) -> str:
        """로컬 파일 경로를 메타 API가 접근 가능한 공개 URL로 변환"""
        from config import PUBLIC_BASE_URL, OUTPUT_DIR

        p = Path(media_path).resolve()
        filename = p.name
        try:
            p.relative_to(Path(OUTPUT_DIR).resolve())
            return f"{PUBLIC_BASE_URL}/outputs/{filename}"
        except ValueError:
            return f"{PUBLIC_BASE_URL}/uploads/{filename}"

    # ─────────────────────────────────────────────────────────
    # 4. 인스타그램 (메타 Graph API)
    # ─────────────────────────────────────────────────────────
    def _publish_instagram(self, post: dict) -> dict:
        """인스타그램 비즈니스 계정에 게시 (사용자 로그인으로 연결된 페이지 액세스 토큰 필요)"""
        token_row = get_oauth_token(post.get("user_id"), "instagram")
        if not token_row:
            return {
                "success": False,
                "error": "인스타그램 계정 연결이 필요합니다. 브라우저에서 /auth/meta/login 에 접속해 먼저 로그인해주세요.",
            }

        access_token = token_row["access_token"]
        extra = json.loads(token_row.get("extra_data") or "{}")
        ig_user_id = extra.get("ig_user_id")

        if not ig_user_id:
            return {
                "success": False,
                "error": "연결된 인스타그램 비즈니스 계정을 찾을 수 없습니다. 페이지에 인스타그램 계정이 연결되어 있는지 확인 후 /auth/meta/login 을 다시 진행해주세요.",
            }

        content = post.get("content", "")
        hashtags = post.get("hashtags", "")
        media_path = post.get("media_path", "")

        caption = content
        if hashtags:
            caption += f" {hashtags}"

        # 인스타그램은 텍스트 단독 게시가 불가능 — 미디어 없으면 안내 메시지 반환
        if not media_path or not Path(media_path).exists():
            return {
                "success": True,
                "url": "",
                "platform": "instagram",
                "note": "인스타그램은 사진 또는 영상이 필수입니다. 원고가 준비되었으니, 미디어를 첨부하여 다시 발행해주세요.",
                "prepared_caption": caption[:2200],
            }

        try:
            media_url = self._build_public_media_url(media_path)
            ext = Path(media_path).suffix.lower()
            is_video = ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]

            graph_base = "https://graph.facebook.com/v19.0"
            create_payload = {"caption": caption[:2200], "access_token": access_token}
            if is_video:
                create_payload["media_type"] = "REELS"
                create_payload["video_url"] = media_url
            else:
                create_payload["image_url"] = media_url

            resp = requests.post(f"{graph_base}/{ig_user_id}/media", data=create_payload, timeout=60)
            data = resp.json()

            if "id" not in data:
                error_msg = data.get("error", {}).get("message", str(data))
                return {"success": False, "error": f"인스타그램 미디어 생성 실패: {error_msg}"}

            creation_id = data["id"]

            # 영상은 메타 서버 처리 시간이 필요 — FINISHED 상태가 될 때까지 폴링 (최대 약 2분)
            if is_video:
                for _ in range(24):
                    status_resp = requests.get(
                        f"{graph_base}/{creation_id}",
                        params={"fields": "status_code", "access_token": access_token},
                        timeout=15,
                    )
                    status = status_resp.json().get("status_code")
                    if status == "FINISHED":
                        break
                    if status == "ERROR":
                        return {"success": False, "error": "인스타그램 영상 처리 중 오류가 발생했습니다."}
                    time.sleep(5)

            publish_resp = requests.post(
                f"{graph_base}/{ig_user_id}/media_publish",
                data={"creation_id": creation_id, "access_token": access_token},
                timeout=30,
            )
            publish_data = publish_resp.json()

            if "id" not in publish_data:
                error_msg = publish_data.get("error", {}).get("message", str(publish_data))
                return {"success": False, "error": f"인스타그램 게시 실패: {error_msg}"}

            media_id = publish_data["id"]

            permalink_resp = requests.get(
                f"{graph_base}/{media_id}",
                params={"fields": "permalink", "access_token": access_token},
                timeout=15,
            )
            permalink = permalink_resp.json().get("permalink", "")

            print(f"[Instagram] ✅ 게시 완료! Media ID: {media_id}")
            return {
                "success": True,
                "url": permalink or "https://www.instagram.com/",
                "platform": "instagram",
                "media_id": media_id,
            }

        except Exception as e:
            return {"success": False, "error": f"인스타그램 발행 실패: {str(e)}"}

    # ─────────────────────────────────────────────────────────
    # 5. 페이스북 (메타 Graph API)
    # ─────────────────────────────────────────────────────────
    def _publish_facebook(self, post: dict) -> dict:
        """페이스북 페이지에 게시 (사용자 로그인으로 연결된 페이지 액세스 토큰 필요)"""
        token_row = get_oauth_token(post.get("user_id"), "facebook")
        if not token_row:
            return {
                "success": False,
                "error": "페이스북 계정 연결이 필요합니다. 브라우저에서 /auth/meta/login 에 접속해 먼저 로그인해주세요.",
            }

        page_access_token = token_row["access_token"]
        extra = json.loads(token_row.get("extra_data") or "{}")
        page_id = extra.get("page_id")

        if not page_id:
            return {
                "success": False,
                "error": "연결된 페이스북 페이지 정보를 찾을 수 없습니다. /auth/meta/login 을 다시 진행해주세요.",
            }

        content = post.get("content", "")
        hashtags = post.get("hashtags", "")
        message = content
        if hashtags:
            message += f"\n\n{hashtags}"

        try:
            url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
            resp = requests.post(url, data={"message": message, "access_token": page_access_token}, timeout=30)
            data = resp.json()

            if resp.status_code == 200 and data.get("id"):
                post_id = data["id"]
                print(f"[Facebook] ✅ 게시 완료! Post ID: {post_id}")
                return {
                    "success": True,
                    "url": f"https://www.facebook.com/{post_id}",
                    "platform": "facebook",
                    "post_id": post_id,
                }
            else:
                error_msg = data.get("error", {}).get("message", str(data))
                return {"success": False, "error": f"페이스북 API 오류: {error_msg}"}

        except Exception as e:
            return {"success": False, "error": f"페이스북 발행 실패: {str(e)}"}

    # ─────────────────────────────────────────────────────────
    # 6. 스레드 (메타 Threads API — 추후 활성화)
    # ─────────────────────────────────────────────────────────
    def _publish_threads(self, post: dict) -> dict:
        """스레드 API (메타 인증 대기 중)"""
        return {
            "success": False,
            "error": "스레드는 현재 메타 개발자 계정 인증 대기 중입니다. 인증 완료 후 자동으로 활성화됩니다.",
            "platform": "threads",
        }
