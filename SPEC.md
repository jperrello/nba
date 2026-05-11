NBA Lineup Simulator — Spec (v2)

Working definition

A backend system for NBA lineup analytics with two modes, exposed via an agent-facing Python CLI (one-shot commands, JSON by
default), with a TypeScript/React web frontend deferred to phase 2.

- Data-app mode: queries real historical lineup and player performance from ESPN data (via pseudo-r/Public-ESPN-API). Pre-canned
subcommands + nba sql escape hatch + nba schema for agent self-discovery.
- Simulation mode: users construct counterfactual matchups — swap players in/out of historical rosters, or build full rosters
across eras. Output is structured (score, win prob, who-guards-who, matchup strength, team edges) plus a narrative scouting take
from a fine-tuned LM. Inspiration: NBA 2K MyTeam with real data and a real ML pipeline.

Knicks-first showcase, league-wide training. Anchor scenarios:
- Multi-player roster swap: "2025 Knicks with DDV+Randle instead of KAT vs. Pacers"
- Cross-era full-roster matchup: "2026 Knicks vs. 2016 Warriors"

Not: betting tool, fantasy basketball, real-time/live system, free-form chatbot, single-game predictor, web app in v1.

Who uses it and how

Phase 1: Joey via agent-facing CLI. One-shot commands, JSON by default, an LLM composes/parses. Flow:
1. nba schema → see Postgres schema.
2. nba lineup stats --players ... or nba sql "..." for data queries.
3. nba sim --team1 'knicks-2024[swap=kat->randle,divincenzo]' --team2 'pacers-2024' for sims.
4. Output: score, matchups (Hungarian-assigned), team edges, scouting narrative. Warnings as structured fields.

Phase 2: humans via TS/React web on the same backend.

Core features

- Data ingestion: nightly batch pulls ESPN PBP, box scores, rosters, coach-game mappings via pseudo-r/Public-ESPN-API into
Postgres.
- SFT corpus ingestion: two pipelines — Reddit (r/nba breakdowns + high-karma comments) and analyst audio (yt-dlp + Whisper).
Quality-filtered, merged. Corpus is for voice/register learning, not facts.
- Curated facts table (new): structured Postgres table holding ground-truth player/lineup/coach facts (career stats, season
averages, notable performances, awards, role descriptors). Source: derived from ingested ESPN data + manual seed for descriptors.
This is what the scouting LM retrieves at inference time so it doesn't have to remember anything.
- Player embedding model: PyTorch from scratch. One vector per (player, season). Trained on z-score-normalized stats + era token.
Stored in pgvector.
- Predictor (concretely specified):
  - Training target: per-possession point differential from PBP-derived lineup stints (home pts − away pts per possession on the
floor).
  - Inputs: home lineup feature vector (concat of sum + mean of player embeddings), away lineup feature vector, context features
(era token, home/away, coach as categorical, days-rest if available).
  - Architecture: small MLP, ~5-50M params.
  - Sample-size handling: trains at the stint level (~millions of stints across post-2002 history), not at sparse 5v5-tuple level.
 Bayesian shrinkage toward player-level priors (RAPM-style regularization) for rare lineup matchups.
- Matchup module: Hungarian assignment on player embeddings for who-guards-who; embedding distance for matchup strength.
- Scouting LM: small open-weight model (~7-8B), LoRA-fine-tuned on the SFT corpus for voice/register only. Served via vLLM. At
inference: takes structured predictor output + retrieved facts from the curated facts table → narrative paragraph.
- CLI surface: pre-canned subcommands + nba sql "..." escape hatch + nba schema.
- Sim result cache: Postgres table keyed by (lineup1_hash, lineup2_hash, context_hash, model_versions). Rust gateway checks before
 forwarding.
- Eval harness: Inspect runs predictor accuracy on held-out historical matchups + coherence/style checks on scouting LM output +
factuality checks against the facts table.

Rules and edge cases

- Era handling: z-score normalize stats per season per league AND pass era token. Embeddings, predictor, and LM-context all see
era.
- Player granularity: one embedding per (player, season). 2016 Curry vs. 2026 Curry is first-class.
- Sparse data: best-effort + structured warning. Threshold: [decide at implementation, ~<200 minutes/season].
- Mid-season trades: merge player stats across teams within a season into one (player, season) embedding. Coach-game mappings
remain per-game.
- Pre-2002 data: use whatever ESPN exposes. Coverage [guess: thin/absent pre-2002]. Fail gracefully if year has no data. Training
window depends on the P0 validation result (see Decisions to double-check).
- Coach handling (v1): categorical feature in the predictor, not an embedding. v2 promotes to embedding only if predictor
residuals show systematic unexplained variance by coach.
- Facts retrieval failure: if a fact lookup misses (player not in facts table), the LM prompt notes the gap explicitly so the
model says "limited data" rather than confabulating.
- Sim cache invalidation: keyed by model versions. Retraining bumps version field.
- Swap mechanic: roster-level swap is primary. Model takes resulting lineup as input; embeddings already encode the new players,
no special imputation at sim time.

Look and feel

CLI: structured JSON by default; --human flag pretty-prints + includes scouting narrative. Warnings as structured array in JSON,
"Warnings:" section in human mode. Errors typed (InvalidPlayerError, InsufficientDataError, EraOutOfRangeError) for agent
legibility.

Phase 2 web: TBD; NBA 2K team-building as inspiration.

Resolved decisions

CLI shape

Choice: one-shot, agent-facing, JSON-by-default.
Why: user explicitly framed CLI as a test harness for an LLM, humans coming via web. Stateless commands are agent-friendliest and
translate cleanly to web.

Simulation output shape

Choice: score + tactical breakdown (no possession-by-possession sim).
Why: hybrid that gives the scouting LM structured input without the infra burn of an event-level autoregressive model.

Cross-era handling

Choice: both — z-score normalize AND pass era token.
Why: era token preserves era info for the scouting LM even after stats are normalized.

Matchup logic

Choice: embedding-similarity (Hungarian + distance).
Why: makes the player-embedding model load-bearing across matchups, swaps, and similar-player lookups.

LM architecture (revised)

Choice: fine-tune for voice/register only, retrieve facts from a curated facts table at inference.
Why: the r/nba + analyst corpus is noisy on facts but fine for voice. Separating "how to write" from "what to write about" fixes
the hallucination risk while preserving the Tier-2 SFT training story. Stats and player facts come from a structured table, not
the model's parameters.

Predictor architecture (newly specified)

Choice: small MLP trained on per-possession point differential at the stint level, with RAPM-style Bayesian shrinkage for rare
matchups.
Why: training at the stint level dodges the 5v5-tuple sample-size collapse (millions of stints vs. sparse tuples). Shrinkage
toward player-level priors handles tail matchups. Per-possession target is what PBP data natively produces.

Coach modeling (revised — cut from v1)

Choice: coach as categorical feature in the predictor for v1; coach embeddings deferred to v2.
Why: team-level patterns under a coach are confounded by roster — you'd be learning "this coach had good players." v2 promotes to
embedding only if predictor residuals show systematic coaching variance unexplained by roster.

SFT corpus source

Choice: hybrid r/nba + analyst transcripts.
Why: user rejected LM-generated training data and scraped pro writing. Hybrid gives volume + register-anchoring. Acceptable for
voice learning even though noisy on facts (facts come from retrieval).

Training compute

Choice: local dev + AWS for real runs.
Why: matches how real ML teams work, FSDP load-bearing on multi-GPU AWS runs, dev loop fast.

Data-app mode shape

Choice: pre-canned subcommands + SQL escape hatch.
Why: typed schemas for common queries (agent-friendly); SQL for long tail.

Player granularity

Choice: one embedding per (player, season).
Why: captures evolution, makes cross-era same-player sims first-class.

Sparse data handling

Choice: best-effort + structured warning.
Why: doesn't block exploration, gives agent/UI the data to decide whether to trust.

Technical constraints

- Stack:
  - Languages: Python (primary), Rust (inference gateway), SQL (Postgres)
  - ML: PyTorch + HuggingFace Transformers + PEFT (LoRA/QLoRA); FSDP via torchrun for multi-GPU LM fine-tunes
  - Base model for SFT: 7-8B open-weight class; choice (Llama 3 8B / Qwen 2.5 7B / Mistral 7B / Phi-3) decided at implementation
time via Inspect benchmark
  - Evals: Inspect + LLM-as-judge for coherence + facts-table-grounded factuality checks
  - Cloud: AWS — EKS, S3 (artifacts + Terraform state), IAM, ECR, RDS Postgres + pgvector
  - IaC: Terraform; state in S3
  - MLOps: MLflow self-hosted on EKS (tracking + registry)
  - Serving: vLLM behind Rust/axum gateway (auth, rate limit, OTel, sim cache lookup, facts retrieval, streaming)
  - Observability: OpenTelemetry, Prometheus, Grafana
  - CI: GitHub Actions
- Dev environment: local for code/data iteration; LM LoRA on AWS EC2 g5/p4 spot. Assumes local GPU (see Decisions to
double-check).
- Data source: pseudo-r/Public-ESPN-API. Reddit API. yt-dlp + Whisper.
- Phase boundary: phase 1 = both CLI modes working against trained models deployed to EKS with Inspect evals in CI. Phase 2 =
React/TS web frontend.

Out of scope

- Live/upcoming game predictions (no live polling)
- Recommending lineup changes
- Free-form chatbot interface
- Web frontend in phase 1
- Betting integration
- Fantasy basketball
- Authentication, multi-user, shareable sim URLs
- Player tracking data (not in ESPN's public API)
- Pre-2002 historical data unless ESPN's API surprises us
- Coach embeddings in v1 (deferred to v2)
- TensorFlow / JAX (PyTorch only)
- LangChain / LlamaIndex (agent loop written by hand)

Decisions to double-check

1. P0 prereq — ESPN API coverage: before any infra work, pull lineup data for 2003, 2008, 2013, 2018, 2023 via
pseudo-r/Public-ESPN-API and confirm PBP-derived stints can be reconstructed. Concrete deliverable: a one-pager noting which
seasons have full PBP, which have boxscore-only, and which are missing. If pre-2010 is thin, the training-data window starts at
2010 and the cross-era pitch shifts to "2010s-2020s only" before committing to anything else.
2. Local GPU assumption: "local dev + AWS for real runs" assumes a local GPU with ~24GB+ VRAM for LoRA on a 7-8B model. If not,
the dev loop shifts — verify before infra.
3. Base model for SFT: decided by Inspect benchmark on a representative scouting prompt set at implementation time.
4. SFT corpus size: ~5-10k examples is the rule of thumb for LoRA voice learning; if analyst transcripts yield significantly less,
 r/nba volume has to carry. Verify corpus size early.
5. Facts table coverage: the curated facts table is new — needs explicit decisions on schema, manual-vs-derived split, and update
cadence. Likely needs its own sub-design before implementation.
