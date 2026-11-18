"""
VibeMatch 2.0 command line.

  python -m src.vibematch "calm songs for studying, no explicit lyrics"
  python -m src.vibematch --offline "hype kpop for the gym"      # force the rule-based fallback
  python -m src.vibematch --trace "songs with saxophone"         # print every agent step
  python -m src.vibematch                                        # interactive; answers follow-up questions
"""

import argparse
import json

from src.agent import Concierge, Result


def describe_profile(profile: dict) -> str:
    """One line summarizing what the agent understood."""
    shown = []
    for key in ("genre", "mood", "activity", "energy", "mood_tags", "instrumentalness"):
        if key in profile:
            value = profile[key]
            shown.append(f"{key}={','.join(value) if isinstance(value, list) else value}")
    if profile.get("related_genres"):
        shown.append(f"related={','.join(profile['related_genres'])}")
    if profile.get("exclude_explicit"):
        shown.append("clean lyrics only")
    elif profile.get("allow_explicit") is False:
        shown.append("explicit discouraged")
    if profile.get("note_matches"):
        shown.append("song-note matches=" + ",".join(str(i) for i in profile["note_matches"]))
    return "; ".join(shown) or "(nothing usable)"


def render(result: Result, show_trace: bool = False) -> str:
    """Format a result for the terminal."""
    lines = [f'Request: "{result.request}"', f"Mode: {result.mode}"]
    if result.status != "ok":
        lines.append(f"Status: {result.status.upper()} — {result.message}")
    else:
        lines.append(f"Understood: {describe_profile(result.profile)}")
        lines.append("Retrieved: " + ", ".join(f"{src}/{title.split(' — ')[0]} ({score})" for src, title, score in result.retrieved[:4]))
        for note in result.notes:
            lines.append(f"Guardrail: {note}")
        lines.append("Picks:")
        for i, pick in enumerate(result.picks, start=1):
            song = pick.song
            lines.append(f"  {i}. {song['title']} — {song['artist']} [{song['genre']} / {song['mood']}] score {pick.score:.2f}")
            lines.append(f"     {pick.why}")
        lines.append(f"Answer: {result.message}")
        passed = sum(result.checks.values())
        failed = [name for name, ok in result.checks.items() if not ok]
        lines.append(f"Checks: {passed}/{len(result.checks)} passed" + (f" (failed: {', '.join(failed)})" if failed else ""))
        lines.append(f"Confidence: {result.confidence:.2f} ({result.confidence_label})")
    if show_trace:
        lines.append("Trace:")
        for entry in result.trace:
            lines.append("  " + json.dumps(entry, default=str))
    return "\n".join(lines)


def main() -> None:
    """Parse arguments and run one request, or an interactive session."""
    parser = argparse.ArgumentParser(description="VibeMatch 2.0: natural-language music recommendations")
    parser.add_argument("request", nargs="*", help="what you want to hear")
    parser.add_argument("--offline", action="store_true", help="skip the LLM and use the rule-based fallback")
    parser.add_argument("--zero-shot", action="store_true", help="parse without the few-shot examples")
    parser.add_argument("--bare-prompt", action="store_true", help="baseline parser prompt: field names only")
    parser.add_argument("--no-retrieval", action="store_true", help="ablation: skip the knowledge base")
    parser.add_argument("--trace", action="store_true", help="print every agent step")
    parser.add_argument("--k", type=int, default=5, help="picks to show in fallback mode")
    args = parser.parse_args()

    style = "bare" if args.bare_prompt else "zero-shot" if args.zero_shot else "few-shot"
    concierge = Concierge(offline=args.offline, prompt_style=style, k=args.k, use_retrieval=not args.no_retrieval)
    if args.request:
        print(render(concierge.run(" ".join(args.request)), args.trace))
        return

    print(f"VibeMatch 2.0 ({concierge.mode}). Blank line to quit.")
    while True:
        request = input("\nWhat do you want to hear? ").strip()
        if not request:
            break
        result = concierge.run(request)
        if result.status == "clarify":  # human in the loop: ask, then retry with the answer added
            follow_up = input(f"{result.message}\n> ").strip()
            if follow_up:
                result = concierge.run(f"{request}. {follow_up}")
        print(render(result, args.trace))


if __name__ == "__main__":
    main()
