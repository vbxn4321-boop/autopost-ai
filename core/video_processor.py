"""
core/video_processor.py — 파이썬 기반 로컬 영상 합성 시스템
FFmpeg + MoviePy + Whisper (로컬 STT)
WEEK 3 구현 대상
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import OUTPUT_DIR, WHISPER_MODEL, WHISPER_LANGUAGE, PLATFORM_SETTINGS


class VideoProcessor:
    """
    로컬 영상 처리 파이프라인
    - 오디오 추출 및 STT (Whisper 로컬)
    - 자막 텍스트 오버레이 (MoviePy)
    - BGM 믹싱 (MoviePy)
    - 플랫폼별 해상도 변환 (FFmpeg)
    """

    def __init__(self):
        self._whisper_model = None  # 지연 로딩 (최초 사용 시 로드)
        print("[VideoProcessor] 초기화 완료 (Whisper는 첫 사용 시 로드)")

    @property
    def whisper_model(self):
        """Whisper 모델 지연 로딩"""
        if self._whisper_model is None:
            print(f"[Whisper] 모델 로딩 중... ({WHISPER_MODEL})")
            import whisper
            self._whisper_model = whisper.load_model(WHISPER_MODEL)
            print("[Whisper] 모델 로딩 완료")
        return self._whisper_model

    # ─── 1. 오디오 STT ──────────────────────────────────────────

    def extract_audio_transcript(self, video_path: str) -> dict:
        """
        영상에서 음성을 추출하여 텍스트로 변환 (Whisper 로컬 STT)

        Returns:
            dict: {
                "text": 전체 텍스트,
                "segments": [{"start": float, "end": float, "text": str}, ...]
            }
        """
        print(f"[STT] 음성 분석 시작: {video_path}")
        result = self.whisper_model.transcribe(
            video_path,
            language=WHISPER_LANGUAGE,
            task="transcribe",
        )
        print(f"[STT] 완료. 텍스트 길이: {len(result['text'])}자")
        return {
            "text": result["text"].strip(),
            "segments": [
                {"start": s["start"], "end": s["end"], "text": s["text"].strip()}
                for s in result.get("segments", [])
            ],
        }

    # ─── 2. 자막 오버레이 ────────────────────────────────────────

    def add_subtitle_overlay(self, video_path: str, subtitle_text: str,
                              platform: str, output_path: str = None,
                              subtitle_options: dict = None) -> str:
        """
        MoviePy로 영상 하단에 자막 텍스트 오버레이

        Args:
            video_path: 원본 영상 경로
            subtitle_text: 자막으로 표시할 텍스트
            platform: 플랫폼 (해상도 결정에 사용)
            output_path: 출력 경로 (None이면 자동 생성)
            subtitle_options: 자막 옵션 딕셔너리 (font, color, bg_color, stroke_color, stroke_width, position)

        Returns:
            str: 처리된 영상 파일 경로
        """
        from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip

        if output_path is None:
            stem = Path(video_path).stem
            output_path = str(OUTPUT_DIR / f"{stem}_{platform}_subtitled.mp4")

        print(f"[자막] 오버레이 시작: {video_path}")
        video = VideoFileClip(video_path)

        # 플랫폼별 해상도
        settings = PLATFORM_SETTINGS.get(platform, PLATFORM_SETTINGS["instagram"])
        target_w, target_h = settings["video_resolution"]

        # 영상 리사이즈
        video = video.resize(height=target_h).crop(
            x_center=video.w * (target_h / video.h) / 2,
            width=target_w
        ) if video.w / video.h != target_w / target_h else video.resize((target_w, target_h))

        # 옵션 파싱
        if subtitle_options is None:
            subtitle_options = {}

        font = subtitle_options.get("font", "NanumGothic")
        color = subtitle_options.get("color", "white")
        bg_color = subtitle_options.get("bg_color", "transparent")
        stroke_color = subtitle_options.get("stroke_color", "black")
        stroke_width = subtitle_options.get("stroke_width", 2)
        position = subtitle_options.get("position", ("center", 0.82))

        # 자막 클립 생성
        txt_clip_kwargs = {
            "txt": subtitle_text,
            "fontsize": int(target_w * 0.04),    # 영상 너비의 4%
            "color": color,
            "font": font,
            "method": "caption",
            "size": (int(target_w * 0.9), None),  # 좌우 마진 10%
        }

        if stroke_width > 0:
            txt_clip_kwargs["stroke_color"] = stroke_color
            txt_clip_kwargs["stroke_width"] = stroke_width
            
        if bg_color and bg_color != "transparent":
            txt_clip_kwargs["bg_color"] = bg_color

        txt_clip = (
            TextClip(**txt_clip_kwargs)
            .set_position(position, relative=True)
            .set_duration(video.duration)
        )

        final = CompositeVideoClip([video, txt_clip])
        final.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile="temp_audio.m4a",
            remove_temp=True,
            logger=None,
        )
        final.close()
        video.close()

        print(f"[자막] 완료: {output_path}")
        return output_path

    # ─── 3. BGM 추가 ─────────────────────────────────────────────

    def add_bgm(self, video_path: str, bgm_path: str,
                output_path: str = None, bgm_volume: float = 0.3) -> str:
        """
        BGM을 원본 음성에 믹싱하여 합성

        Args:
            video_path: 영상 파일 경로
            bgm_path: BGM 오디오 파일 경로 (.mp3)
            output_path: 출력 경로
            bgm_volume: BGM 볼륨 (0.0 ~ 1.0, 기본 0.3)

        Returns:
            str: 처리된 영상 파일 경로
        """
        from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip

        if output_path is None:
            stem = Path(video_path).stem
            output_path = str(OUTPUT_DIR / f"{stem}_bgm.mp4")

        print(f"[BGM] 믹싱 시작: {bgm_path} (볼륨: {bgm_volume})")
        video = VideoFileClip(video_path)
        bgm = AudioFileClip(bgm_path).volumex(bgm_volume)

        # BGM을 영상 길이에 맞게 자르거나 루프
        if bgm.duration < video.duration:
            from moviepy.audio.fx.all import audio_loop
            bgm = audio_loop(bgm, duration=video.duration)
        else:
            bgm = bgm.subclip(0, video.duration)

        # 오디오 믹싱
        if video.audio:
            mixed = CompositeAudioClip([video.audio, bgm])
        else:
            mixed = bgm

        final = video.set_audio(mixed)
        final.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile="temp_audio_bgm.m4a",
            remove_temp=True,
            logger=None,
        )
        final.close()
        video.close()

        print(f"[BGM] 완료: {output_path}")
        return output_path

    # ─── 4. 플랫폼별 해상도 변환 ─────────────────────────────────

    def resize_for_platform(self, video_path: str, platform: str,
                             output_path: str = None) -> str:
        """
        플랫폼별 해상도로 영상 변환 (FFmpeg 사용)
        - instagram/tiktok: 1080x1920 (9:16)
        - danggeun/naver_blog: 1080x1080 (1:1)
        """
        import ffmpeg

        settings = PLATFORM_SETTINGS.get(platform, PLATFORM_SETTINGS["instagram"])
        target_w, target_h = settings["video_resolution"]

        if output_path is None:
            stem = Path(video_path).stem
            output_path = str(OUTPUT_DIR / f"{stem}_{platform}_{target_w}x{target_h}.mp4")

        print(f"[리사이즈] {platform}: {target_w}x{target_h}")

        (
            ffmpeg
            .input(video_path)
            .filter("scale", target_w, target_h, force_original_aspect_ratio="decrease")
            .filter("pad", target_w, target_h, "(ow-iw)/2", "(oh-ih)/2", color="black")
            .output(output_path, vcodec="libx264", acodec="aac", strict="experimental")
            .overwrite_output()
            .run(quiet=True)
        )

        print(f"[리사이즈] 완료: {output_path}")
        return output_path

    # ─── 5. 전체 파이프라인 ──────────────────────────────────────

    def process_video(self, video_path: str, subtitle_text: str,
                      platform: str, bgm_path: str = None, subtitle_options: dict = None) -> dict:
        """
        전체 영상 처리 파이프라인 실행

        1. 이미지 업로드 시 동영상 변환 (VideoComposer 연동)
        2. 플랫폼별 해상도 변환
        3. 자막 오버레이
        4. BGM 믹싱 (bgm_path가 있을 때만)

        Returns:
            dict: {
                "output_path": str,
                "transcript": str (STT 결과),
                "steps": [완료된 단계 목록]
            }
        """
        steps = []
        stem = Path(video_path).stem
        current_path = video_path

        try:
            # Step 0: 이미지를 영상으로 변환 (파일 확장자 확인)
            ext = Path(video_path).suffix.lower()
            if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                from core.video_composer import VideoComposer
                composer = VideoComposer()
                current_path = composer.create_video_from_image(video_path, platform)
                stem = Path(current_path).stem
                steps.append("image_to_video")

            # Step 1: 해상도 변환
            resized_path = str(OUTPUT_DIR / f"{stem}_resized.mp4")
            current_path = self.resize_for_platform(current_path, platform, resized_path)
            steps.append("resize")

            # Step 2: 자막 오버레이
            if subtitle_text:
                subtitled_path = str(OUTPUT_DIR / f"{stem}_subtitled.mp4")
                current_path = self.add_subtitle_overlay(
                    current_path, subtitle_text, platform, subtitled_path, subtitle_options
                )
                steps.append("subtitle")

            # Step 3: BGM 믹싱
            if bgm_path and Path(bgm_path).exists():
                final_path = str(OUTPUT_DIR / f"{stem}_final_{platform}.mp4")
                current_path = self.add_bgm(current_path, bgm_path, final_path)
                steps.append("bgm")
            else:
                # BGM 없으면 현재 파일을 final로 복사
                import shutil
                final_path = str(OUTPUT_DIR / f"{stem}_final_{platform}.mp4")
                shutil.copy2(current_path, final_path)
                current_path = final_path

            print(f"[파이프라인] 완료! 단계: {steps}")
            return {
                "output_path": current_path,
                "transcript": subtitle_text,
                "steps": steps,
                "success": True,
            }

        except Exception as e:
            print(f"[파이프라인 오류] {e}")
            return {
                "output_path": None,
                "transcript": subtitle_text,
                "steps": steps,
                "success": False,
                "error": str(e),
            }


if __name__ == "__main__":
    # 빠른 임포트 테스트
    print("[VideoProcessor] 모듈 로딩 성공")
    vp = VideoProcessor()
    print("[VideoProcessor] 인스턴스 생성 성공")
