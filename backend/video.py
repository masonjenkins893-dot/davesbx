"""Video processing — scene-aware keyframe extraction + transcript."""
import subprocess
import os
import json
from pathlib import Path
from config import WORKSPACE_DIR, get_workspace_path


class VideoProcessor:
    """Processes videos into keyframes + timestamped transcripts for LLM consumption."""

    def process_video(self, path: str) -> dict:
        video_path = get_workspace_path(path)
        if not video_path.exists():
            return {"error": "Video file not found"}

        # Create output directory alongside the video
        video_stem = video_path.stem
        output_dir = video_path.parent / f"{video_stem}_frames"
        output_dir.mkdir(parents=True, exist_ok=True)

        transcript_path = output_dir / f"{video_stem}_transcript.json"

        # Step 1: Scene-aware keyframe extraction using ffmpeg
        # Detect scene changes and extract those frames
        try:
            # First pass: detect scene changes
            scene_cmd = [
                "ffmpeg", "-i", str(video_path),
                "-filter:v", "select='gt(scene,0.3)',showinfo",
                "-f", "null", "-"
            ]
            result = subprocess.run(scene_cmd, capture_output=True, text=True)

            # Parse scene change timestamps from stderr
            scene_times = []
            for line in result.stderr.split("\n"):
                if "showinfo" in line and "pts_time:" in line:
                    try:
                        pts_str = line.split("pts_time:")[1].split()[0]
                        scene_times.append(float(pts_str))
                    except (IndexError, ValueError):
                        pass

            # If no scene changes detected, sample evenly (1 frame per second)
            if not scene_times:
                # Get video duration
                duration_cmd = [
                    "ffprobe", "-v", "quiet", "-show_entries",
                    "format=duration", "-of", "csv=p=0", str(video_path)
                ]
                dur_result = subprocess.run(duration_cmd, capture_output=True, text=True)
                try:
                    duration = float(dur_result.stdout.strip())
                except:
                    duration = 60  # fallback

                # Sample 1 frame per second (max 30 frames)
                interval = max(1, duration / 30)
                scene_times = [i * interval for i in range(int(duration / interval))]

            # Extract frames at detected scene change times
            frames_list = []
            for i, t in enumerate(scene_times):
                frame_name = f"frame_{i:04d}_{t:.1f}s.png"
                frame_path = output_dir / frame_name
                extract_cmd = [
                    "ffmpeg", "-i", str(video_path),
                    "-ss", str(t),
                    "-frames:v", "1",
                    "-q:v", "2",
                    str(frame_path)
                ]
                subprocess.run(extract_cmd, capture_output=True)
                if frame_path.exists():
                    rel_path = str(frame_path.relative_to(WORKSPACE_DIR.resolve()))
                    frames_list.append({
                        "index": i,
                        "timestamp": t,
                        "path": rel_path
                    })

        except Exception as e:
            return {"error": f"Frame extraction failed: {str(e)}"}

        # Step 2: Extract audio and generate transcript
        transcript = {"segments": [], "full_text": ""}
        try:
            audio_path = output_dir / f"{video_stem}_audio.wav"
            extract_audio_cmd = [
                "ffmpeg", "-i", str(video_path),
                "-vn", "-ac", "1", "-ar", "16000",
                "-f", "wav", str(audio_path)
            ]
            subprocess.run(extract_audio_cmd, capture_output=True)

            if audio_path.exists():
                # Try local speech-to-text (whisper if available)
                try:
                    import whisper
                    model = whisper.load_model("base")
                    result = model.transcribe(str(audio_path))
                    transcript = {
                        "segments": [
                            {
                                "start": seg["start"],
                                "end": seg["end"],
                                "text": seg["text"].strip()
                            }
                            for seg in result["segments"]
                        ],
                        "full_text": result["text"].strip()
                    }
                except ImportError:
                    transcript = {
                        "segments": [],
                        "full_text": "",
                        "note": "Whisper not installed. Run: pip install openai-whisper to enable transcription."
                    }

                # Clean up audio file
                audio_path.unlink()
        except Exception as e:
            transcript = {"segments": [], "full_text": "", "error": str(e)}

        # Save transcript
        with open(transcript_path, "w") as f:
            json.dump(transcript, f, indent=2)

        return {
            "video": path,
            "frames_dir": str(output_dir.relative_to(WORKSPACE_DIR.resolve())),
            "frames_count": len(frames_list),
            "frames": frames_list,
            "transcript_path": str(transcript_path.relative_to(WORKSPACE_DIR.resolve())),
            "transcript": transcript
        }

    def get_frames(self, path: str) -> dict:
        video_path = get_workspace_path(path)
        video_stem = video_path.stem
        output_dir = video_path.parent / f"{video_stem}_frames"

        if not output_dir.exists():
            return {"error": "Video has not been processed yet. Call /video/process/{path} first."}

        frames = []
        for f in sorted(output_dir.glob("frame_*.png")):
            try:
                # Parse timestamp from filename
                name = f.stem  # e.g. frame_0001_12.5s
                parts = name.split("_")
                timestamp = float(parts[-1].rstrip("s")) if len(parts) >= 3 else 0
            except:
                timestamp = 0
            frames.append({
                "path": str(f.relative_to(WORKSPACE_DIR.resolve())),
                "timestamp": timestamp
            })

        return {"frames": frames, "count": len(frames)}

    def get_transcript(self, path: str) -> dict:
        video_path = get_workspace_path(path)
        video_stem = video_path.stem
        output_dir = video_path.parent / f"{video_stem}_frames"
        transcript_path = output_dir / f"{video_stem}_transcript.json"

        if not transcript_path.exists():
            return {"error": "Transcript not found. Process the video first."}

        with open(transcript_path, "r") as f:
            return json.load(f)


video_processor = VideoProcessor()
