"""
core/video_composer.py — 이미지 슬라이드쇼 생성 엔진
단일 이미지를 입력받아 영상으로 변환
"""
import os
import sys
from pathlib import Path
from moviepy.editor import ImageClip

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

if __name__ == "__main__":
    pass
