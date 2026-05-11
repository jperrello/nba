# SFT corpus — sample pipeline (nba-7t3)

Sample run for Lane D bullet 3 of `OVERSEER_BRIEF.md`. Goal: get Reddit +
analyst-transcript text to disk, count it, and verify the spec hedge (#4) that
the 5–10k LoRA rule of thumb is reachable before slice 3 plans LM training.

**NO LoRA training in this lane** — corpus pipeline only.

## Pipelines

- `nba/corpus/reddit.py` — Reddit pull.
- `nba/corpus/transcripts.py` — YouTube → yt-dlp → faster-whisper transcripts.
- `nba/corpus/sources.yaml` — source list (subreddits, video URLs).

Run as modules:

```bash
python -m nba.corpus.reddit --limit 50 --min-karma 5
python -m nba.corpus.transcripts --model tiny
```

A `nba corpus` CLI subcommand pair is planned but gated on a brutus contract
(per `OVERSEER_BRIEF.md` coordination rules). Routed via athena.

## Reddit

### Access path

Per `docs/reddit_access_2026.md` (gullivan2), three viable Python paths in 2026:

1. **PRAW + OAuth** (60–100 QPM, free tier, requires `REDDIT_CLIENT_ID` +
   `REDDIT_CLIENT_SECRET`).
2. **PullPush.io mirror** — successor to Pushshift, no auth, archival access.
3. **`reddit.com/r/<sub>/.json` unauthenticated** — 10 QPM, last-resort fallback.

The pipeline tries them in that order. This sample run used **PullPush** —
PRAW credentials weren't in the environment and PullPush was alive on
2026-05-11. Gullivan2's doc flags PullPush availability as "not directly
confirmed in May 2026" by the retrieved sources, so re-check at next run; if
it's down, drop in PRAW creds or fall through to the public JSON.

### Sources

Subreddits (per bead `nba-7t3` brief):

- `r/nba` — broad voice, high-volume.
- `r/nbadiscussion` — long-form film/analysis.
- `r/heat` — broad coach voice (Spo/Heat-culture register).
- `r/nyknicks` — primary team for slice 2.
- `r/lakers` — broad voice, big subreddit.

For each subreddit: top 50 submissions by score (PullPush `sort=desc,
sort_type=score`) + top 100 comments per submission.

### Filters

- `min-karma`: default **5**. Posts and comments below this score are dropped.
  Karma is a cheap signal that the content cleared at least minimal community
  bar — important because PullPush archives include deleted/`[removed]` items.
- **URL dedupe**: `seen_url` set keyed on permalink.
- **Body dedupe**: SHA-256 (first 16 hex chars) of the text, second pass.
  Catches cross-posts and quoted-comment chains.
- **Profanity strip**: behind `--strip-profanity` flag (`better_profanity`).
  **Off by default** — corpus is for voice/register learning, and swearing is
  part of NBA Twitter / r/nba voice.

### Output

`data/corpus/reddit/<subreddit>.jsonl` with one record per line:

```json
{"source":"reddit","url":"https://www.reddit.com/...",
 "text":"...",
 "metadata":{"subreddit":"nba","kind":"post"|"comment","score":N,
             "author_hash":"<16hex>","created_utc":N,
             "parent_url":"..." (comments only),"backend":"pullpush"}}
```

Author names are SHA-256-hashed (first 16 hex chars) — Reddit usernames are
public, but the corpus is voice-only and there's no reason to ship raw handles.

## Transcripts (YouTube)

### Pipeline

1. `yt-dlp -x --audio-format mp3 --print-json <url>` → mp3 in a tempdir.
2. `faster_whisper.WhisperModel("tiny", device="cpu", compute_type="int8")`
   with `vad_filter=True` to skip silence and music.
3. Chunk whisper segments into 30–60s windows, breaking on sentence-final
   punctuation when the window passes 30s.
4. Write one JSONL line per chunk to `data/corpus/transcripts/<video_id>.jsonl`.

Tempdir audio is deleted after transcription — we only keep transcript text.

### Sources

`nba/corpus/sources.yaml`. Sample run pulled three Thinking Basketball videos
(brand-safe analyst content). Channel list is configurable; replace / extend
in follow-up runs.

### Output

```json
{"source":"yt-dlp+whisper","url":"https://www.youtube.com/watch?v=...",
 "text":"<chunk text>",
 "metadata":{"channel":"Thinking Basketball","video_id":"<id>",
             "published":"YYYYMMDD","chunk_start_s":F,"chunk_end_s":F,
             "whisper_model":"tiny"}}
```

## Sample run results (2026-05-11)

```
$ wc -l data/corpus/reddit/*.jsonl data/corpus/transcripts/*.jsonl
    2404 data/corpus/reddit/heat.jsonl
    3997 data/corpus/reddit/lakers.jsonl
    4900 data/corpus/reddit/nba.jsonl
    3325 data/corpus/reddit/nbadiscussion.jsonl
    2400 data/corpus/reddit/nyknicks.jsonl
      16 data/corpus/transcripts/k0tn9QRJMec.jsonl
      16 data/corpus/transcripts/lyCYzSrYp-k.jsonl
      23 data/corpus/transcripts/wDViQIwOtY8.jsonl
   17081 total
```

| source | items | lines |
|---|---:|---:|
| Reddit (5 subs × 50 posts, `min_karma=5`) | 250 posts + ~13k comments | 17,026 |
| Transcripts (3 videos, `tiny` whisper) | 3 videos / 457 raw segments | 55 |
| **total** | | **17,081** |

Average yield: ~68 records per Reddit post (post + top-100 comments after
karma + dedupe filtering); 14–20 chunks per ~5–10 min YouTube video.

## Verdict on the 5–10k LoRA rule of thumb

**Reachable.**

A sample-scale run (5 subreddits × 50 posts, 3 short videos) already produced
~17k records on disk — comfortably past the 5–10k threshold the spec hedges
on. At full scale we have at least 2 axes of growth without changing pipeline
shape:

- Reddit: lift the per-sub cap from 50 to a few hundred top posts, add a few
  more team subs / analyst writeup threads — straightforward 5–10× more lines.
- Transcripts: 1 hour of whisper-`tiny` audio → ~100–200 chunks. A modest
  analyst-channel back-catalog (50–100 videos, common for the named
  channels) yields 5k–20k transcript chunks on its own.

For LoRA voice learning, Reddit alone over-clears the threshold; transcripts
are a register-anchoring supplement, not the load-bearing source. The
question that comes next isn't volume — it's *quality* (e.g., should `r/nba`
news headlines be dropped in favor of `r/nbadiscussion`-style long-form, and
how much to weight raw Reddit voice vs. polished analyst voice in the SFT
mix). That sits in slice 3 alongside the actual LoRA training.
