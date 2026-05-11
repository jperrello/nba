# Reddit data access — Python paths as of May 2026

Compiled by gullivan2 (librarian role). Sources only, no synthesis. Code blocks are minimal quoted patterns from each source, not invented.

### Sources

1. **Reddit Data API Terms (official)** — https://redditinc.com/policies/data-api-terms
   Reddit Data API requires registration; commercial use requires a contract; on termination users must delete cached User Content. Authoritative TOS.

2. **Reddit API Rate Limits 2026: Complete Guide** — https://painonsocial.com/blog/reddit-api-rate-limits-guide
   Free OAuth tier = 60 req/min (10-min rolling window, per OAuth client, ~86,400/day); unauthenticated = 10 req/min.

3. **Reddit API Pricing in 2026 — Octolens** — https://octolens.com/blog/reddit-api-pricing
   Free tier 100 QPM OAuth / 10 QPM no-OAuth; commercial ≈ $0.24 per 1,000 calls, manual approval (2–4 weeks); historical data requires custom enterprise deal.

4. **How Much Does Reddit API Cost? 2026 Pricing Guide** — https://painonsocial.com/blog/how-much-does-reddit-api-cost
   Enterprise tier "starts at approximately $12,000/yr"; pricing not public, negotiated, extra fees for historical access.

5. **PRAW 7.7.1 — Ratelimits** — https://praw.readthedocs.io/en/stable/getting_started/ratelimits.html
   PRAW reads `X-Ratelimit-` headers, auto-sleeps; configurable `ratelimit_seconds` (default 5s) tolerates up to 600s server-requested waits.
   ```python
   import praw
   reddit = praw.Reddit(client_id="…", client_secret="…", user_agent="app/1.0",
                        username="…", password="…")
   for c in reddit.subreddit("nba").stream.comments():
       print(c.body)
   ```

6. **Async PRAW 7.8.2 — Comment Extraction** — https://asyncpraw.readthedocs.io/en/latest/tutorials/comments.html
   `asyncpraw` mirrors PRAW API but coroutine-based; uses `CommentForest`, `replace_more`, `SubredditStream.comments()` for live streams.

7. **PullPush.io — Reddit API Documentation** — https://pullpush.io/
   Live successor to Pushshift; legacy endpoints `/reddit/search/comment` and `/reddit/search/submission`; built on Watchful1 bittorrent dumps; TOS bound (accessing implies acceptance), no removals of dump-sourced posts. No published rate limit.
   ```python
   import requests
   r = requests.get("https://api.pullpush.io/reddit/search/comment",
                    params={"subreddit":"nba","size":100,"after":"30d"})
   for c in r.json()["data"]: print(c["body"])
   ```

8. **PullPush announcement post** — https://pullpush-io.github.io/
   "Successor and further development of Pushshift" — explicitly framed as 3rd-party service to keep moderation/search tooling alive after the 2023 Pushshift shutdown.

9. **Reddit Archive changelog (ihsoyct.github.io)** — https://ihsoyct.github.io/changelog.html
   As of 2025-04-28: PullPush temporarily disabled while servers updated; Arctic Shift added as alternative backend; both still treated as live mirrors.

10. **Arctic Shift — GitHub (ArthurHeitmann/arctic_shift)** — https://github.com/ArthurHeitmann/arctic_shift
    Reddit mirror project: large dumps + API + web UI at arctic-shift.photon-reddit.com; ships `scripts/processFiles.py` for .zst/.zst_block processing; install via `pip install zstandard`. Posts archived within seconds of creation; upvotes refreshed after ~1.5 days.

11. **Arctic Shift data-collection notes (issue #39)** — https://github.com/ArthurHeitmann/arctic_shift/issues/39
    Owner confirms post-2023 data is collected by Arctic Shift itself (not Pushshift); rescans for vote/score updates ~1.5 days after creation.

12. **BAScraper (maxjo020418)** — https://github.com/maxjo020418/BAScraper
    Async Python wrapper unifying PullPush + Arctic-Shift; explicit recommendation: "For large amounts of data, head to ArcticShift's academic torrent zst dumps"; calls PRAW "honestly useless" for bulk historical pulls.

13. **Watchful1/PushshiftDumps (GitHub)** — https://github.com/Watchful1/PushshiftDumps
    Reference Python scripts for the dump format: `single_file.py`, `iterate_folder.py`, `combine_folder_multiprocess.py`; zstandard ndjson processing patterns.

14. **Academic Torrents — Reddit 2005-06 to 2024-12 (top-40k subreddits)** — https://academictorrents.com/details/1614740ac8c94505e4ecb9d88be8bed7b6afddd4
    Watchful1 dataset, per-subreddit zst ndjson files, torrent client can pull single subreddits; covers Pushshift era through 2024-12.

15. **Academic Torrents — Reddit 2005-06 to 2023-12 (full)** — https://academictorrents.com/details/9c263fc85366c1ef8f5bb9da0203f4c8c8db75f4
    Full historical Pushshift dump set (stuck_in_the_matrix / Watchful1 / RaiderBDev), zstd ndjson, paired with Watchful1 scripts.

16. **Academic Torrents — monthly 2024-08 (RaiderBDev)** — https://academictorrents.com/details/8c2d4b00ce8ff9d45e335bed106fe9046c60adb0
    Confirms ongoing monthly RaiderBDev dumps; related listings show entries up through 2026-02 (~60 GB/month), so dump cadence continues.

17. **Stack Overflow — extract .zst into pandas** — https://stackoverflow.com/questions/61067762/how-to-extract-zst-files-into-a-pandas-dataframe
    Minimal pattern for converting Pushshift zst→json→pandas using `zstandard`; pitfall: `max_output_size` must be large enough for monthly dumps.
    ```python
    import zstandard, json
    with open("RC_2024-08.zst","rb") as f:
        d = zstandard.ZstdDecompressor(max_window_size=2**31).stream_reader(f)
        for line in d.read().decode().splitlines():
            obj = json.loads(line)
    ```

18. **PSAW (legacy Pushshift wrapper)** — https://psaw.readthedocs.io/
    PSAW/PMAW docs still online but BAScraper README notes PushShift "is now only available to reddit admins" — wrappers effectively dead for public use.

19. **r/pushshift — "Reddit comments/submissions 2005-06 to 2025-06"** — https://www.reddit.com/r/pushshift/comments/1mcw9f5/reddit_commentssubmissions_200506_to_202506/
    Active community thread (2026 visible footer) tracking quarterly dump releases; primary discovery channel for new torrent links.

20. **r/DataHoarder — PullPush vs Arctic Shift vs Pushshift Dumps** — https://www.reddit.com/r/DataHoarder/comments/1rlyn3c/pullpush_vs_arctic_shift_vs_pushshift_dumps/
    Community comparison thread (open question on whether PullPush/Arctic-Shift pull straight from dumps vs. live-collect); useful for cross-checking provenance.

21. **Apify vs Bright Data 2026** — https://use-apify.com/docs/apify-vs-the-world/apify-vs-bright-data
    Apify Compute Unit pricing $0.20–$0.30/CU; pre-built Reddit scrapers in Apify Store; Bright Data tiered $1.50/1k records PAYG → $0.79/1k on $1,999/mo plan.

22. **Best Reddit Scraping Tools 2026** — https://www.redditcommentscraper.com/article-best-reddit-scraping-tools.html
    Annual TCO table: PRAW $500–$900 (dev time), Apify $788, Octoparse $900, Bright Data $6,400; PRAW only entry with "Complete API Access".

23. **Reddit licenses data to Google ($60M) and OpenAI** — https://techcrunch.com/2024/05/16/openai-inks-deal-to-train-ai-on-reddit-data/ and https://www.cbsnews.com/news/google-reddit-60-million-deal-ai-training/
    Reddit explicitly monetizes corpus to LLM trainers under bilateral contracts; signals stance that uncontracted training use is disallowed.

24. **TechCrunch — Reddit locks down public data, requires contract** — https://techcrunch.com/2024/05/09/reddit-locks-down-its-public-data-in-new-content-policy-says-use-now-requires-a-contract/
    May 2024 policy change: public data use for AI training now contractually gated; framed as anti-uncompensated-scraping.

25. **FTC investigating Reddit AI data sales** — https://therecord.media/ftc-investigating-reddit-selling-user-data-ai
    FTC inquiry disclosed in S-1; relevant context that user-content-as-training-data is under regulatory scrutiny.

26. **r/MachineLearning — "New Reddit API terms effectively ban training AI"** — https://www.reddit.com/r/MachineLearning/comments/12r7qi7/d_new_reddit_api_terms_effectively_bans_all_use/
    Community read of API terms: training-corpus use of API-pulled data prohibited absent commercial contract; research carve-out unclear.

### Contested / Unclear

- **Provenance of PullPush / Arctic Shift comment-level data after 2023**: PullPush homepage credits Watchful1 bittorrent files (i.e. Pushshift-era dumps); Arctic Shift owner says post-2023 data is freshly collected by Arctic Shift, not Pushshift (issue #39). r/DataHoarder thread explicitly asks the question without resolution.
- **PullPush availability**: Reddit Archive changelog shows PullPush was *temporarily disabled* around 2025-04-28 ("updating their servers"); current uptime in May 2026 not directly confirmed by any source I pulled.
- **Whether torrent-dump corpora may be used for SFT training**: Reddit's 2024 policy + API terms gate *API-derived* training use behind contracts; legal status of LLM training on academic-torrent dumps (Reddit not party) is unaddressed in retrieved sources — the FTC/IPO-era guidance speaks to Reddit's API, not third-party archives.
- **PRAW concrete quota number**: PRAW docs describe header-driven adaptive throttling but do not state a numeric ceiling; secondary sources cite 60 QPM (PainOnSocial) and 100 QPM (Octolens) for the free OAuth tier — sources disagree.

### Couldn't find

- An explicit, on-the-record statement from Arctic Shift/PullPush operators about per-IP or per-API-key rate limits.
- An official Reddit pricing sheet (only third-party reporting of the ~$12k floor / $0.24-per-1k figure).
- A current canonical Python SDK for Arctic Shift's API beyond `BAScraper` (which wraps both PullPush and Arctic Shift).
- Direct legal guidance on SFT-corpus use of academic-torrent Reddit dumps; the retrieved sources only address API-derived data.
