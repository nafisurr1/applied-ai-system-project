# AI Interactions Log

> **Stretch features only.** This log covers the two stretch features that ask for one: the advanced song attributes (SF8) and the scoring-mode design pattern (SF10). The diversity penalty is documented in `model_card.md`, and the results table in `README.md`.

---

## Agentic Workflow (SF8)

**What task did you give the agent?**

Add five or more meaningful attributes that the starter catalog doesn't have, fill them in for all 20 songs, and update the scoring so the new attributes actually change recommendations, without changing the results for profiles that don't use them.

**Prompts used:**

- "Add five new attributes to every song in `data/songs.csv`: popularity (0–100), release decade, two or three detailed mood tags (like nostalgic, aggressive, euphoric), instrumentalness (0–1) and an explicit flag. Keep the existing columns and values exactly as they are."
- "Update `load_songs` so the new columns come back as the right types (ints, a float, a list of tags, a bool), and update `score_song` so a profile can target popularity, decade and instrumentalness by closeness, earn points for shared mood tags, and penalize explicit songs only when it asks for clean lyrics. Every new rule has to add a reason with its points."
- "Show that profiles that don't use the new preferences get exactly the same output as before."

**What did the agent generate or change?**

- `data/songs.csv`: 5 new columns for all 20 rows: `popularity`, `release_decade`, `mood_tags` (semicolon-separated), `instrumentalness`, `explicit` (0/1). The 10 original columns were left byte-for-byte unchanged.
- `src/recommender.py`:
  - added the new fields to `INT_FIELDS` / `FLOAT_FIELDS`, and parsing for `mood_tags` (split on `;`) and `explicit` (to `bool`) in `load_songs()`
  - added weights (`popularity`, `release_decade`, `instrumentalness` 0.5 each; `mood_tags` 0.5 per tag; `explicit` −3.0) and closeness scales (popularity 100, decade 50 years)
  - added the mood-tag and explicit rules to `score_song()`
  - gave the new `Song` dataclass fields defaults, so the starter tests that build `Song` with only the original 10 fields still pass
- `src/main.py`: two profiles that use the new attributes, "Nostalgic Road Trip" (decade 1990, three mood tags, clean lyrics) and "Edge case: clean workout".
- Commands run: the CLI before and after (outputs diffed), and `python -m pytest`.

**What did you verify or fix manually?**

- **No regressions:** I diffed the full `python -m src.main` output for the original six profiles before and after the change, and it was identical, so the new attributes only matter when a profile asks for them.
- **Scores by hand:** for a clean-lyrics pop profile, Gym Hero lost exactly 3.00 points with an "explicit lyrics (−3.00)" reason, and Sunrise City gained +0.50 per shared mood tag. Both are now pinned down by `test_explicit_penalty_only_when_profile_asks_for_clean_lyrics` and `test_mood_tags_score_per_shared_tag`.
- **A behavior I didn't expect:** the explicit rule is a penalty, not a filter, so in the "clean workout" profile Gym Hero still lands at #3. I kept it as a penalty for now (it's documented as a limitation and as the first future-work item in the model card), because a hard filter is a separate design decision.
- **A test that couldn't fail:** after planting a bug that counts mood tags once instead of per tag, I confirmed `test_mood_tags_score_per_shared_tag` fails, so that rule is really covered.

---

## Design Pattern (SF10)

**Which design pattern did you use?**

**Strategy.** Each scoring mode is a strategy object (`ScoringMode`) that the scoring function asks for weights. The caller picks the strategy at runtime (`--mode` in `main.py`, `mode=` in `recommend_songs()` and `Recommender`).

**How did AI help you brainstorm or implement it?**

I asked the assistant for ways to support "genre-first", "mood-first" and "energy-focused" rankings without copying the scoring function. It laid out three options:

1. **A class per strategy** (`GenreFirstScorer`, `MoodFirstScorer`, …) each with its own `score()` method. This is the textbook Strategy shape.
2. **Strategy objects that only carry weight overrides**, with one shared scoring algorithm that reads its weights from whichever strategy is active.
3. **An `if mode == ...` chain** inside `score_song()`.

I chose option 2. The modes differ only in how much each signal is worth, not in how scoring works, so option 1 would repeat the same loop four times, and option 3 grows a new branch for every mode and mixes "what the weights are" into "how scoring works". With option 2, adding a mode is one line in `MODES`, and the experiment runner can create a one-off strategy (the "no mood" feature-removal experiment is `ScoringMode("no-mood", ..., {"mood": 0.0})`) without touching `recommender.py`. The assistant also suggested prototyping the second mode on an `experiment/mood-first` branch. I built it on `main` instead, because the existing tests plus a diff of the balanced output showed the default behavior didn't change.

**How does the pattern appear in your final code?**

- `ScoringMode` (frozen dataclass: `name`, `description`, `overrides`, and a `weight(feature)` method that falls back to the default `WEIGHTS`) and the `MODES` dictionary in `src/recommender.py`.
- `score_song(user_prefs, song, mode)` calls `get_mode(mode).weight` for every rule, so the same code serves all four modes.
- `src/main.py` exposes the choice as `--mode {balanced,genre-first,mood-first,energy-focused}`. `src/experiments.py` uses `MODES["energy-focused"]` for the weight-shift experiment and its own `ScoringMode` for the mood-removal experiment.
- `test_energy_focused_mode_lifts_happy_indie_pop_over_intense_pop` and the parametrized `test_explanation_points_add_up_to_the_score` cover all four strategies.
