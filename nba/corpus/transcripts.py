from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SOURCES = Path("nba/corpus/sources.yaml")
DEFAULT_OUT = Path("data/corpus/transcripts")
DEFAULT_MODEL = "tiny"  # faster-whisper model size; tiny ≈ 75MB, runs CPU.
CHUNK_MIN_SECONDS = 30.0
CHUNK_MAX_SECONDS = 60.0


@dataclass
class Segment:
    start: float
    end: float
    text: str


def _ytdlp_audio(url: str, out_dir: Path) -> tuple[Path, dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_template = str(out_dir / "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "-x",  # extract audio
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--no-playlist",
        "-o", out_template,
        "--print-json",
        "--no-progress",
        "--quiet",
        url,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        raise RuntimeError(f"yt-dlp failed for {url}: {res.stderr[:500]}")
    info: dict[str, Any] = {}
    for line in res.stdout.strip().splitlines():
        if line.startswith("{"):
            info = json.loads(line)
            break
    vid = info.get("id") or ""
    audio_path = out_dir / f"{vid}.mp3"
    if not audio_path.exists():
        cands = list(out_dir.glob(f"{vid}.*"))
        if cands:
            audio_path = cands[0]
        else:
            raise RuntimeError(f"yt-dlp produced no audio file for {url}")
    return audio_path, info


def _transcribe(audio: Path, model_name: str) -> list[Segment]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(audio), vad_filter=True, beam_size=1)
    out: list[Segment] = []
    for s in segments:
        t = (s.text or "").strip()
        if not t:
            continue
        out.append(Segment(start=float(s.start), end=float(s.end), text=t))
    return out


def _sentence_chunks(segments: list[Segment]) -> list[Segment]:
    # Group whisper segments into 30-60s windows, breaking on sentence-final
    # punctuation when the window is long enough.
    if not segments:
        return []
    chunks: list[Segment] = []
    buf_text: list[str] = []
    buf_start = segments[0].start
    buf_end = segments[0].start

    def flush():
        if buf_text:
            chunks.append(Segment(start=buf_start, end=buf_end, text=" ".join(buf_text).strip()))

    for seg in segments:
        if not buf_text:
            buf_start = seg.start
        buf_text.append(seg.text)
        buf_end = seg.end
        window = buf_end - buf_start
        ends_sentence = bool(re.search(r"[.!?]\s*$", seg.text.strip()))
        if window >= CHUNK_MAX_SECONDS or (window >= CHUNK_MIN_SECONDS and ends_sentence):
            flush()
            buf_text = []
    flush()
    return chunks


def _to_records(
    video_url: str,
    channel: str,
    info: dict[str, Any],
    chunks: list[Segment],
    model_name: str,
) -> list[dict[str, Any]]:
    vid = info.get("id") or ""
    published = info.get("upload_date") or info.get("release_date") or ""
    out: list[dict[str, Any]] = []
    for ch in chunks:
        out.append({
            "source": "yt-dlp+whisper",
            "url": video_url,
            "text": ch.text,
            "metadata": {
                "channel": channel,
                "video_id": vid,
                "published": published,
                "chunk_start_s": round(ch.start, 2),
                "chunk_end_s": round(ch.end, 2),
                "whisper_model": model_name,
            },
        })
    return out


def run(
    sources_file: Path,
    limit: int,
    model_name: str,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load(sources_file.read_text())
    videos = (cfg.get("youtube") or {}).get("videos") or []
    if limit > 0:
        videos = videos[:limit]
    summary: dict[str, Any] = {"videos": [], "output_dir": str(out_dir), "total_lines": 0}
    with tempfile.TemporaryDirectory(prefix="nba-yt-") as tmp:
        tmp_dir = Path(tmp)
        for v in videos:
            url = v.get("url")
            channel = v.get("channel") or "unknown"
            if not url:
                continue
            entry: dict[str, Any] = {"url": url, "channel": channel}
            try:
                audio, info = _ytdlp_audio(url, tmp_dir)
                segments = _transcribe(audio, model_name)
                chunks = _sentence_chunks(segments)
                records = _to_records(url, channel, info, chunks, model_name)
                vid = info.get("id") or url.rsplit("/", 1)[-1]
                path = out_dir / f"{vid}.jsonl"
                with path.open("w", encoding="utf-8") as f:
                    for r in records:
                        f.write(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n")
                entry.update({
                    "video_id": info.get("id"),
                    "segments": len(segments),
                    "chunks_written": len(chunks),
                    "path": str(path),
                })
                summary["total_lines"] += len(chunks)
            except Exception as e:
                entry["error"] = str(e)[:300]
                print(f"[transcripts] {url} failed: {e}", file=sys.stderr)
            summary["videos"].append(entry)
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="nba-7t3 transcripts corpus pipeline (sample run).")
    p.add_argument("--sources-file", default=str(DEFAULT_SOURCES), help="YAML with youtube.videos[].")
    p.add_argument("--limit", type=int, default=0, help="Max videos to process (0 = all in file).")
    p.add_argument("--model", default=DEFAULT_MODEL, help="faster-whisper model name.")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT), help="Output directory.")
    args = p.parse_args(argv)
    summary = run(Path(args.sources_file), args.limit, args.model, Path(args.out_dir))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
