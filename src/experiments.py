"""
Phase 4 experiments: how sensitive are the rankings to the weights?

Run from the project root with:  python -m src.experiments
"""

from src.main import PROFILES
from src.recommender import MODES, ScoringMode, load_songs, recommend_songs

EXPERIMENTS = {
    "baseline": MODES["balanced"],
    "weight shift": MODES["energy-focused"],  # energy x2 (3.0), genre x0.5 (1.0)
    "no mood": ScoringMode("no-mood", "feature removal: mood check turned off", {"mood": 0.0}),
}


def top_titles(prefs: dict, songs: list, mode: ScoringMode, k: int = 5) -> list:
    """Titles of the top k songs for one profile under one weighting."""
    return [song["title"] for song, _, _ in recommend_songs(prefs, songs, k, mode)]


def main() -> None:
    """Print each profile's top 5 under every experiment and mark what moved."""
    songs = load_songs("data/songs.csv")
    for name, prefs in PROFILES.items():
        base = top_titles(prefs, songs, EXPERIMENTS["baseline"])
        print(f"\n=== {name} ===")
        for label, mode in EXPERIMENTS.items():
            result = top_titles(prefs, songs, mode)
            changed = "" if result == base else "   <- changed"
            print(f"  {label:<13} {' | '.join(result)}{changed}")


if __name__ == "__main__":
    main()
