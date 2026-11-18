# AI Interactions Log

This file holds the evidence for two stretch features: **agentic workflow traces** (intermediate reasoning steps saved from real runs) and the **specialization** comparison, with the numbers summarized in [`model_card.md`](model_card.md#5-evaluation-results). The Project 3 log is kept at [`docs/project3_ai_interactions.md`](docs/project3_ai_interactions.md).

---

## Agentic workflow: how one request moves through the agent

`Concierge.run()` is a fixed plan with checks between steps:

1. **guard_input**: refuse empty, oversized or prompt-injection text before any model call.
2. **retrieve**: BM25 over the genre guide, activity guide and song notes.
3. **parse_request**: tool call to the LLM (qwen3:8b) with the retrieved guide snippets and few-shot examples; JSON-schema output. Retried once, then a keyword parser.
4. **validate_profile**: decision point. Normalize, clamp, drop unknowns, merge activity targets, related genres and song-note matches. If nothing usable is left, the agent stops and asks a clarifying question.
5. **rank**: tool call to the Project 3 recommender (`recommend_songs`, diversity on), giving the top 8 candidates with reasons.
6. **compose**: tool call to the LLM, which picks 3–5 candidates with grounded reasons.
7. **verify**: decision point. Five checks; on failure the agent retries compose with the failed check names as feedback, then falls back to a template answer.
8. **confidence** and **done**.

Every step is written to `logs/vibematch.log` and returned in `Result.trace`. `python -m src.vibematch --trace "..."` prints them. The traces below were saved from real runs and are also committed as JSON lines in [`assets/sample_traces.jsonl`](assets/sample_traces.jsonl).

### Trace 1: a full successful run

`llm: 'something with a saxophone for a rainy afternoon' -> ok, confidence 0.88`

Retrieval surfaces Coffee Shop Stories' liner notes first (BM25 9.97). The parser returns `described_sound: "saxophone"`, and the validator fills energy from the rainy-day guide and records the song-note matches. The recommender ranks 8 candidates, the model picks 3 of them with reasons drawn from the notes, and all five verifier checks pass on the first attempt.

```
{"step": "start", "mode": "llm (ollama:qwen3:8b)", "prompt_style": "few-shot", "retrieval": true}
{"step": "guard_input", "blocked": false}
{"step": "retrieve", "hits": [["song_notes", "7. Coffee Shop Stories \u2014 Slow Stereo", 9.97], ["activity_guide", "rainy day", 3.71], ["song_notes", "20. Rainy Day Blues \u2014 Hollow Creek", 3.49], ["genre_guide", "jazz", 2.91], ["genre_guide", "blues", 2.27], ["activity_guide", "heartbreak", 2.17]]}
{"step": "parse_request", "source": "llm", "attempt": 1, "raw": {"is_music_request": true, "genre": null, "mood": "relaxed", "activity": "rainy day", "energy": null, "mood_tags": ["rainy", "cozy"], "exclude_explicit": false, "described_sound": "saxophone"}}
{"step": "validate_profile", "profile": {"mood": "relaxed", "activity": "rainy day", "energy": 0.35, "mood_tags": ["rainy", "cozy"], "note_matches": {"7": "'saxophone, rainy, afternoon'", "20": "'rainy'"}}, "fixes": ["energy 0.35 taken from the 'rainy day' activity guide"]}
{"step": "rank", "candidates": [[7, "Coffee Shop Stories", 3.72], [20, "Rainy Day Blues", 2.71], [4, "Library Rain", 2.5], [18, "Island Time", 2.27], [17, "Paper Boats", 1.92], [2, "Midnight Coding", 1.4], [6, "Spacewalk Thoughts", 1.4], [13, "Moonlit Sonata Redux", 1.3]]}
{"step": "compose", "source": "llm", "attempt": 1, "picks": [[7, "Features a warm saxophone melody, evoking a rainy afternoon in a cafe."], [4, "Gentle lofi with rain sounds and a cozy atmosphere, perfect for a rainy day."], [20, "Includes rain sound effects and a melancholic blues feel, fitting a rainy mood."]], "summary": "Enjoy a cozy, rainy afternoon with smooth saxophone, gentle lofi, and melancholic blues.", "checks": {"ids_from_candidates": true, "three_to_five_unique_picks": true, "explicit_filter_honored": true, "reasons_present": true, "no_other_songs_mentioned": true}}
{"step": "final_checks", "checks": {"ids_from_candidates": true, "three_to_five_unique_picks": true, "explicit_filter_honored": true, "reasons_present": true, "no_other_songs_mentioned": true}}
{"step": "done", "confidence": 0.88, "label": "high"}
```

### Trace 2: a decision to ask instead of answer

`llm: 'play something' -> clarify, confidence 0.0`

Nothing in "play something" retrieves anything or parses into a usable field, so the agent stops at the clarify step. The interactive CLI shows this question and reruns the request with the listener's answer added (human in the loop).

```
{"step": "start", "mode": "llm (ollama:qwen3:8b)", "prompt_style": "few-shot", "retrieval": true}
{"step": "guard_input", "blocked": false}
{"step": "retrieve", "hits": []}
{"step": "parse_request", "source": "llm", "attempt": 1, "raw": {"is_music_request": true, "genre": null, "mood": null, "activity": null, "energy": null, "mood_tags": [], "exclude_explicit": false, "described_sound": null}}
{"step": "validate_profile", "profile": {}, "fixes": []}
{"step": "clarify", "question": "I need a little more to go on. What are you doing while you listen (studying, working out, driving...), or what genre or mood do you want?"}
```

### Trace 3: recovering when the model server is down

`ollama unreachable: 'hype k-pop for the gym' -> ok, confidence 0.64`

The same agent pointed at an Ollama port with nothing listening. Both parse attempts fail (`Connection refused`), so the keyword parser takes over; its raw output (genre "k-pop", mood "hype", activity "gym") is normalized to k-pop with related genres, intense and workout. Both compose attempts fail, the log says why ("llm unavailable on both attempts"), and the template answer is used. The request is still answered and verified, with confidence 0.64 (medium).

```
{"step": "start", "mode": "llm (ollama:qwen3:8b)", "prompt_style": "few-shot", "retrieval": true}
{"step": "guard_input", "blocked": false}
{"step": "retrieve", "hits": [["genre_guide", "k-pop", 5.29], ["song_notes", "5. Gym Hero \u2014 Max Pulse", 4.39], ["activity_guide", "workout", 3.63], ["genre_guide", "j-pop", 1.93], ["genre_guide", "indie pop", 1.87], ["genre_guide", "pop", 1.71]]}
{"step": "parse_request", "source": "llm", "attempt": 1, "error": "Ollama not reachable at http://127.0.0.1:9: <urlopen error [Errno 61] Connection refused>"}
{"step": "parse_request", "source": "llm", "attempt": 2, "error": "Ollama not reachable at http://127.0.0.1:9: <urlopen error [Errno 61] Connection refused>"}
{"step": "parse_request", "source": "rules", "raw": {"is_music_request": true, "genre": "k-pop", "mood": "hype", "activity": "gym", "energy": 0.9, "mood_tags": [], "exclude_explicit": false, "described_sound": null}}
{"step": "validate_profile", "profile": {"genre": "k-pop", "related_genres": ["pop", "edm", "indie pop"], "mood": "intense", "activity": "workout", "energy": 0.9, "mood_tags": ["pumped", "driving", "confident"], "note_matches": {"5": "'gym, pop'"}}, "fixes": ["'k-pop' is not in the catalog; using related genres pop, edm, indie pop", "mood 'hype' normalized to 'intense'"]}
{"step": "rank", "candidates": [[5, "Gym Hero", 5.71], [3, "Storm Runner", 2.98], [12, "Laser Bloom", 2.92], [11, "Concrete Crown", 2.32], [10, "Rooftop Lights", 2.29], [1, "Sunrise City", 1.88], [16, "Iron Verdict", 1.4], [19, "Fuego Lento", 1.35]]}
{"step": "compose", "source": "llm", "attempt": 1, "error": "Ollama not reachable at http://127.0.0.1:9: <urlopen error [Errno 61] Connection refused>"}
{"step": "compose", "source": "llm", "attempt": 2, "error": "Ollama not reachable at http://127.0.0.1:9: <urlopen error [Errno 61] Connection refused>"}
{"step": "compose", "source": "template", "reason": "llm unavailable on both attempts"}
{"step": "compose", "source": "template", "picks": [[5, "Pumped-up workout pop with booming 808 bass, chanted vocals and a countdown drop. Matches: mood match: intense (+1.00); related genre: pop ~ k-pop (+1.00)."], [3, "Fast rock track with distorted twin guitars, pounding live drums and a shouted chorus about outrunning a storm. Matches: mood match: intense (+1.00); energy 0.91 vs target 0.9 (+1.48)."], [12, "Euphoric festival EDM with a soaring synth lead, a long build and a massive drop. Matches: related genre: edm ~ k-pop (+1.00); energy 0.95 vs target 0.9 (+1.43)."], [11, "Confident hip-hop over a hard trap beat with rattling hi-hats; boastful verses about coming up from nothing. Matches: energy 0.78 vs target 0.9 (+1.32); mood tags confident, driving (+1.00)."], [10, "Jangly indie pop with chiming guitars, a bouncy bassline and a carefree chorus about watching city lights from a rooftop. Matches: related genre: indie pop ~ k-pop (+1.00); energy 0.76 vs target 0.9 (+1.29)."]]}
{"step": "final_checks", "checks": {"ids_from_candidates": true, "three_to_five_unique_picks": true, "explicit_filter_honored": true, "reasons_present": true, "no_other_songs_mentioned": true}}
{"step": "done", "confidence": 0.64, "label": "medium"}
```

---

## Specialization: specialized parser prompt vs a bare baseline

The default parser prompt is specialized for this catalog: it lists the allowed moods, activities and mood tags, gives a rule for every field, includes the retrieved guide sections, and adds four worked examples (`FEW_SHOT` in `src/agent.py`) for a study request, a genre-plus-activity request, a described-sound request and an off-topic message. `--zero-shot` removes only the examples; `--bare-prompt` is the baseline, giving just the field names. `python -m src.evaluate` scores every variant field by field on two labeled sets, none of which appear in the examples:

| Prompt | Set A (14 requests, labeled before run 1) | Set B (15 requests, labeled after run 1, before any prompt change was tested) |
|--------|--------------------------------------------|---------------------------------------------------------------------------------|
| few-shot: vocabulary + rules + retrieved guides + 4 examples (default) | 50/56 (89%) | 59/60 (98%) |
| zero-shot: the same without the examples | 52/56 (93%) | 57/60 (95%) |
| bare baseline: field names only | 40/56 (71%) | 41/60 (68%) |
| keyword parser (no LLM) | 51/56 (91%) | 54/60 (90%) |

**What the numbers say.** The specialized prompt measurably changes the model's output compared with the bare baseline (+18 and +30 points), mostly on the activity field and the clean-lyrics flag. Typical bare-baseline outputs from the same model (`assets/eval_report.md`, "Misses"):

- "rainy sunday blues" → genre `pop`, activity `relaxing`, clean `true` (expected blues, rainy day, false)
- "edm bangers for the pregame" → activity `null`, clean `true` (expected party, false)
- "calm music for studying, no explicit lyrics" → genre `study`, which the validator drops as unknown (README sample run)

The four examples themselves are not a reliable improvement: zero-shot wins set A by 4 points, few-shot wins set B by 3. With the examples, the model still marks "some lo-fi to help me focus on homework" as clean-only; without them it doesn't. My guess is the first example, which pairs studying with "no swearing". I kept the examples as the default because they win on the unseen set B; rewriting that first example is the next change I'd test.
