#!/usr/bin/env python3
"""Build a Savvy Indigo Fox short from a small JSON brief.

The script intentionally has no Python dependencies for rendering. FFmpeg and
FFprobe do the media work. ElevenLabs narration is delegated to the repository's
existing scripts/elevenlabs-tts.py, which reads ELEVENLABS_API_KEY from the
environment, .env, or .archon/.env without printing the secret.

Commands:
  check   Validate tools, paths, and configuration without spending credits.
  voice   Generate narration only.
  render  Assemble existing media and narration without calling an API.
  all     Run check, voice, then render.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("[savvy-fox]", " ".join(cmd[:3]), "..." if len(cmd) > 3 else "")
    subprocess.run(cmd, cwd=cwd or ROOT, check=True)


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def load_brief(path: Path) -> dict:
    if not path.is_file():
        fail(f"brief not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")
    data["_brief_dir"] = str(path.parent.resolve())
    return data


def resolve(value: str, *, base: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def project_dir(brief: dict) -> Path:
    return resolve(brief.get("project_dir", "."), base=ROOT)


def validate(brief: dict, *, require_voice_key: bool) -> None:
    for binary in ("ffmpeg", "ffprobe"):
        if shutil.which(binary) is None:
            fail(f"{binary} is not installed or not on PATH")

    scenes = brief.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        fail("brief.scenes must be a non-empty array")

    project = project_dir(brief)
    for index, scene in enumerate(scenes):
        kind = scene.get("kind")
        if kind not in {"video", "image"}:
            fail(f"scene {index}: kind must be video or image")
        if not scene.get("path"):
            fail(f"scene {index}: path is required")
        media = resolve(scene["path"], base=project)
        if not media.is_file():
            fail(f"scene {index}: media not found: {media}")
        duration = float(scene.get("duration", 0))
        if duration <= 0:
            fail(f"scene {index}: duration must be greater than zero")

    voice = brief.get("voice", {})
    engine = voice.get("engine", "none")
    if engine not in {"none", "elevenlabs"}:
        fail("voice.engine must be none or elevenlabs")
    if engine == "elevenlabs":
        if not voice.get("script"):
            fail("voice.script is required for ElevenLabs")
        if require_voice_key and not os.getenv("ELEVENLABS_API_KEY"):
            # The delegated script can also load .env files. Avoid claiming the
            # key is missing if either conventional secret file exists.
            env_candidates = [ROOT / ".env", ROOT / ".archon" / ".env"]
            if not any(p.is_file() for p in env_candidates):
                fail(
                    "ELEVENLABS_API_KEY is unavailable. Set it in the shell, "
                    ".env, or .archon/.env; never commit that file."
                )

    print(f"[savvy-fox] check passed: {len(scenes)} scenes")


def generate_voice(brief: dict) -> Path | None:
    voice = brief.get("voice", {})
    if voice.get("engine", "none") == "none":
        print("[savvy-fox] voice generation skipped")
        return None

    project = project_dir(brief)
    (project / "audio").mkdir(parents=True, exist_ok=True)
    script_path = project / "script.txt"
    script_path.write_text(voice["script"].strip() + "\n", encoding="utf-8")

    env = os.environ.copy()
    if voice.get("voice_id"):
        env["ELEVENLABS_VOICE_ID"] = voice["voice_id"]
    if voice.get("model_id"):
        env["ELEVENLABS_MODEL_ID"] = voice["model_id"]

    cmd = [sys.executable, str(ROOT / "scripts" / "elevenlabs-tts.py"), str(project)]
    if voice.get("shorts", True):
        cmd.append("--shorts")
    if voice.get("single_call", True):
        cmd.append("--no-chunk")
    print("[savvy-fox] generating ElevenLabs narration")
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)
    narration = project / "audio" / "narration.wav"
    if not narration.is_file() or narration.stat().st_size == 0:
        fail("voice generation completed without narration.wav")
    return narration


def ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(seconds * 100)))
    hours, rem = divmod(centiseconds, 360000)
    minutes, rem = divmod(rem, 6000)
    secs, cs = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def write_captions(brief: dict, output: Path) -> None:
    captions = brief.get("captions", [])
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,DejaVu Sans,68,&H00F7F2FA,&H000000FF,&HCC120B20,&H88000000,-1,0,0,0,100,100,-1,0,1,6,2,2,70,70,250,1
Style: Accent,DejaVu Sans,72,&H005CB8E5,&H000000FF,&HCC120B20,&H88000000,-1,0,0,0,100,100,-1,0,1,6,2,2,70,70,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    rows = []
    for caption in captions:
        text = str(caption["text"]).replace("\n", r"\N").replace(",", r"\,")
        style = "Accent" if caption.get("accent") else "Main"
        rows.append(
            f"Dialogue: 0,{ass_time(float(caption['start']))},"
            f"{ass_time(float(caption['end']))},{style},,0,0,0,,{text}"
        )
    output.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")


def render(brief: dict) -> Path:
    project = project_dir(brief)
    work = project / ".savvy-fox-work"
    segments_dir = work / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    fps = int(brief.get("fps", 30))
    scenes = brief["scenes"]
    segment_paths: list[Path] = []
    for index, scene in enumerate(scenes):
        src = resolve(scene["path"], base=project)
        duration = float(scene["duration"])
        segment = segments_dir / f"{index:03d}.mp4"
        fade = float(scene.get("fade_in", 0.25 if index else 0))
        vf = [
            "scale=1080:1920:force_original_aspect_ratio=increase",
            "crop=1080:1920",
            f"fps={fps}",
        ]
        if scene["kind"] == "image":
            zoom = float(scene.get("zoom", 0.0004))
            vf.append(
                "zoompan="
                f"z='min(zoom+{zoom},1.04)':"
                "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d=1:s=1080x1920:fps={fps}"
            )
        if fade > 0:
            vf.append(f"fade=t=in:st=0:d={fade}")
        cmd = ["ffmpeg", "-y", "-v", "warning"]
        if scene["kind"] == "image":
            cmd.extend(["-framerate", str(fps), "-loop", "1", "-t", str(duration)])
        cmd.extend(["-i", str(src), "-t", str(duration), "-vf", ",".join(vf)])
        cmd.extend([
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(fps), str(segment),
        ])
        run(cmd)
        segment_paths.append(segment)

    concat_file = work / "segments.txt"
    concat_file.write_text(
        "".join(f"file '{p.as_posix()}'\n" for p in segment_paths),
        encoding="utf-8",
    )
    silent_video = work / "silent.mp4"
    run([
        "ffmpeg", "-y", "-v", "warning", "-f", "concat", "-safe", "0",
        "-i", str(concat_file), "-c", "copy", str(silent_video),
    ])

    audio = brief.get("audio", {})
    narration_value = audio.get("narration_path", "audio/narration.wav")
    narration = resolve(narration_value, base=project)
    intro_audio = audio.get("intro_source_audio")
    voice_track = work / "voice.wav"
    if intro_audio:
        intro = resolve(intro_audio, base=project)
        intro_duration = float(audio.get("intro_duration", scenes[0]["duration"]))
        intro_wav = work / "intro.wav"
        run([
            "ffmpeg", "-y", "-v", "warning", "-i", str(intro), "-t",
            str(intro_duration), "-vn", "-ar", "48000", "-ac", "1", str(intro_wav),
        ])
        if not narration.is_file():
            fail(f"narration not found: {narration}")
        run([
            "ffmpeg", "-y", "-v", "warning", "-i", str(intro_wav), "-i",
            str(narration), "-filter_complex",
            "[0:a]aresample=48000[a0];[1:a]aresample=48000[a1];"
            "[a0][a1]concat=n=2:v=0:a=1[a]",
            "-map", "[a]", str(voice_track),
        ])
    else:
        if not narration.is_file():
            fail(f"narration not found: {narration}")
        run([
            "ffmpeg", "-y", "-v", "warning", "-i", str(narration),
            "-ar", "48000", "-ac", "1", str(voice_track),
        ])

    total = probe_duration(voice_track)
    captions_ass = work / "captions.ass"
    write_captions(brief, captions_ass)
    output = resolve(brief.get("output", "out/savvy-fox-short.mp4"), base=project)
    output.parent.mkdir(parents=True, exist_ok=True)

    music_value = audio.get("music_path")
    cmd = ["ffmpeg", "-y", "-v", "warning", "-i", str(silent_video), "-i", str(voice_track)]
    if music_value:
        music = resolve(music_value, base=project)
        cmd.extend(["-stream_loop", "-1", "-i", str(music)])
        volume = float(audio.get("music_volume", 0.10))
        filter_complex = (
            f"[0:v]subtitles={captions_ass.as_posix()}[v];"
            f"[1:a]aresample=48000[voice];[2:a]atrim=duration={total:.3f},"
            f"aresample=48000,volume={volume}[music];"
            "[voice][music]amix=inputs=2:duration=first:dropout_transition=2,"
            "alimiter=limit=0.95[a]"
        )
    else:
        filter_complex = (
            f"[0:v]subtitles={captions_ass.as_posix()}[v];"
            "[1:a]aresample=48000,alimiter=limit=0.95[a]"
        )
    cmd.extend([
        "-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v",
        "high", "-level", "4.1", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(output),
    ])
    run(cmd)
    run(["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"])
    print(f"[savvy-fox] ready: {output} ({probe_duration(output):.2f}s)")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "voice", "render", "all"))
    parser.add_argument("brief", type=Path)
    args = parser.parse_args()

    brief = load_brief(args.brief.resolve())
    validate(brief, require_voice_key=args.command in {"voice", "all"})
    if args.command in {"voice", "all"}:
        generate_voice(brief)
    if args.command in {"render", "all"}:
        render(brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
