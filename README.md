# 🎵 Music Recommender Simulation: VibeMatch 1.0

## Project Summary

VibeMatch is a small **content-based** music recommender. It loads a 20-song catalog from `data/songs.csv`, compares every song to a listener's taste profile (favorite genre and mood, target energy, and optional extras like acousticness, decade, mood tags and a clean-lyrics flag), and returns the top 5 songs. Each song comes with a score and a list of reasons that add up to that score. It supports four switchable scoring strategies and an optional diversity penalty, and prints results as a table in the terminal. The goal is to show how recommenders turn data into rankings, and where a simple scoring rule is fooled. Those findings are written up in the [**Model Card**](model_card.md).

---

## How The System Works

### How real recommenders work

Spotify, YouTube and TikTok mix two families of methods. **Collaborative filtering** learns from behavior across many users: if people who play, save and replay song A also tend to play song B, then B gets recommended to someone who likes A, even if the two songs sound nothing alike. Its inputs are interaction signals: plays, skips (especially in the first 30 seconds), likes, saves, repeat listens, playlist adds and follows. **Content-based filtering** looks at the songs themselves: audio features such as tempo, energy, valence (how positive it sounds), danceability and acousticness, plus metadata like genre, mood tags, release year and lyrics. It recommends songs that are close to what a user already likes. Real systems combine both. Content features handle brand-new songs and users with no history (the "cold start" problem), collaborative signals capture taste that audio features miss, and a ranking stage orders a few hundred candidates using context such as time of day.

There are three separate pieces in any of these systems:

- **Input data**: what we know about each song (its features).
- **User preferences**: what we know about the listener (a taste profile, or their history).
- **Ranking**: the rule that turns the two into an ordered list.

### What this simulation does

This project is a small **content-based** recommender. There are no other users, so there is no collaborative filtering. It compares one user's taste profile against every song in `data/songs.csv`, gives each song a score with written reasons, and returns the top *k*.

**`Song` features used:** `genre`, `mood`, `energy`, `tempo_bpm`, `valence`, `danceability`, `acousticness` (from the starter), plus `popularity`, `release_decade`, `mood_tags`, `instrumentalness` and `explicit` (added in the advanced-features stretch).

**`UserProfile` / preference dictionary:** `genre` and `mood` (favorites), `energy` (target 0.0–1.0), `likes_acoustic` (True or False). Optional extras are `valence`, `tempo_bpm`, `danceability`, `popularity`, `release_decade`, `instrumentalness`, `mood_tags` (a list) and `allow_explicit`. Any preference a profile leaves out is simply not scored.

### Algorithm recipe

**Scoring rule (one song):**

| Signal | Points (balanced mode) |
|--------|------------------------|
| Genre matches the favorite genre | +2.0 |
| Mood matches the favorite mood | +1.0 |
| Energy closeness | up to +1.5, computed as `1.5 × (1 − abs(song.energy − target))` |
| Acousticness closeness (target 0.8 if `likes_acoustic`, else 0.2) | up to +0.5 |
| Any other numeric target the profile sets (valence, tempo, danceability, popularity, decade, instrumentalness) | up to +0.5 each, same closeness formula; tempo is scaled by 100 BPM, popularity by 100, decade by 50 years |
| Each matching mood tag | +0.5 |
| Explicit song when the profile has `allow_explicit: False` | −3.0 |

Closeness rewards songs that are **near** the target rather than just higher or lower. A user asking for energy 0.4 gets the most points from a 0.4 song, not from the loudest one. Genre counts double a mood match because it is the strongest single signal of whether a listener will even consider a song. Mood still adds a full point so it can break ties inside a genre.

**Ranking rule (the whole list):** score every song with the scoring rule, sort from highest to lowest (ties broken by song id so results repeat exactly), and return the top *k* with their reasons. Both rules are needed. The scoring rule only judges one song in isolation; the ranking rule is what turns many judgments into a recommendation, and it is where list-level rules such as the diversity penalty live.

**Data flow:** user preferences → loop over every song in the CSV and score it → sort → top *k* with explanations.

### Scoring modes (Strategy pattern)

`ScoringMode` in `src/recommender.py` holds a set of weight overrides, and `score_song()` reads every weight from the active mode, so the scoring algorithm never changes; only the strategy does. Pick one with `--mode`:

| Mode | Weights changed from balanced | Use it when |
|------|-------------------------------|-------------|
| `balanced` (default) | none | the recipe above |
| `genre-first` | genre 4.0, mood 0.5, energy 1.0 | you want to stay inside your genre |
| `mood-first` | genre 1.0, mood 3.0, mood tags 1.0 each | the feeling matters more than the label |
| `energy-focused` | genre 1.0, energy 3.0 | the Phase 4 weight-shift experiment (energy ×2, genre ×½) |

### Diversity penalty

With `--diverse`, `recommend_songs()` builds the top *k* greedily. Each time it picks the next song, it subtracts **1.0** for every song by the same artist already in the list and **0.5** for every song in the same genre (`diversity_penalty()`, `rerank_for_diversity()`). The penalty appears in the reasons, so the printed score always equals the listed points.

### Biases I expect before building

- Genre is worth the most points, so the system will probably over-prioritize genre and bury great songs that match the user's mood and energy but carry a different label. For example, "indie pop" is not an exact match for "pop".
- With 1–3 songs per genre, fans of small genres (metal, classical) will see the same one song on top every time and then unrelated filler.
- Energy closeness works the same at both ends of the scale, but the catalog has more mid- and high-energy songs, so low-energy listeners have fewer close options.

---

## Getting Started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Mac or Linux
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### Run it

All commands run from the project root.

| What | Command |
|------|---------|
| All 8 test profiles, balanced mode | `python -m src.main` |
| One profile | `python -m src.main --profile "Chill Lofi"` |
| Another scoring strategy | `python -m src.main --mode mood-first` (also `genre-first`, `energy-focused`) |
| With the diversity penalty | `python -m src.main --diverse` |
| More or fewer results | `python -m src.main --k 3` |
| Weight experiments side by side | `python -m src.experiments` |
| Tests | `python -m pytest` |

The starter `src/main.py` imported `recommender` directly, which fails with `ModuleNotFoundError` under `python -m src.main`. It now imports `src.recommender`, and `pytest.ini` puts the project root on the path so plain `pytest` works too.

---

## Sample Recommendation Output

Default "pop / happy" profile (`python -m src.main --profile "Starter: pop / happy"`):

```
Loaded songs: 20

=== Starter: pop / happy ===
Profile: genre=pop, mood=happy, energy=0.8
Mode: balanced (default recipe: genre 2.0, mood 1.0, energy up to 1.5)
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| #  | Song                               | Genre / mood         | Score | Why                                                        |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 1  | Sunrise City — Neon Echo           | pop / happy          | 4.47  | genre match: pop (+2.00)                                   |
|    |                                    |                      |       | mood match: happy (+1.00)                                  |
|    |                                    |                      |       | energy 0.82 vs target 0.8 (+1.47)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 2  | Gym Hero — Max Pulse               | pop / intense        | 3.30  | genre match: pop (+2.00)                                   |
|    |                                    |                      |       | energy 0.93 vs target 0.8 (+1.30)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 3  | Rooftop Lights — Indigo Parade     | indie pop / happy    | 2.44  | mood match: happy (+1.00)                                  |
|    |                                    |                      |       | energy 0.76 vs target 0.8 (+1.44)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 4  | Fuego Lento — La Marea             | latin / playful      | 1.50  | energy 0.8 vs target 0.8 (+1.50)                           |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 5  | Concrete Crown — Kilo Verse        | hip-hop / confident  | 1.47  | energy 0.78 vs target 0.8 (+1.47)                          |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
```

Same idea with the diversity penalty on, for Chill Lofi (`python -m src.main --profile "Chill Lofi" --diverse`). The second LoRoom song drops from #3 to #5:

```
Loaded songs: 20

=== Chill Lofi ===
Profile: genre=lofi, mood=chill, energy=0.35, likes_acoustic=True
Mode: balanced (default recipe: genre 2.0, mood 1.0, energy up to 1.5) + diversity penalty
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| #  | Song                               | Genre / mood         | Score | Why                                                        |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 1  | Library Rain — Paper Lanterns      | lofi / chill         | 4.97  | genre match: lofi (+2.00)                                  |
|    |                                    |                      |       | mood match: chill (+1.00)                                  |
|    |                                    |                      |       | energy 0.35 vs target 0.35 (+1.50)                         |
|    |                                    |                      |       | acousticness 0.86 vs target 0.8 (+0.47)                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 2  | Midnight Coding — LoRoom           | lofi / chill         | 4.35  | genre match: lofi (+2.00)                                  |
|    |                                    |                      |       | mood match: chill (+1.00)                                  |
|    |                                    |                      |       | energy 0.42 vs target 0.35 (+1.40)                         |
|    |                                    |                      |       | acousticness 0.71 vs target 0.8 (+0.45)                    |
|    |                                    |                      |       | diversity: lofi already listed (-0.50)                     |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 3  | Spacewalk Thoughts — Orbit Bloom   | ambient / chill      | 2.83  | mood match: chill (+1.00)                                  |
|    |                                    |                      |       | energy 0.28 vs target 0.35 (+1.40)                         |
|    |                                    |                      |       | acousticness 0.92 vs target 0.8 (+0.44)                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 4  | Coffee Shop Stories — Slow Stereo  | jazz / relaxed       | 1.93  | energy 0.37 vs target 0.35 (+1.47)                         |
|    |                                    |                      |       | acousticness 0.89 vs target 0.8 (+0.46)                    |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
| 5  | Focus Flow — LoRoom                | lofi / focused       | 1.92  | genre match: lofi (+2.00)                                  |
|    |                                    |                      |       | energy 0.4 vs target 0.35 (+1.42)                          |
|    |                                    |                      |       | acousticness 0.78 vs target 0.8 (+0.49)                    |
|    |                                    |                      |       | diversity: LoRoom already listed (-1.00)                   |
|    |                                    |                      |       | diversity: lofi already listed (-1.00)                     |
+----+------------------------------------+----------------------+-------+------------------------------------------------------------+
```

The full output for all 8 profiles, including the adversarial ones, is in the [model card's Evaluation section](model_card.md#7-evaluation).

---

## Features beyond the core

- **Five advanced song attributes:** `popularity` (0–100), `release_decade`, `mood_tags` (2–3 tags per song, e.g. `nostalgic;warm;open-road`), `instrumentalness` and `explicit`, added to all 20 songs in `data/songs.csv`. `load_songs()` converts them to int, float, list and bool. `score_song()` scores popularity, decade and instrumentalness by closeness (up to +0.5 each), gives +0.5 per shared mood tag, and applies −3.0 to explicit songs when a profile sets `allow_explicit: False`. The "Nostalgic Road Trip" and "clean workout" profiles exercise them.
- **Multiple scoring modes:** the Strategy-style `ScoringMode` / `MODES` in `src/recommender.py`, selected with `--mode` (see above).
- **Diversity penalty:** `diversity_penalty()` and `rerank_for_diversity()`, turned on with `--diverse`. Documented in the model card.
- **Results table:** `format_table()` in `src/main.py` draws an ASCII table (rank, song and artist, genre and mood, score) with each reason on its own wrapped line, using only the standard library (`textwrap`).

---

## Testing

```bash
python -m pytest
```

22 tests in `tests/test_recommender.py`: the two starter tests for `Recommender`, plus loading and type conversion, closeness scoring (nearer beats bigger), genre outweighing mood, sorting and `k` edge cases, unknown genres and modes, the energy-focused mode changing the pop/happy ranking, the diversity penalty, the explicit penalty, mood tags, and a test that the points listed in every explanation add up to the score in all four modes, with and without diversity. To make sure the tests can fail, I planted eight small bugs (closeness rewarding bigger values, genre weight 0.5, sorting ascending, ignoring the diversity penalty, always applying the explicit penalty, counting mood tags once, inverting `likes_acoustic`, not converting ints). Each one made at least one test fail.

```
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0 -- ~/ai110-module3show-musicrecommendersimulation-starter/.venv/bin/python
cachedir: .pytest_cache
rootdir: ~/ai110-module3show-musicrecommendersimulation-starter
configfile: pytest.ini
testpaths: tests
collecting ... collected 22 items

tests/test_recommender.py::test_recommend_returns_songs_sorted_by_score PASSED [  4%]
tests/test_recommender.py::test_explain_recommendation_returns_non_empty_string PASSED [  9%]
tests/test_recommender.py::test_load_songs_converts_types PASSED         [ 13%]
tests/test_recommender.py::test_score_song_returns_score_and_reasons PASSED [ 18%]
tests/test_recommender.py::test_closeness_rewards_nearness_not_bigger_values PASSED [ 22%]
tests/test_recommender.py::test_genre_match_outweighs_mood_match PASSED  [ 27%]
tests/test_recommender.py::test_recommendations_are_sorted_and_sized PASSED [ 31%]
tests/test_recommender.py::test_explanation_points_add_up_to_the_score[False-balanced] PASSED [ 36%]
tests/test_recommender.py::test_explanation_points_add_up_to_the_score[False-genre-first] PASSED [ 40%]
tests/test_recommender.py::test_explanation_points_add_up_to_the_score[False-mood-first] PASSED [ 45%]
tests/test_recommender.py::test_explanation_points_add_up_to_the_score[False-energy-focused] PASSED [ 50%]
tests/test_recommender.py::test_explanation_points_add_up_to_the_score[True-balanced] PASSED [ 54%]
tests/test_recommender.py::test_explanation_points_add_up_to_the_score[True-genre-first] PASSED [ 59%]
tests/test_recommender.py::test_explanation_points_add_up_to_the_score[True-mood-first] PASSED [ 63%]
tests/test_recommender.py::test_explanation_points_add_up_to_the_score[True-energy-focused] PASSED [ 68%]
tests/test_recommender.py::test_unknown_genre_still_returns_results PASSED [ 72%]
tests/test_recommender.py::test_unknown_mode_is_rejected PASSED          [ 77%]
tests/test_recommender.py::test_energy_focused_mode_lifts_happy_indie_pop_over_intense_pop PASSED [ 81%]
tests/test_recommender.py::test_diversity_penalty_demotes_repeat_artist_and_genre PASSED [ 86%]
tests/test_recommender.py::test_explicit_penalty_only_when_profile_asks_for_clean_lyrics PASSED [ 90%]
tests/test_recommender.py::test_mood_tags_score_per_shared_tag PASSED    [ 95%]
tests/test_recommender.py::test_recommender_class_uses_mode_and_profile_keys PASSED [100%]

============================== 22 passed in 0.03s ==============================
```

---

## Experiments You Tried

Details and full output are in the [model card](model_card.md#7-evaluation). In short:

- **Weight shift (genre 2.0 → 1.0, energy 1.5 → 3.0):** for the pop/happy profile, Rooftop Lights (indie pop, happy) moves above Gym Hero (pop, intense). That's more accurate. For "sad but hyped", loud songs push out the sad ones, which is just different, not better.
- **Mood check removed:** 6 of 8 profiles change. Chill Lofi picks up a sad blues song, and Gym Hero takes #1 for High-Energy Pop. Mood is what separates calm-happy from calm-sad.
- **Diversity penalty:** spreads Chill Lofi across lofi, ambient and jazz instead of two songs from the same artist.
- **Eight profiles**, including three adversarial ones (conflicting sad + high energy, a genre not in the catalog, and clean lyrics for a workout where the obvious pick is explicit).

---

## Limitations and Risks

- **Genre is an exact string match worth the most points**, so "indie pop" gets no credit from a pop fan, and an intense explicit pop song outranks a happy indie-pop song for a happy-pop listener.
- **A tiny, uneven catalog:** 20 songs, most genres with one song, so fans of small genres get one real match and then loud filler. The same few high-energy songs show up across most profiles.
- **Labels beat feel when preferences conflict**, and the clean-lyrics option is a penalty, not a filter, so an explicit song can still be recommended.
- **No listening history, lyrics or context**, so there's no collaborative filtering and no ground truth to measure accuracy against.

---

## Reflection

Building this made it concrete that a recommender is two decisions: what to *measure* (features) and how much each one is *worth* (weights). Turning a taste profile into a ranked list took one loop and one sort. What I spent my time on was finding out what the weights actually do. Every number in the recipe is a judgment about what listeners care about, and changing genre from 2.0 to 1.0 changed which song a "happy pop" fan sees second. Real systems learn those weights from millions of plays and skips instead of a student guessing them, but they are still choosing what to optimize.

Bias showed up without anyone intending it. The catalog has one rock song and three lofi songs, so rock fans get worse lists. Exact genre matching shuts out songs with slightly different labels, and once the label points run out, the same loud songs fill everyone's list, which is a small filter bubble. Every one of those results came with a tidy, true-sounding explanation. That's the part I'll remember: an explainable system isn't automatically a fair or good one. You have to test it with users it wasn't designed around. My full reflection is in [model_card.md](model_card.md#9-personal-reflection).
