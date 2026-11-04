import re

import pytest

from src.recommender import Recommender, Song, UserProfile, closeness, load_songs, recommend_songs, score_song

def make_small_recommender() -> Recommender:
    songs = [
        Song(
            id=1,
            title="Test Pop Track",
            artist="Test Artist",
            genre="pop",
            mood="happy",
            energy=0.8,
            tempo_bpm=120,
            valence=0.9,
            danceability=0.8,
            acousticness=0.2,
        ),
        Song(
            id=2,
            title="Chill Lofi Loop",
            artist="Test Artist",
            genre="lofi",
            mood="chill",
            energy=0.4,
            tempo_bpm=80,
            valence=0.6,
            danceability=0.5,
            acousticness=0.9,
        ),
    ]
    return Recommender(songs)


def test_recommend_returns_songs_sorted_by_score():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    results = rec.recommend(user, k=2)

    assert len(results) == 2
    # Starter expectation: the pop, happy, high energy song should score higher
    assert results[0].genre == "pop"
    assert results[0].mood == "happy"


def test_explain_recommendation_returns_non_empty_string():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    song = rec.songs[0]

    explanation = rec.explain_recommendation(user, song)
    assert isinstance(explanation, str)
    assert explanation.strip() != ""


# --- Added tests ------------------------------------------------------------

CATALOG = load_songs("data/songs.csv")
POP_HAPPY = {"genre": "pop", "mood": "happy", "energy": 0.8}


def titles(results):
    return [song["title"] for song, _, _ in results]


def test_load_songs_converts_types():
    assert len(CATALOG) == 20
    song = CATALOG[0]
    assert isinstance(song["id"], int) and isinstance(song["energy"], float)
    assert isinstance(song["popularity"], int) and isinstance(song["release_decade"], int)
    assert song["mood_tags"] == ["euphoric", "sunny", "carefree"]
    assert isinstance(song["explicit"], bool)


def test_score_song_returns_score_and_reasons():
    score, reasons = score_song(POP_HAPPY, CATALOG[0])  # Sunrise City: pop, happy, energy 0.82
    assert isinstance(score, float)
    assert "genre match: pop (+2.00)" in reasons
    assert "mood match: happy (+1.00)" in reasons
    assert score == pytest.approx(2.0 + 1.0 + 1.5 * (1 - 0.02))


def test_closeness_rewards_nearness_not_bigger_values():
    assert closeness(0.4, 0.4) == 1.0
    assert closeness(0.9, 0.4) < closeness(0.45, 0.4)
    assert closeness(0.0, 1.0) == 0.0
    low, _ = score_song({"energy": 0.4}, {"genre": "x", "mood": "y", "energy": 0.4})
    high, _ = score_song({"energy": 0.4}, {"genre": "x", "mood": "y", "energy": 0.9})
    assert low > high


def test_genre_match_outweighs_mood_match():
    genre_only, _ = score_song({"genre": "rock", "mood": "sad"}, {"genre": "rock", "mood": "happy"})
    mood_only, _ = score_song({"genre": "rock", "mood": "sad"}, {"genre": "pop", "mood": "sad"})
    assert genre_only > mood_only


def test_recommendations_are_sorted_and_sized():
    results = recommend_songs(POP_HAPPY, CATALOG, k=5)
    scores = [score for _, score, _ in results]
    assert len(results) == 5
    assert scores == sorted(scores, reverse=True)
    assert titles(results)[0] == "Sunrise City"
    assert len(recommend_songs(POP_HAPPY, CATALOG, k=100)) == 20
    assert recommend_songs(POP_HAPPY, CATALOG, k=0) == []


@pytest.mark.parametrize("mode", ["balanced", "genre-first", "mood-first", "energy-focused"])
@pytest.mark.parametrize("diverse", [False, True])
def test_explanation_points_add_up_to_the_score(mode, diverse):
    prefs = {"genre": "lofi", "mood": "chill", "energy": 0.35, "likes_acoustic": True, "mood_tags": ["cozy"]}
    for _, score, explanation in recommend_songs(prefs, CATALOG, k=5, mode=mode, diverse=diverse):
        listed = sum(float(x) for x in re.findall(r"\(([+-]\d+\.\d+)\)", explanation))
        assert listed == pytest.approx(score, abs=0.03)


def test_unknown_genre_still_returns_results():
    results = recommend_songs({"genre": "k-pop", "mood": "happy", "energy": 0.7}, CATALOG, k=3)
    assert len(results) == 3
    assert all("genre match" not in why for _, _, why in results)


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        recommend_songs(POP_HAPPY, CATALOG, mode="loudest-first")


def test_energy_focused_mode_lifts_happy_indie_pop_over_intense_pop():
    balanced = titles(recommend_songs(POP_HAPPY, CATALOG, k=3))
    shifted = titles(recommend_songs(POP_HAPPY, CATALOG, k=3, mode="energy-focused"))
    assert balanced.index("Gym Hero") < balanced.index("Rooftop Lights")
    assert shifted.index("Rooftop Lights") < shifted.index("Gym Hero")


def test_diversity_penalty_demotes_repeat_artist_and_genre():
    prefs = {"genre": "lofi", "mood": "chill", "energy": 0.35, "likes_acoustic": True}
    plain = titles(recommend_songs(prefs, CATALOG, k=5))
    diverse = recommend_songs(prefs, CATALOG, k=5, diverse=True)
    assert plain.index("Focus Flow") == 2
    assert titles(diverse).index("Focus Flow") == 4
    focus_reasons = dict((s["title"], why) for s, _, why in diverse)["Focus Flow"]
    assert "diversity: LoRoom already listed (-1.00)" in focus_reasons
    scores = [score for _, score, _ in diverse]
    assert scores == sorted(scores, reverse=True)


def test_explicit_penalty_only_when_profile_asks_for_clean_lyrics():
    gym_hero = next(s for s in CATALOG if s["title"] == "Gym Hero")
    allowed, _ = score_song({"genre": "pop"}, gym_hero)
    clean, reasons = score_song({"genre": "pop", "allow_explicit": False}, gym_hero)
    assert allowed - clean == pytest.approx(3.0)
    assert "explicit lyrics (-3.00)" in reasons


def test_mood_tags_score_per_shared_tag():
    dusty = next(s for s in CATALOG if s["title"] == "Dusty Highway")
    score, reasons = score_song({"mood_tags": ["nostalgic", "warm", "rainy"]}, dusty)
    assert score == pytest.approx(1.0)
    assert reasons == ["mood tags nostalgic, warm (+1.00)"]


def test_recommender_class_uses_mode_and_profile_keys():
    songs = [Song(**{k: v for k, v in s.items() if k in Song.__dataclass_fields__}) for s in CATALOG]
    user = UserProfile(favorite_genre="pop", favorite_mood="happy", target_energy=0.8, likes_acoustic=False)
    assert Recommender(songs).recommend(user, k=1)[0].title == "Sunrise City"
    shifted = [s.title for s in Recommender(songs, mode="energy-focused").recommend(user, k=3)]
    assert shifted.index("Rooftop Lights") < shifted.index("Gym Hero")
