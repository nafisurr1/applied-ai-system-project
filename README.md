# 🎵 Music Recommender Simulation

## Project Summary

In this project you will build and explain a small music recommender system.

Your goal is to:

- Represent songs and a user "taste profile" as data
- Design a scoring rule that turns that data into recommendations
- Evaluate what your system gets right and wrong
- Reflect on how this mirrors real world AI recommenders

Replace this paragraph with your own summary of what your version does.

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
| Energy closeness | up to +1.5, computed as `1.5 × (1 − |song.energy − target|)` |
| Acousticness closeness (target 0.8 if `likes_acoustic`, else 0.2) | up to +0.5 |
| Any other numeric target the profile sets (valence, tempo, danceability, popularity, decade, instrumentalness) | up to +0.5 each, same closeness formula; tempo is scaled by 100 BPM, popularity by 100, decade by 50 years |
| Each matching mood tag | +0.5 |
| Explicit song when the profile has `allow_explicit: False` | −3.0 |

Closeness rewards songs that are **near** the target rather than just higher or lower. A user asking for energy 0.4 gets the most points from a 0.4 song, not from the loudest one. Genre counts double a mood match because it is the strongest single signal of whether a listener will even consider a song. Mood still adds a full point so it can break ties inside a genre.

**Ranking rule (the whole list):** score every song with the scoring rule, sort from highest to lowest (ties broken by song id so results repeat exactly), and return the top *k* with their reasons. Both rules are needed. The scoring rule only judges one song in isolation; the ranking rule is what turns many judgments into a recommendation, and it is where list-level rules such as the diversity penalty live.

**Data flow:** user preferences → loop over every song in the CSV and score it → sort → top *k* with explanations.

### Biases I expect before building

- Genre is worth the most points, so the system will probably over-prioritize genre and bury great songs that match the user's mood and energy but carry a different label. For example, "indie pop" is not an exact match for "pop".
- With 1–3 songs per genre, fans of small genres (metal, classical) will see the same one song on top every time and then unrelated filler.
- Energy closeness works the same at both ends of the scale, but the catalog has more mid- and high-energy songs, so low-energy listeners have fewer close options.

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Run the app:

```bash
python -m src.main
```

### Running Tests

Run the starter tests with:

```bash
pytest
```

You can add more tests in `tests/test_recommender.py`.

---

## Sample Recommendation Output

Paste a sample of your recommender's output here as a text block so a reader can see what it produces:

```
# e.g.:
# User profile: genre=indie, mood=chill, energy=low
# Recommendations:
#   1. ...
#   2. ...
#   3. ...
```

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or demo video link here -->

---

## Experiments You Tried

Use this section to document the experiments you ran. For example:

- What happened when you changed the weight on genre from 2.0 to 0.5
- What happened when you added tempo or valence to the score
- How did your system behave for different types of users

---

## Limitations and Risks

Summarize some limitations of your recommender.

Examples:

- It only works on a tiny catalog
- It does not understand lyrics or language
- It might over favor one genre or mood

You will go deeper on this in your model card.

---

## Reflection

Read and complete `model_card.md`:

[**Model Card**](model_card.md)

Write 1 to 2 paragraphs here about what you learned:

- about how recommenders turn data into predictions
- about where bias or unfairness could show up in systems like this



