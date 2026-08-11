"""
core/video_composer.py — 이미지 슬라이드쇼 생성 엔진 + 타임라인 합성
단일 이미지를 영상으로 변환하거나, 여러 이미지/영상 클립을 순서대로 이어붙인다.
"""
import os
import sys
import uuid
from pathlib import Path
from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import OUTPUT_DIR, PLATFORM_SETTINGS

class VideoComposer:
    def __init__(self):
        print("[VideoComposer] 초기화 완료")

    def create_video_from_image(self, image_path: str, platform: str, duration: int = 5) -> str:
        """
        단일 이미지 파일을 동영상으로 변환 (크롭 후 지정된 해상도에 맞춤)
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")

        stem = Path(image_path).stem
        output_path = str(OUTPUT_DIR / f"{stem}_slideshow_{platform}.mp4")

        # 플랫폼별 해상도 가져오기
        settings = PLATFORM_SETTINGS.get(platform, PLATFORM_SETTINGS["instagram"])
        target_w, target_h = settings["video_resolution"]

        print(f"[Composer] 이미지 변환 시작: {image_path} -> {target_w}x{target_h}")
        img_clip = ImageClip(image_path)
        
        # 비율에 맞춰 화면 가득 채우기 (Crop)
        img_ratio = img_clip.w / img_clip.h
        target_ratio = target_w / target_h

        if img_ratio > target_ratio:
            # 원본이 가로로 더 김 -> 높이에 맞추고 가로를 잘라냄
            img_clip = img_clip.resize(height=target_h)
            img_clip = img_clip.crop(x_center=img_clip.w/2, width=target_w, height=target_h)
        else:
            # 원본이 세로로 더 김 -> 너비에 맞추고 세로를 잘라냄
            img_clip = img_clip.resize(width=target_w)
            img_clip = img_clip.crop(y_center=img_clip.h/2, width=target_w, height=target_h)

        # 재생 시간 및 FPS 설정
        video_clip = img_clip.set_duration(duration)

        # 렌더링
        video_clip.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            logger=None,
        )
        
        video_clip.close()
        print(f"[Composer] 슬라이드쇼 생성 완료: {output_path}")
        
        return output_path

    def compose_timeline(self, clips: list, platform: str, subtitle_text: str = "",
                          subtitle_options: dict = None, bgm_path: str = None) -> str:
        """
        타임라인 에디터에서 배치한 여러 이미지/영상 클립을 순서대로 이어붙여 하나의 영상으로 만든다.

        Args:
            clips: [{"path": str, "type": "image"|"video", "duration": float}, ...]
                   이미지 기본 2초, 영상 기본 4초 (duration 미지정 시)
            platform: 플랫폼 (해상도 결정)
            subtitle_text, subtitle_options, bgm_path: 있으면 기존 VideoProcessor 파이프라인을
                이어서 그대로 재사용해 자막/BGM까지 합성한다.

        Returns:
            str: 최종 완성된 영상 파일 경로
        """
        if not clips:
            raise ValueError("타임라인에 클립이 없습니다")

        settings = PLATFORM_SETTINGS.get(platform, PLATFORM_SETTINGS["instagram"])
        target_w, target_h = settings["video_resolution"]
        target_ratio = target_w / target_h

        moviepy_clips = []
        try:
            for item in clips:
                path = item["path"]
                if not os.path.exists(path):
                    raise FileNotFoundError(f"타임라인 클립 파일을 찾을 수 없습니다: {path}")

                item_type = item.get("type", "image")
                default_duration = 4 if item_type == "video" else 2
                duration = float(item.get("duration") or default_duration)

                if item_type == "video":
                    clip = VideoFileClip(path)
                    if clip.duration > duration:
                        clip = clip.subclip(0, duration)
                    # 영상이 지정 길이보다 짧으면 있는 그대로 사용 (억지로 늘리지 않음)
                else:
                    clip = ImageClip(path).set_duration(duration)

                # 클립마다 목표 해상도로 크롭/리사이즈 (서로 다른 비율이 섞여도 결과가 깨지지 않도록)
                clip_ratio = clip.w / clip.h
                if clip_ratio > target_ratio:
                    clip = clip.resize(height=target_h)
                    clip = clip.crop(x_center=clip.w / 2, width=target_w, height=target_h)
                else:
                    clip = clip.resize(width=target_w)
                    clip = clip.crop(y_center=clip.h / 2, width=target_w, height=target_h)

                moviepy_clips.append(clip)

            print(f"[Composer] 타임라인 합성 시작: 클립 {len(moviepy_clips)}개 → {target_w}x{target_h}")
            final = concatenate_videoclips(moviepy_clips, method="compose")

            concat_path = str(OUTPUT_DIR / f"timeline_{uuid.uuid4().hex}.mp4")
            final.write_videofile(
                concat_path, fps=24, codec="libx264", audio_codec="aac", logger=None
            )
            final.close()
        finally:
            for c in moviepy_clips:
                try:
                    c.close()
                except Exception:
                    pass

        # 이어붙인 영상에 기존 자막/BGM 파이프라인을 그대로 재사용해 최종 합성
        from core.video_processor import VideoProcessor
        vp = VideoProcessor()
        current_path = concat_path

        if subtitle_text:
            current_path = vp.add_subtitle_overlay(
                current_path, subtitle_text, platform, subtitle_options=subtitle_options
            )

        if bgm_path and os.path.exists(bgm_path):
            current_path = vp.add_bgm(current_path, bgm_path)

        print(f"[Composer] 타임라인 합성 완료: {current_path}")
        return current_path


if __name__ == "__main__":
    pass
