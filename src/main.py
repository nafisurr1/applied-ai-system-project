"""
Command line runner for the Music Recommender Simulation.

Run from the project root with:  python -m src.main
"""

from src.recommender import load_songs, recommend_songs

PROFILES = {
    "Starter: pop / happy": {"genre": "pop", "mood": "happy", "energy": 0.8},
    "High-Energy Pop": {"genre": "pop", "mood": "happy", "energy": 0.9, "danceability": 0.85},
    "Chill Lofi": {"genre": "lofi", "mood": "chill", "energy": 0.35, "likes_acoustic": True},
    "Deep Intense Rock": {"genre": "rock", "mood": "intense", "energy": 0.92, "likes_acoustic": False},
    # Adversarial: wants sad songs but very high energy, a combination the catalog barely has.
    "Edge case: sad but hyped": {"genre": "folk", "mood": "sad", "energy": 0.9},
    # Adversarial: a genre that is not in the catalog at all.
    "Edge case: unknown genre": {"genre": "k-pop", "mood": "happy", "energy": 0.7},
}


def print_recommendations(name: str, prefs: dict, songs: list, k: int = 5) -> None:
    """Print one profile's top k songs with scores and reasons."""
    print(f"\n=== {name} ===")
    print("Profile: " + ", ".join(f"{key}={value}" for key, value in prefs.items()))
    for rank, (song, score, explanation) in enumerate(recommend_songs(prefs, songs, k), start=1):
        print(f"  {rank}. {song['title']} by {song['artist']} [{song['genre']}, {song['mood']}]  Score: {score:.2f}")
        print(f"     Because: {explanation}")


def main() -> None:
    """Load the catalog and print recommendations for every profile."""
    songs = load_songs("data/songs.csv")
    print(f"Loaded songs: {len(songs)}")
    for name, prefs in PROFILES.items():
        print_recommendations(name, prefs, songs)


if __name__ == "__main__":
    main()
