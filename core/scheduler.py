"""
core/scheduler.py — 백그라운드 예약 발행 스케줄러
매 분마다 DB를 검사하여 예약된 시간이 지난 게시물을 퍼블리싱
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apscheduler.schedulers.background import BackgroundScheduler
from core.db import get_pending_posts, update_post_status
from core.publisher import Publisher

class PostScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.publisher = Publisher()
        # 매 1분마다 check_and_publish 실행
        self.scheduler.add_job(self.check_and_publish, 'interval', minutes=1)

    def check_and_publish(self):
        print("\n[Scheduler] ⏰ 예약 발행 대기열 검사 중...")
        pending_posts = get_pending_posts()
        
        if not pending_posts:
            return

        for post in pending_posts:
            post_id = post["id"]
            is_retry = post.get("status") == "failed"
            retry_label = f" (재시도 {post.get('retry_count', 0) + 1}/3)" if is_retry else ""
            print(f"[Scheduler] 예약물 발견: ID {post_id} ({post['platform']}){retry_label} - 예약시간: {post['scheduled_at']}")

            # 발송 시도
            result = self.publisher.publish_post(post)

            if result["success"]:
                update_post_status(post_id, status="published")
                print(f"[Scheduler] 🎉 ID {post_id} 발행 완료 처리됨!")
            else:
                update_post_status(post_id, status="failed", error_msg=result.get("error"))
                next_retry = post.get("retry_count", 0) + 1
                if next_retry >= 3:
                    print(f"[Scheduler] ❌ ID {post_id} 발행 실패 — 재시도 3회 모두 소진, 더 이상 재시도하지 않음: {result.get('error')}")
                else:
                    print(f"[Scheduler] ⚠️ ID {post_id} 발행 실패 ({next_retry}/3) — 5분 후 재시도 예정: {result.get('error')}")

    def start(self):
        print("[Scheduler] 🚀 백그라운드 스케줄러 시작 완료 (1분 주기)")
        self.scheduler.start()
        
    def stop(self):
        self.scheduler.shutdown()
