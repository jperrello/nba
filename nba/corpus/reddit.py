from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

DEFAULT_SUBREDDITS = ["nba", "nbadiscussion", "heat", "nyknicks", "lakers"]
DEFAULT_LIMIT = 100
DEFAULT_KARMA = 5
USER_AGENT = "nba-corpus/0.1 (nba-7t3 sample pipeline)"

# Access strategy (per docs/reddit_access_2026.md):
#   1. PRAW with OAuth if REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET in env.
#   2. PullPush.io mirror (https://api.pullpush.io) — successor to Pushshift,
#      no auth, designed for archival access.
#   3. Unauthenticated https://www.reddit.com/r/<sub>/top.json — 10 QPM, works
#      without any setup. Last resort because rate limit is tight.


@dataclass
class Record:
    source: str
    url: str
    text: str
    metadata: dict[str, Any]

    def to_jsonl(self) -> str:
        return json.dumps(
            {"source": self.source, "url": self.url, "text": self.text, "metadata": self.metadata},
            separators=(",", ":"),
            ensure_ascii=False,
        )


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _strip_profanity(text: str) -> str:
    from better_profanity import profanity  # local import — optional dep at call site

    if not profanity.CENSOR_WORDSET:
        profanity.load_censor_words()
    return profanity.censor(text)


def _try_praw():
    cid = os.environ.get("REDDIT_CLIENT_ID")
    sec = os.environ.get("REDDIT_CLIENT_SECRET")
    if not cid or not sec:
        return None
    try:
        import praw  # type: ignore
    except ImportError:
        return None
    return praw.Reddit(
        client_id=cid,
        client_secret=sec,
        user_agent=os.environ.get("REDDIT_USER_AGENT", USER_AGENT),
    )


def fetch_praw(reddit: Any, subreddit: str, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for post in reddit.subreddit(subreddit).top(time_filter="year", limit=limit):
        out.append({
            "id": post.id,
            "permalink": f"https://www.reddit.com{post.permalink}",
            "title": post.title or "",
            "body": post.selftext or "",
            "score": int(post.score or 0),
            "author": str(post.author) if post.author else "[deleted]",
            "created_utc": int(post.created_utc or 0),
            "comments": _praw_comments(post),
        })
    return out


def _praw_comments(post: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        post.comments.replace_more(limit=0)
        for c in post.comments.list():
            body = getattr(c, "body", "") or ""
            if not body or body == "[deleted]":
                continue
            out.append({
                "id": c.id,
                "permalink": f"https://www.reddit.com{c.permalink}",
                "body": body,
                "score": int(getattr(c, "score", 0) or 0),
                "author": str(c.author) if c.author else "[deleted]",
                "created_utc": int(getattr(c, "created_utc", 0) or 0),
            })
    except Exception:
        pass
    return out


def fetch_pullpush(subreddit: str, limit: int, client: httpx.Client) -> list[dict[str, Any]]:
    base = "https://api.pullpush.io/reddit/search"
    posts_r = client.get(
        f"{base}/submission",
        params={"subreddit": subreddit, "size": min(limit, 100), "sort": "desc", "sort_type": "score"},
        timeout=30.0,
    )
    posts_r.raise_for_status()
    posts = posts_r.json().get("data", [])
    out: list[dict[str, Any]] = []
    for p in posts:
        pid = p.get("id")
        if not pid:
            continue
        comments: list[dict[str, Any]] = []
        try:
            c_r = client.get(
                f"{base}/comment",
                params={"link_id": pid, "size": 100, "sort": "desc", "sort_type": "score"},
                timeout=30.0,
            )
            if c_r.status_code == 200:
                for c in c_r.json().get("data", []):
                    body = c.get("body") or ""
                    if not body or body == "[deleted]":
                        continue
                    cperm = c.get("permalink") or f"/r/{subreddit}/comments/{pid}/_/{c.get('id', '')}"
                    if cperm.startswith("/"):
                        cperm = "https://www.reddit.com" + cperm
                    comments.append({
                        "id": c.get("id", ""),
                        "permalink": cperm,
                        "body": body,
                        "score": int(c.get("score", 0) or 0),
                        "author": c.get("author") or "[deleted]",
                        "created_utc": int(c.get("created_utc", 0) or 0),
                    })
        except Exception:
            pass
        perm = p.get("permalink") or f"/r/{subreddit}/comments/{pid}/"
        if perm.startswith("/"):
            perm = "https://www.reddit.com" + perm
        out.append({
            "id": pid,
            "permalink": perm,
            "title": p.get("title") or "",
            "body": p.get("selftext") or "",
            "score": int(p.get("score", 0) or 0),
            "author": p.get("author") or "[deleted]",
            "created_utc": int(p.get("created_utc", 0) or 0),
            "comments": comments,
        })
        time.sleep(0.6)
    return out


def fetch_public(subreddit: str, limit: int, client: httpx.Client) -> list[dict[str, Any]]:
    r = client.get(
        f"https://www.reddit.com/r/{subreddit}/top.json",
        params={"t": "all", "limit": min(limit, 100)},
        headers={"User-Agent": USER_AGENT},
        timeout=30.0,
    )
    r.raise_for_status()
    children = r.json().get("data", {}).get("children", [])
    out: list[dict[str, Any]] = []
    for c in children:
        d = c.get("data", {})
        pid = d.get("id")
        if not pid:
            continue
        comments: list[dict[str, Any]] = []
        try:
            time.sleep(6.5)  # 10 QPM ceiling per gullivan2's doc
            cr = client.get(
                f"https://www.reddit.com/r/{subreddit}/comments/{pid}.json",
                params={"limit": 100, "sort": "top"},
                headers={"User-Agent": USER_AGENT},
                timeout=30.0,
            )
            if cr.status_code == 200:
                data = cr.json()
                if isinstance(data, list) and len(data) >= 2:
                    for child in data[1].get("data", {}).get("children", []):
                        cd = child.get("data", {})
                        body = cd.get("body") or ""
                        if not body or body in ("[deleted]", "[removed]"):
                            continue
                        comments.append({
                            "id": cd.get("id", ""),
                            "permalink": f"https://www.reddit.com{cd.get('permalink', '')}",
                            "body": body,
                            "score": int(cd.get("score", 0) or 0),
                            "author": cd.get("author") or "[deleted]",
                            "created_utc": int(cd.get("created_utc", 0) or 0),
                        })
        except Exception:
            pass
        out.append({
            "id": pid,
            "permalink": f"https://www.reddit.com{d.get('permalink', '')}",
            "title": d.get("title") or "",
            "body": d.get("selftext") or "",
            "score": int(d.get("score", 0) or 0),
            "author": d.get("author") or "[deleted]",
            "created_utc": int(d.get("created_utc", 0) or 0),
            "comments": comments,
        })
        time.sleep(6.5)
    return out


def fetch_subreddit(subreddit: str, limit: int) -> tuple[str, list[dict[str, Any]]]:
    reddit = _try_praw()
    if reddit is not None:
        try:
            return "praw", fetch_praw(reddit, subreddit, limit)
        except Exception as e:
            print(f"[reddit] praw failed for r/{subreddit}: {e}", file=sys.stderr)
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        try:
            data = fetch_pullpush(subreddit, limit, client)
            if data:
                return "pullpush", data
        except Exception as e:
            print(f"[reddit] pullpush failed for r/{subreddit}: {e}", file=sys.stderr)
        try:
            return "reddit-json", fetch_public(subreddit, limit, client)
        except Exception as e:
            print(f"[reddit] public json failed for r/{subreddit}: {e}", file=sys.stderr)
            return "none", []


def to_records(
    subreddit: str,
    backend: str,
    posts: list[dict[str, Any]],
    min_karma: int,
    strip: bool,
) -> list[Record]:
    out: list[Record] = []
    for p in posts:
        body_text = (p["title"] + "\n\n" + p["body"]).strip() if p.get("body") else p["title"]
        if not body_text:
            continue
        if int(p.get("score", 0)) < min_karma:
            continue
        text = _strip_profanity(body_text) if strip else body_text
        out.append(Record(
            source="reddit",
            url=p["permalink"],
            text=text,
            metadata={
                "subreddit": subreddit,
                "kind": "post",
                "score": p["score"],
                "author_hash": _hash(p.get("author") or ""),
                "created_utc": p.get("created_utc", 0),
                "backend": backend,
            },
        ))
        for c in p.get("comments", []):
            if int(c.get("score", 0)) < min_karma:
                continue
            body = c.get("body") or ""
            if not body:
                continue
            ctext = _strip_profanity(body) if strip else body
            out.append(Record(
                source="reddit",
                url=c["permalink"],
                text=ctext,
                metadata={
                    "subreddit": subreddit,
                    "kind": "comment",
                    "score": c["score"],
                    "author_hash": _hash(c.get("author") or ""),
                    "created_utc": c.get("created_utc", 0),
                    "parent_url": p["permalink"],
                    "backend": backend,
                },
            ))
    return out


def dedupe(records: list[Record]) -> list[Record]:
    seen_url: set[str] = set()
    seen_body: set[str] = set()
    out: list[Record] = []
    for r in records:
        if r.url in seen_url:
            continue
        bh = _hash(r.text)
        if bh in seen_body:
            continue
        seen_url.add(r.url)
        seen_body.add(bh)
        out.append(r)
    return out


def run(
    subreddits: list[str],
    limit: int,
    min_karma: int,
    strip_profanity: bool,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"subreddits": {}, "output_dir": str(out_dir), "total_lines": 0}
    for sub in subreddits:
        backend, posts = fetch_subreddit(sub, limit)
        records = to_records(sub, backend, posts, min_karma, strip_profanity)
        records = dedupe(records)
        path = out_dir / f"{sub}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(r.to_jsonl() + "\n")
        summary["subreddits"][sub] = {
            "backend": backend,
            "posts_fetched": len(posts),
            "records_written": len(records),
            "path": str(path),
        }
        summary["total_lines"] += len(records)
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="nba-7t3 Reddit corpus pipeline (sample run).")
    p.add_argument("--subreddit", action="append", help="Subreddit (repeatable). Default: brief list.")
    p.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Posts per subreddit.")
    p.add_argument("--min-karma", type=int, default=DEFAULT_KARMA, help="Minimum score for inclusion.")
    p.add_argument("--strip-profanity", action="store_true", help="Censor profanity via better-profanity.")
    p.add_argument("--out-dir", default="data/corpus/reddit", help="Output directory.")
    args = p.parse_args(argv)
    subs = args.subreddit or DEFAULT_SUBREDDITS
    summary = run(subs, args.limit, args.min_karma, args.strip_profanity, Path(args.out_dir))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
