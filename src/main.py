"""
Command line runner for the Music Recommender Simulation.

Run from the project root with:  python -m src.main
Options:  --mode {balanced,genre-first,mood-first,energy-focused}  --diverse  --k N  --profile NAME
"""

import argparse
import textwrap

from src.recommender import MODES, load_songs, recommend_songs

PROFILES = {
    "Starter: pop / happy": {"genre": "pop", "mood": "happy", "energy": 0.8},
    "High-Energy Pop": {"genre": "pop", "mood": "happy", "energy": 0.9, "danceability": 0.85},
    "Chill Lofi": {"genre": "lofi", "mood": "chill", "energy": 0.35, "likes_acoustic": True},
    "Deep Intense Rock": {"genre": "rock", "mood": "intense", "energy": 0.92, "likes_acoustic": False},
    # Uses the advanced attributes: decade, mood tags and a clean-lyrics filter.
    "Nostalgic Road Trip": {
        "genre": "country", "mood": "nostalgic", "energy": 0.6, "release_decade": 1990,
        "mood_tags": ["nostalgic", "warm", "open-road"], "allow_explicit": False,
    },
    # Adversarial: wants sad songs but very high energy, a combination the catalog barely has.
    "Edge case: sad but hyped": {"genre": "folk", "mood": "sad", "energy": 0.9},
    # Adversarial: a genre that is not in the catalog at all.
    "Edge case: unknown genre": {"genre": "k-pop", "mood": "happy", "energy": 0.7},
    # Adversarial: wants gym music but no explicit lyrics; the obvious pick (Gym Hero) is explicit.
    "Edge case: clean workout": {"genre": "pop", "mood": "intense", "energy": 0.9, "allow_explicit": False},
}

REASON_WIDTH = 58


def format_table(results: list) -> str:
    """Render ranked results as an ASCII table with one wrapped line per reason."""
    widths = [2, 34, 20, 5, REASON_WIDTH]
    rule = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def row(cells):
        return "| " + " | ".join(str(c).ljust(w) for c, w in zip(cells, widths)) + " |"

    lines = [rule, row(["#", "Song", "Genre / mood", "Score", "Why"]), rule]
    for rank, (song, score, explanation) in enumerate(results, start=1):
        reasons = []
        for reason in explanation.split("; "):
            reasons.extend(textwrap.wrap(reason, REASON_WIDTH) or [""])
        song_lines = textwrap.wrap(f"{song['title']} — {song['artist']}", widths[1])
        first = [rank, song_lines[0], f"{song['genre']} / {song['mood']}"[: widths[2]], f"{score:.2f}"]
        for i in range(max(len(reasons), len(song_lines))):
            left = first if i == 0 else ["", song_lines[i] if i < len(song_lines) else "", "", ""]
            lines.append(row(left + [reasons[i] if i < len(reasons) else ""]))
        lines.append(rule)
    return "\n".join(lines)


def print_recommendations(name: str, prefs: dict, songs: list, k: int, mode: str, diverse: bool) -> None:
    """Print one profile's top k songs as a table."""
    print(f"\n=== {name} ===")
    print("Profile: " + ", ".join(f"{key}={value}" for key, value in prefs.items()))
    print(f"Mode: {mode} ({MODES[mode].description}){' + diversity penalty' if diverse else ''}")
    print(format_table(recommend_songs(prefs, songs, k, mode, diverse)))


def main() -> None:
    """Load the catalog and print recommendations for every profile (or one)."""
    parser = argparse.ArgumentParser(description="Music Recommender Simulation")
    parser.add_argument("--mode", choices=list(MODES), default="balanced", help="scoring strategy")
    parser.add_argument("--diverse", action="store_true", help="penalize repeated artists and genres")
    parser.add_argument("--k", type=int, default=5, help="how many songs to recommend")
    parser.add_argument("--profile", choices=list(PROFILES), help="run only this profile")
    args = parser.parse_args()

    songs = load_songs("data/songs.csv")
    print(f"Loaded songs: {len(songs)}")
    names = [args.profile] if args.profile else list(PROFILES)
    for name in names:
        print_recommendations(name, PROFILES[name], songs, args.k, args.mode, args.diverse)


if __name__ == "__main__":
    main()
