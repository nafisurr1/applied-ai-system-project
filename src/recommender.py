"""Content-based music recommender: load a song catalog, score songs against a taste profile, rank them."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from typing import Dict, List, Tuple

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
    def __init__(self, songs: List[Song]):
        """Hold the catalog of Song objects."""
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Return the top k Song objects for this user, best first."""
        by_id = {song.id: song for song in self.songs}
        ranked = recommend_songs(user.to_prefs(), [asdict(s) for s in self.songs], k)
        return [by_id[song["id"]] for song, _, _ in ranked]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Explain in one line why this song scored the way it did for this user."""
        score, reasons = score_song(user.to_prefs(), asdict(song))
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


def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """
    Scores a single song against user preferences.
    Required by recommend_songs() and src/main.py
    """
    prefs = normalize_prefs(user_prefs)
    score = 0.0
    reasons = []

    for feature in ("genre", "mood"):
        wanted = prefs.get(feature)
        if wanted and str(song[feature]).lower() == str(wanted).lower():
            score += WEIGHTS[feature]
            reasons.append(f"{feature} match: {song[feature]} (+{WEIGHTS[feature]:.2f})")

    for feature in NUMERIC_PREFS:
        if feature not in prefs or feature not in song:
            continue
        target = float(prefs[feature])
        points = WEIGHTS[feature] * closeness(song[feature], target, SCALES.get(feature, 1.0))
        if points >= 0.01:
            score += points
            reasons.append(f"{feature} {song[feature]:g} vs target {target:g} (+{points:.2f})")

    wanted_tags = {tag.lower() for tag in prefs.get("mood_tags", [])}
    shared = sorted(wanted_tags & {tag.lower() for tag in song.get("mood_tags", [])})
    if shared:
        points = WEIGHTS["mood_tags"] * len(shared)
        score += points
        reasons.append(f"mood tags {', '.join(shared)} (+{points:.2f})")

    if prefs.get("allow_explicit") is False and song.get("explicit"):
        score += WEIGHTS["explicit"]
        reasons.append(f"explicit lyrics ({WEIGHTS['explicit']:+.2f})")

    return score, reasons


def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """
    Functional implementation of the recommendation logic.
    Required by src/main.py
    """
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song)
        scored.append((song, score, "; ".join(reasons) or "no matching features"))
    # sorted() returns a new list and leaves `songs` untouched; ties go to the lower id.
    return sorted(scored, key=lambda item: (-item[1], item[0]["id"]))[:max(k, 0)]
