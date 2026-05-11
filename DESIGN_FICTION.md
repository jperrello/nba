# Design Fiction: The Night the Knicks Beat the 73-Win Warriors

*A speculative scene set roughly twelve months after `nba` v1 ships. All quotes, scores, and "outputs" below are fabricated — this is fiction in service of the spec, not a prediction.*

---

## Scene 1 — 11:47pm, a Tuesday in March

Joey is on the couch. The Knicks lost to the Pacers earlier, and `/r/nba` is doing its nightly post-mortem about whether KAT is the problem. A top comment claims that swapping KAT out for prime Randle would have flipped the season. The next reply says that's crazy because Randle never played with this Brunson. The third reply is just a crying-Jordan face.

Joey opens a terminal. Not because he is going to win the argument — he doesn't post on Reddit — but because for the first time in his life he can actually check.

```
$ nba schema --table lineup_stints --format json | head
```

The schema comes back. He'd forgotten the exact column name for the home-coach mapping. Found it: `coach_home_id`. He keeps going.

```
$ nba sim \
    --team1 'knicks-2026[swap=towns->randle-2021,divincenzo-2024]' \
    --team2 'pacers-2026' \
    --context 'home=knicks,rest=2' \
    --human
```

The Rust gateway hashes the inputs, checks the sim cache, misses, and forwards to the predictor. Thirty-eight milliseconds later the MLP returns a per-possession differential of +3.1 for the counterfactual Knicks. The Hungarian solver decides Randle-2021 should be guarding Siakam (embedding distance: 0.41, flagged as a "size-match, motor-match, switch-risk on the perimeter"). Then the scouting LM wakes up, pulls eleven facts from the curated facts table — Randle's 2020-21 All-NBA Second Team selection, DiVincenzo's 2023-24 corner-three rate, Siakam's post-trade usage with Indiana — and writes a paragraph.

What Joey sees in his terminal:

```
═══════════════════════════════════════════════════════════════
  NYK (alt) 114  —  IND 109     win prob: 0.61 ± 0.08
═══════════════════════════════════════════════════════════════

Key matchups (Hungarian-assigned):
  Brunson      vs  Haliburton    edge: NYK  (+0.7)
  DiVincenzo   vs  Nesmith       edge: NYK  (+0.3)
  Bridges      vs  Mathurin      edge: NYK  (+0.9)
  Anunoby      vs  Siakam        edge: IND  (-0.4) *
  Randle-2021  vs  Turner        edge: NYK  (+0.5)

  * matchup flagged: cross-era assignment, Anunoby on
    primary scorer is high-leverage. See team edges.

Team edges:
  + Knicks rebound rate vs this Indiana frontcourt
  + Cleaner halfcourt fit at the 4 spot (Randle-2021)
  - Lost spacing relative to actual roster (-1.2 pts/100)
  - Defensive switchability worse on Haliburton actions

Scouting take:
  This is the Knicks team Knicks fans keep dreaming
  about, and the model mostly agrees. Randle in his
  2020-21 form gives them a halfcourt hub they don't
  currently have, and DiVincenzo replaces the gravity
  that Towns provides from deep without giving up much
  on the defensive end. The catch is Haliburton. Indiana
  will hunt the switch onto Randle every possession and
  the model knows it — that -0.4 on the Anunoby/Siakam
  line is doing a lot of work to keep this game close.
  Coach factor: small. This is mostly a roster story.

Warnings:
  • Randle-2021 has not played with Brunson in any
    historical stint. Prior is from comparable-archetype
    lineups. (n_effective ≈ 340 possessions)
  • DiVincenzo-2024 minutes with this Brunson exist but
    are small sample (n = 1,041 possessions).
```

Joey reads the scouting paragraph twice. He believes it. Not because the LM is impressive — by now the LM voice is just background, a thing that sounds like an NBA writer because it was trained to — but because the warnings are honest. The model said `n_effective ≈ 340 possessions` and didn't try to hide it. The Reddit thread upstairs has no warnings.

He doesn't post. He goes to bed.

---

## Scene 2 — The Agent Joey Doesn't Know He's Talking To

Three weeks later, Joey is in a group chat. A friend asks: "if you could pick any single season Knicks roster of the last 20 years, who beats the 73-win Warriors?"

Joey doesn't know. But he has wired the `nba` CLI into a small agent loop he built one weekend — a Claude session with a system prompt that says *"you have access to these subcommands, the output is JSON, do not invent player names, if a player isn't found tell the user."* He types the question into the agent.

The agent does what the spec assumed it would do. It calls `nba schema` first. Then `nba sql "SELECT season, COUNT(*) FROM rosters WHERE team_id = 'NYK' GROUP BY season ORDER BY season DESC LIMIT 25"` to see which Knicks seasons even exist. Then it loops, firing off `nba sim` calls one per Knicks roster against the `gsw-2016` team. The Rust gateway is doing what it was built to do: most of these sims have been cached by some other agent on some other night. The agent gets 22 of 25 results from cache.

The three uncached ones run fresh. Six seconds total.

The agent comes back with a ranking. Top of the list: the 2012-13 Knicks, age-34 Carmelo edition. The simulator gives them a 28% win probability against the Warriors. Bottom of the list: the 2014-15 Knicks. The agent quotes the scouting paragraph for the Melo team and notes — correctly, because it read the warnings — that the win probability is wide because no Knicks team in this window faced anything resembling the 2016 Warriors' pace and space, so the model is extrapolating into a regime where stints don't really exist.

Joey pastes the answer into the group chat. His friend says "no way, the Linsanity Knicks were better." His friend is wrong; the simulator says so. But the simulator also says it's not confident. Joey types both halves of that into the chat. Nobody believes him about the second half.

---

## Scene 3 — What Doesn't Happen

It is worth saying what does not happen in this fiction, because the spec was specific about what the system is *not*.

Joey never asks the system who will win tonight's Knicks game. The system has no live mode. Tonight's game is not in any stint table because it has not yet been played. When Joey's friend asks the agent "what's the line on Knicks-Celtics tonight," the agent — because the system prompt told it to be honest about scope — says it can't do that and isn't supposed to.

Joey never opens a web app. The spec said phase 2; phase 2 is still in design. He's been using the CLI for a year. He has opinions about which subcommands should have shorter aliases. He has emailed Joey-the-developer (himself) about it twice.

The scouting LM never invents a stat. This took a year of work that the design fiction is glossing over — the curated facts table needed three rebuilds, the LoRA had to be retrained twice when the corpus filtering rules changed, and the Inspect factuality eval blocked four releases for hallucinating Tim Hardaway Jr.'s three-point percentage by 2 points. The factuality eval is, at this point, the most important thing in CI. When it fails the deploy doesn't go out, and nobody overrides it, because once you let a model say a fake number out loud in a confident voice the whole thing is over.

Nobody bets on a sim. There is no betting integration. The thought has come up. The answer has been no.

---

## Scene 4 — The Cross-Era Sim, A Year Later

Joey is at his parents' house. His dad, who has been watching basketball since Walt Frazier, asks: "you ever run the '70 Knicks against the current team?"

Joey opens the laptop.

```
$ nba sim --team1 'knicks-1970' --team2 'knicks-2026'
```

The CLI returns an `EraOutOfRangeError`. The 1970 Knicks aren't in the data — ESPN's public API didn't go back that far when the system was built, and the P0 validation a year ago set the training window at 2003 onward. The error message says exactly that. It also suggests, because the spec said errors should be agent-legible and helpful, the earliest available Knicks season: 2002-03.

Joey runs that one instead. The 2002-03 Knicks lose to the 2026 Knicks by 19. The scouting LM writes a paragraph about pace and floor spacing and Allan Houston's knees. Joey's dad says "yeah, that sounds about right," which is, in the end, all the validation an NBA simulator ever really gets.

---

## Coda — The Things The Spec Got Right And The Things It Didn't

**Got right:**
- JSON-by-default. Once the agent loop existed, the human-mode flag became a debugging tool, not the main path.
- Separating voice from facts. The LM never had to know a stat to sound like it knew a stat. The factuality eval caught the few times it tried.
- Stint-level training. The 5v5-tuple problem would have killed it. Stints made it tractable.
- Per-season player embeddings. The 2016-Curry-vs-2026-Curry sim is the single most-run query in the cache. Nobody predicted that. Everyone should have.

**Got wrong, or at least got expensive:**
- The facts table needed its own team. The spec said "likely needs its own sub-design before implementation." It needed three.
- The local GPU assumption held for development but the LoRA-on-spot story was less smooth than advertised; preemptions during FSDP runs cost roughly a week of wall-clock time across the first six months.
- Coach-as-categorical was fine for v1 but the residuals did, in fact, show coach-shaped variance, and the v2 promotion to coach embeddings is currently the biggest open ticket. The spec predicted this exactly. It did not predict that the team would put it off for nine months because the data-app users didn't care.
- "Knicks-first showcase, league-wide training" worked for the demos and broke for everything else. By month four, anchor scenarios were a liability — every new feature got tested against the Knicks first and the rest of the league second. Coverage gaps for non-Eastern-Conference small-market teams were embarrassing for two full quarters.

**Did not appear in the spec but turned out to matter:**
- The sim cache became a social object. People shared cache keys instead of screenshots. "Run sim `a4f9c2…` and look at the matchup line" became a thing in the group chat. The spec treated the cache as an infrastructure detail. It was a feature.
- Warnings were the most important text in the output. People trusted the system because of how it described its own uncertainty, not because of how confident the numbers looked.
- The agent loop, written by hand per the spec's exclusion of LangChain/LlamaIndex, was 180 lines of Python at the start of year one. It was 180 lines of Python at the end of year one. This was the right call and nobody bragged about it because nobody noticed.
