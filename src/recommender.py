"""Content-based music recommender: load a song catalog, score songs against a taste profile, rank them."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from typing import Dict, List, Tuple, Union

INT_FIELDS = {"id", "popularity", "release_decade"}
FLOAT_FIELDS = {"energy", "tempo_bpm", "valence", "danceability", "acousticness", "instrumentalness"}

# Points for each signal. Numeric features earn up to their weight, scaled by closeness.
WEIGHTS = {
    "genre": 2.0,
    "mood": 1.0,
    "energy": 1.5,
    "acousticness": 0.5,
    "valence": 0.5,
    "tempo_bpm": 0.5,
    "danceability": 0.5,
    "popularity": 0.5,
    "release_decade": 0.5,
    "instrumentalness": 0.5,
    "mood_tags": 0.5,  # per matching tag
    "explicit": -3.0,  # applied when the profile sets allow_explicit=False
}
# How big a gap counts as "completely different" for each numeric feature (default 1.0).
SCALES = {"tempo_bpm": 100.0, "popularity": 100.0, "release_decade": 50.0}
NUMERIC_PREFS = (
    "energy", "acousticness", "valence", "tempo_bpm", "danceability",
    "popularity", "release_decade", "instrumentalness",
)
# Diversity penalty: points taken off for each song already in the list by the same artist / in the same genre.
ARTIST_PENALTY = 1.0
GENRE_PENALTY = 0.5


@dataclass(frozen=True)
class ScoringMode:
    """A weighting strategy. score_song() runs the same algorithm and reads every weight from the active mode."""
    name: str
    description: str
    overrides: Dict[str, float]

    def weight(self, feature: str) -> float:
        """This mode's weight for a feature, falling back to the default recipe."""
        return self.overrides.get(feature, WEIGHTS[feature])


MODES = {
    "balanced": ScoringMode("balanced", "default recipe: genre 2.0, mood 1.0, energy up to 1.5", {}),
    "genre-first": ScoringMode("genre-first", "stay inside the favorite genre", {"genre": 4.0, "mood": 0.5, "energy": 1.0}),
    "mood-first": ScoringMode("mood-first", "match the feeling over the label", {"genre": 1.0, "mood": 3.0, "mood_tags": 1.0}),
    "energy-focused": ScoringMode("energy-focused", "weight-shift experiment: energy doubled, genre halved", {"genre": 1.0, "energy": 3.0}),
}


@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float
    popularity: int = 50
    release_decade: int = 2010
    mood_tags: Tuple[str, ...] = ()
    instrumentalness: float = 0.0
    explicit: bool = False


@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

    def to_prefs(self) -> Dict:
        """Convert the profile to the preference dictionary score_song() expects."""
        return {
            "genre": self.favorite_genre,
            "mood": self.favorite_mood,
            "energy": self.target_energy,
            "likes_acoustic": self.likes_acoustic,
        }


class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song], mode: str = "balanced", diverse: bool = False):
        """Hold the catalog of Song objects and the scoring options."""
        self.songs = songs
        self.mode = mode
        self.diverse = diverse

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Return the top k Song objects for this user, best first."""
        by_id = {song.id: song for song in self.songs}
        ranked = recommend_songs(user.to_prefs(), [asdict(s) for s in self.songs], k, self.mode, self.diverse)
        return [by_id[song["id"]] for song, _, _ in ranked]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Explain in one line why this song scored the way it did for this user."""
        score, reasons = score_song(user.to_prefs(), asdict(song), self.mode)
        return f"Score {score:.2f}: " + ("; ".join(reasons) or "no matching features")


def load_songs(csv_path: str) -> List[Dict]:
    """
    Loads songs from a CSV file.
    Required by src/main.py
    """
    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            song = dict(row)
            for field in INT_FIELDS & song.keys():
                song[field] = int(song[field])
            for field in FLOAT_FIELDS & song.keys():
                song[field] = float(song[field])
            if "mood_tags" in song:
                song["mood_tags"] = [tag.strip() for tag in song["mood_tags"].split(";") if tag.strip()]
            if "explicit" in song:
                song["explicit"] = song["explicit"].strip().lower() in ("1", "true", "yes")
            songs.append(song)
    return songs


def closeness(value: float, target: float, scale: float = 1.0) -> float:
    """1.0 when value equals target, falling linearly to 0.0 when they are `scale` apart."""
    return max(0.0, 1.0 - abs(value - target) / scale)


def normalize_prefs(user_prefs: Dict) -> Dict:
    """Accept either short keys ("genre") or UserProfile-style keys ("favorite_genre")."""
    prefs = dict(user_prefs)
    for long_key, short_key in (("favorite_genre", "genre"), ("favorite_mood", "mood"), ("target_energy", "energy")):
        if long_key in prefs:
            prefs.setdefault(short_key, prefs.pop(long_key))
    if "likes_acoustic" in prefs and "acousticness" not in prefs:
        prefs["acousticness"] = 0.8 if prefs["likes_acoustic"] else 0.2
    return prefs


def get_mode(mode: Union[str, ScoringMode]) -> ScoringMode:
    """Look up a scoring mode by name (or pass one through)."""
    if isinstance(mode, ScoringMode):
        return mode
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; choose from {', '.join(MODES)}")
    return MODES[mode]


def score_song(user_prefs: Dict, song: Dict, mode: Union[str, ScoringMode] = "balanced") -> Tuple[float, List[str]]:
    """
    Scores a single song against user preferences.
    Required by recommend_songs() and src/main.py
    """
    prefs = normalize_prefs(user_prefs)
    weight = get_mode(mode).weight
    score = 0.0
    reasons = []

    for feature in ("genre", "mood"):
        wanted = prefs.get(feature)
        if wanted and weight(feature) and str(song[feature]).lower() == str(wanted).lower():
            score += weight(feature)
            reasons.append(f"{feature} match: {song[feature]} (+{weight(feature):.2f})")

    for feature in NUMERIC_PREFS:
        if feature not in prefs or feature not in song:
            continue
        target = float(prefs[feature])
        points = weight(feature) * closeness(song[feature], target, SCALES.get(feature, 1.0))
        if points >= 0.01:
            score += points
            reasons.append(f"{feature} {song[feature]:g} vs target {target:g} (+{points:.2f})")

    wanted_tags = {tag.lower() for tag in prefs.get("mood_tags", [])}
    shared = sorted(wanted_tags & {tag.lower() for tag in song.get("mood_tags", [])})
    if shared:
        points = weight("mood_tags") * len(shared)
        score += points
        reasons.append(f"mood tags {', '.join(shared)} (+{points:.2f})")

    if prefs.get("allow_explicit") is False and song.get("explicit"):
        score += weight("explicit")
        reasons.append(f"explicit lyrics ({weight('explicit'):+.2f})")

    return score, reasons


def diversity_penalty(song: Dict, picked: List[Dict]) -> Tuple[float, List[str]]:
    """Points to subtract because songs by this artist or in this genre are already in the list."""
    same_artist = sum(p["artist"] == song["artist"] for p in picked)
    same_genre = sum(p["genre"] == song["genre"] for p in picked)
    penalty, reasons = 0.0, []
    if same_artist:
        penalty += ARTIST_PENALTY * same_artist
        reasons.append(f"diversity: {song['artist']} already listed (-{ARTIST_PENALTY * same_artist:.2f})")
    if same_genre:
        penalty += GENRE_PENALTY * same_genre
        reasons.append(f"diversity: {song['genre']} already listed (-{GENRE_PENALTY * same_genre:.2f})")
    return penalty, reasons


def recommend_songs(
    user_prefs: Dict,
    songs: List[Dict],
    k: int = 5,
    mode: Union[str, ScoringMode] = "balanced",
    diverse: bool = False,
) -> List[Tuple[Dict, float, str]]:
    """
    Functional implementation of the recommendation logic.
    Required by src/main.py
    """
    scored = [(song, *score_song(user_prefs, song, mode)) for song in songs]
    # sorted() returns a new list and leaves `songs` untouched; ties go to the lower id.
    ranked = sorted(scored, key=lambda item: (-item[1], item[0]["id"]))
    if diverse:
        ranked = rerank_for_diversity(ranked, k)
    return [(song, score, "; ".join(reasons) or "no matching features") for song, score, reasons in ranked[:max(k, 0)]]


def rerank_for_diversity(ranked: List[Tuple[Dict, float, List[str]]], k: int) -> List[Tuple[Dict, float, List[str]]]:
    """Greedily build the top k, each time taking the best song after its diversity penalty."""
    remaining, picked = list(ranked), []
    while remaining and len(picked) < k:
        best = None
        for index, (song, score, reasons) in enumerate(remaining):
            penalty, notes = diversity_penalty(song, [p[0] for p in picked])
            candidate = (score - penalty, -song["id"], index, reasons + notes)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
        adjusted, _, index, reasons = best
        picked.append((remaining.pop(index)[0], adjusted, reasons))
    return picked
