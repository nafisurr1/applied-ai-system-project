"""
VibeMatch 2.0 agent: turns a free-text music request into grounded, verified recommendations.

Pipeline (each step is recorded in the trace and the log file):
  guard input -> retrieve knowledge -> parse request (LLM, few-shot) -> validate/normalize profile
  -> clarify if too vague -> rank with the recommender -> compose answer (LLM) -> verify -> confidence
Every LLM step has a deterministic fallback, so the system still works without Ollama.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.llm_client import LLMError, OllamaClient
from src.recommender import load_songs, recommend_songs
from src.retriever import Knowledge, Retriever, tokenize

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "logs" / "vibematch.log"
MAX_REQUEST_CHARS = 500
INJECTION_PATTERNS = re.compile(
    r"ignore (all |any )?(previous|prior|above) instructions|system prompt|developer mode|jailbreak|"
    r"you are now|disregard (the )?rules|reveal your (prompt|instructions)",
    re.I,
)
EXPLICIT_OFF = re.compile(r"\b(clean|no (explicit|swearing|cursing|curse words|bad words)|kid[- ]?friendly|family[- ]friendly|for (my )?kids)\b", re.I)
MOOD_SYNONYMS = {
    "upbeat": "happy", "cheerful": "happy", "joyful": "happy", "feel-good": "happy", "feel good": "happy",
    "calm": "chill", "mellow": "chill", "chilled": "chill", "laid-back": "relaxed", "laid back": "relaxed",
    "relaxing": "relaxed", "melancholy": "melancholic", "hype": "intense", "hyped": "intense",
    "energetic": "intense", "pumped": "intense", "aggressive": "angry", "love": "romantic", "dark": "moody",
    "focus": "focused", "fun": "playful", "heartbroken": "sad", "depressing": "sad",
}
ENERGY_WORDS = [
    (re.compile(r"\b(very calm|super chill|low[- ]energy|quiet|soft|sleepy)\b", re.I), 0.25),
    (re.compile(r"\b(high[- ]energy|hype|hyped|intense|banger|pumped|loud)\b", re.I), 0.9),
]

PARSE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_music_request": {"type": "boolean"},
        "genre": {"type": ["string", "null"]},
        "mood": {"type": ["string", "null"]},
        "activity": {"type": ["string", "null"]},
        "energy": {"type": ["number", "null"]},
        "mood_tags": {"type": "array", "items": {"type": "string"}},
        "exclude_explicit": {"type": "boolean"},
        "described_sound": {"type": ["string", "null"]},
    },
    "required": ["is_music_request", "genre", "mood", "activity", "energy", "mood_tags", "exclude_explicit", "described_sound"],
}
COMPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "picks": {
            "type": "array",
            "items": {"type": "object", "properties": {"id": {"type": "integer"}, "why": {"type": "string"}}, "required": ["id", "why"]},
        },
        "summary": {"type": "string"},
    },
    "required": ["picks", "summary"],
}
FEW_SHOT = [
    ("something mellow to study to, no swearing please",
     {"is_music_request": True, "genre": None, "mood": "chill", "activity": "studying", "energy": None,
      "mood_tags": ["calm"], "exclude_explicit": True, "described_sound": None}),
    ("hype k-pop for leg day",
     {"is_music_request": True, "genre": "k-pop", "mood": "intense", "activity": "workout", "energy": 0.9,
      "mood_tags": ["pumped"], "exclude_explicit": False, "described_sound": None}),
    ("songs with a saxophone for a rainy afternoon",
     {"is_music_request": True, "genre": None, "mood": "relaxed", "activity": "rainy day", "energy": None,
      "mood_tags": ["rainy", "cozy"], "exclude_explicit": False, "described_sound": "saxophone"}),
    ("what's the capital of france?",
     {"is_music_request": False, "genre": None, "mood": None, "activity": None, "energy": None,
      "mood_tags": [], "exclude_explicit": False, "described_sound": None}),
]


def setup_logger(path: Path = LOG_PATH) -> logging.Logger:
    """File logger that writes one JSON object per pipeline step."""
    logger = logging.getLogger("vibematch")
    if not logger.handlers:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


@dataclass
class Pick:
    """One recommended song with its ranking score and the explanation shown to the user."""
    song: Dict
    score: float
    why: str


@dataclass
class Result:
    """Everything one run produced, including the step-by-step trace."""
    request: str
    status: str  # "ok" | "clarify" | "refused"
    message: str
    mode: str = "offline"
    profile: Dict = field(default_factory=dict)
    picks: List[Pick] = field(default_factory=list)
    confidence: float = 0.0
    confidence_label: str = "low"
    checks: Dict[str, bool] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    retrieved: List[Tuple[str, str, float]] = field(default_factory=list)
    trace: List[Dict] = field(default_factory=list)


class Concierge:
    """Orchestrates retrieval, the LLM, the recommender and the verifier for one request at a time."""

    def __init__(self, llm: Optional[object] = None, offline: bool = False, few_shot: bool = True, k: int = 5,
                 songs: Optional[List[Dict]] = None, logger: Optional[logging.Logger] = None):
        """Use the given LLM (or a local Ollama client) unless offline mode is forced or no model is reachable."""
        self.songs = songs if songs is not None else load_songs(str(ROOT / "data" / "songs.csv"))
        self.retriever = Retriever()
        self.knowledge = Knowledge(self.retriever.chunks)
        self.few_shot = few_shot
        self.k = k
        self.logger = logger or setup_logger()
        self.catalog_moods = sorted({s["mood"] for s in self.songs})
        self.catalog_tags = sorted({t for s in self.songs for t in s.get("mood_tags", [])})
        self.titles = {s["title"].lower(): s["id"] for s in self.songs}
        if offline:
            self.llm = None
        elif llm is not None:
            self.llm = llm
        else:
            client = OllamaClient()
            self.llm = client if client.is_available() else None
        self.mode = f"llm ({self.llm.name})" if self.llm else "offline (rule-based fallback)"

    # -- public entry point ------------------------------------------------------------------

    def run(self, request: str) -> Result:
        """Answer one request end to end."""
        result = Result(request=request, status="ok", message="", mode=self.mode)
        self._step(result, "start", mode=self.mode, few_shot=self.few_shot)

        problem = self.guard_input(request)
        if problem:
            result.status, result.message = "refused", problem
            self._step(result, "guard_input", blocked=True, reason=problem)
            return result
        self._step(result, "guard_input", blocked=False)

        hits = self.retriever.search(request, k=6)
        result.retrieved = [(c.source, c.title, round(s, 2)) for c, s in hits]
        self._step(result, "retrieve", hits=result.retrieved)

        raw, parse_mode = self.parse_request(request, hits, result)
        if not raw.get("is_music_request", True):
            result.status = "refused"
            result.message = "I can only help with music recommendations. Try something like 'calm songs for studying'."
            self._step(result, "scope_check", in_scope=False)
            return result

        profile, notes = self.validate_profile(raw, request)
        result.profile, result.notes = profile, notes
        self._step(result, "validate_profile", profile=profile, fixes=notes)

        if not self._has_signal(profile):
            result.status = "clarify"
            result.message = ("I need a little more to go on. What are you doing while you listen (studying, working out, "
                              "driving...), or what genre or mood do you want?")
            self._step(result, "clarify", question=result.message)
            return result

        candidates = recommend_songs(profile, self.songs, k=8, diverse=True)
        self._step(result, "rank", candidates=[(s["id"], s["title"], round(sc, 2)) for s, sc, _ in candidates])

        picks, summary, compose_mode = self.compose(request, profile, candidates, result)
        result.picks = picks
        result.checks = self.verify(picks, candidates, profile)
        self._step(result, "final_checks", checks=result.checks)

        result.confidence, result.confidence_label = self.confidence(profile, candidates, parse_mode, compose_mode, notes)
        prefix = ""
        if result.confidence_label == "low":
            wanted = profile.get("genre") or "that request"
            prefix = f"No strong match for {wanted} in this catalog; these are the closest by mood and energy. "
        result.message = prefix + summary
        self._step(result, "done", confidence=result.confidence, label=result.confidence_label)
        return result

    # -- step 1: input guardrail -------------------------------------------------------------

    @staticmethod
    def guard_input(request: str) -> Optional[str]:
        """Return a refusal message for empty, oversized or prompt-injection input, else None."""
        text = (request or "").strip()
        if not text:
            return "Tell me what you'd like to hear, for example 'upbeat songs for a road trip'."
        if len(text) > MAX_REQUEST_CHARS:
            return f"That request is too long ({len(text)} characters). Please keep it under {MAX_REQUEST_CHARS}."
        if INJECTION_PATTERNS.search(text):
            return "I can't change my instructions. Ask me for music instead, like 'calm songs for studying'."
        return None

    # -- step 2: parse the request -----------------------------------------------------------

    def parse_request(self, request: str, hits: List, result: Result) -> Tuple[Dict, str]:
        """Ask the LLM for a structured profile; fall back to the rule-based parser on any failure."""
        if self.llm is not None:
            system = self._parse_prompt(hits)
            for attempt in (1, 2):
                try:
                    raw = self.llm.chat_json(system, request, PARSE_SCHEMA)
                    self._step(result, "parse_request", source="llm", attempt=attempt, raw=raw)
                    return raw, "llm"
                except LLMError as err:
                    self._step(result, "parse_request", source="llm", attempt=attempt, error=str(err), level="warning")
        raw = self.rule_based_parse(request)
        self._step(result, "parse_request", source="rules", raw=raw)
        return raw, "rules"

    def _parse_prompt(self, hits: List) -> str:
        """System prompt with the allowed vocabulary, retrieved guide snippets and (optionally) few-shot examples."""
        guides = [f"[{c.source}/{c.title}] {c.text[:400]}" for c, _ in hits if c.source != "song_notes"]
        prompt = (
            "You turn a listener's music request into JSON for a recommender. Fill a field only if the request "
            "states or clearly implies it; otherwise use null (or [] / false).\n"
            f"- genre: a genre name the listener asked for (any spelling).\n"
            f"- mood: one of {', '.join(self.catalog_moods)}.\n"
            f"- activity: one of {', '.join(sorted(self.knowledge.activities))}.\n"
            "- energy: 0.0 (very calm) to 1.0 (very intense), only if the listener describes intensity.\n"
            f"- mood_tags: up to 3 of {', '.join(self.catalog_tags)}.\n"
            "- exclude_explicit: true only if the listener asks for clean / kid-friendly / no explicit lyrics.\n"
            "- described_sound: instruments or sounds the listener mentions (e.g. 'saxophone'), else null.\n"
            "- is_music_request: false if the message is not asking for music at all.\n"
            "Reference notes retrieved for this request:\n" + ("\n".join(guides) or "(none)")
        )
        if self.few_shot:
            examples = "\n".join(f"Request: {q}\nJSON: {json.dumps(a)}" for q, a in FEW_SHOT)
            prompt += "\nExamples:\n" + examples
        return prompt

    def rule_based_parse(self, request: str) -> Dict:
        """Deterministic keyword parser used when no LLM is available or the LLM fails twice."""
        text = request.lower()
        raw = {"is_music_request": True, "genre": None, "mood": None, "activity": None, "energy": None,
               "mood_tags": [], "exclude_explicit": bool(EXPLICIT_OFF.search(request)), "described_sound": None}
        for alias in sorted(self.knowledge.genre_alias, key=len, reverse=True):
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", text):
                raw["genre"] = alias
                break
        for alias in sorted(self.knowledge.activity_alias, key=len, reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", text):
                raw["activity"] = alias
                break
        for word in sorted(list(self.catalog_moods) + list(MOOD_SYNONYMS), key=len, reverse=True):
            if re.search(rf"\b{re.escape(word)}\b", text):
                raw["mood"] = word
                break
        for pattern, value in ENERGY_WORDS:
            if pattern.search(text):
                raw["energy"] = value
        raw["mood_tags"] = [t for t in self.catalog_tags if re.search(rf"\b{re.escape(t)}\b", text)][:3]
        return raw

    # -- step 3: validate and normalize (guardrail on model output) ------------------------------

    def validate_profile(self, raw: Dict, request: str) -> Tuple[Dict, List[str]]:
        """Map the parsed request onto catalog vocabulary, merge retrieved activity guidance, and log every fix."""
        notes: List[str] = []
        profile: Dict = {}

        genre_text = raw.get("genre")
        genre = self.knowledge.canonical_genre(genre_text)
        if genre_text and not genre:
            notes.append(f"unknown genre '{genre_text}' ignored")
        elif genre:
            if genre_text.strip().lower() != genre:
                notes.append(f"genre '{genre_text}' normalized to '{genre}'")
            profile["genre"] = genre
            profile["related_genres"] = self.knowledge.related_genres(genre)
            if not self.knowledge.in_catalog(genre):
                notes.append(f"'{genre}' is not in the catalog; using related genres {', '.join(profile['related_genres'])}")

        mood_text = (raw.get("mood") or "").strip().lower()
        mood = mood_text if mood_text in self.catalog_moods else MOOD_SYNONYMS.get(mood_text)
        if mood_text and not mood:
            notes.append(f"mood '{mood_text}' is not a catalog mood; ignored")
        elif mood:
            if mood != mood_text:
                notes.append(f"mood '{mood_text}' normalized to '{mood}'")
            profile["mood"] = mood

        activity = self.knowledge.canonical_activity(raw.get("activity"))
        targets: Dict = {}
        if raw.get("activity") and not activity:
            notes.append(f"activity '{raw['activity']}' not in the activity guide; ignored")
        elif activity:
            profile["activity"] = activity
            targets = self.knowledge.activity_targets(activity)

        energy = raw.get("energy")
        if isinstance(energy, (int, float)) and not isinstance(energy, bool):
            clamped = min(max(float(energy), 0.0), 1.0)
            if clamped != energy:
                notes.append(f"energy {energy} clamped to {clamped}")
            profile["energy"] = clamped
        elif "energy" in targets:
            profile["energy"] = targets["energy"]
            notes.append(f"energy {targets['energy']} taken from the '{activity}' activity guide")

        tags = [t.strip().lower() for t in raw.get("mood_tags") or [] if isinstance(t, str)]
        kept = [t for t in tags if t in self.catalog_tags][:3]
        if len(kept) < len(tags):
            notes.append(f"dropped mood tags not in the catalog: {', '.join(t for t in tags if t not in kept)}")
        if not kept and targets.get("mood_tags"):
            kept = [t for t in targets["mood_tags"] if t in self.catalog_tags][:3]
        if kept:
            profile["mood_tags"] = kept

        if "instrumentalness" in targets:
            profile["instrumentalness"] = targets["instrumentalness"]
        if raw.get("exclude_explicit") or EXPLICIT_OFF.search(request) or targets.get("exclude_explicit"):
            profile["exclude_explicit"] = True
        elif targets.get("allow_explicit") is False:
            profile["allow_explicit"] = False

        sound = raw.get("described_sound")
        note_query = f"{sound} {request}" if sound else request
        matches: Dict[int, str] = {}
        query_terms = set(tokenize(note_query))
        for chunk, score in self.retriever.search(note_query, k=3, sources=["song_notes"], min_score=3.0):
            song_id = int(chunk.title.split(".", 1)[0])
            shared = list(dict.fromkeys(t for t in tokenize(chunk.title + " " + chunk.text) if t in query_terms))[:3]
            matches[song_id] = "'" + ", ".join(shared) + "'" if shared else "the request"
        if matches:
            profile["note_matches"] = matches
        return profile, notes

    @staticmethod
    def _has_signal(profile: Dict) -> bool:
        """True if the profile has anything the recommender can score."""
        return any(profile.get(key) for key in ("genre", "mood", "activity", "energy", "mood_tags", "note_matches"))

    # -- step 4: compose and verify ----------------------------------------------------------

    def compose(self, request: str, profile: Dict, candidates: List, result: Result) -> Tuple[List[Pick], str, str]:
        """LLM picks 3-5 candidates with grounded reasons; one retry with verifier feedback, then a template fallback."""
        by_id = {s["id"]: (s, sc, why) for s, sc, why in candidates}
        if self.llm is not None:
            feedback = ""
            for attempt in (1, 2):
                try:
                    reply = self.llm.chat_json(self._compose_prompt(profile, candidates), request + feedback, COMPOSE_SCHEMA)
                except LLMError as err:
                    self._step(result, "compose", source="llm", attempt=attempt, error=str(err), level="warning")
                    continue
                picks = []
                for p in reply.get("picks", []):
                    if not isinstance(p, dict):
                        continue
                    if p.get("id") in by_id:
                        song, score, _ = by_id[p["id"]]
                    else:  # keep invented ids so the verifier can reject them
                        song, score = {"id": p.get("id"), "title": f"unknown id {p.get('id')}", "explicit": False}, 0.0
                    picks.append(Pick(song, score, str(p.get("why", "")).strip()))
                checks = self.verify(picks, candidates, profile)
                self._step(result, "compose", source="llm", attempt=attempt, picks=[(p.song.get("id"), p.why) for p in picks],
                           summary=reply.get("summary"), checks=checks)
                if all(checks.values()):
                    return picks, str(reply.get("summary", "")).strip(), "llm"
                failed = [name for name, ok in checks.items() if not ok]
                feedback = ("\n\nYour previous answer failed these checks: " + ", ".join(failed) +
                            ". Choose 3-5 songs using only candidate ids, and only mention each song's own title.")
            self._step(result, "compose", source="template", reason="llm answer failed verification twice", level="warning")
        picks = [Pick(s, sc, self._template_reason(s, why)) for s, sc, why in candidates[: self.k]]
        summary = self._template_summary(profile)
        self._step(result, "compose", source="template", picks=[(p.song["id"], p.why) for p in picks])
        return picks, summary, "template"

    def _compose_prompt(self, profile: Dict, candidates: List) -> str:
        """System prompt listing only the ranked candidates, their scoring reasons and their liner notes."""
        lines = []
        for song, score, why in candidates:
            note = self.knowledge.song_notes.get(song["id"])
            lines.append(f"id {song['id']} | {song['title']} — {song['artist']} | {song['genre']} / {song['mood']} | "
                         f"energy {song['energy']} | explicit: {'yes' if song.get('explicit') else 'no'} | score {score:.2f} "
                         f"({why}) | notes: {note.text if note else 'none'}")
        return (
            "You are VibeMatch, a music concierge. Recommend 3 to 5 songs for the listener, chosen ONLY from the "
            "CANDIDATES below (they are already ranked; prefer higher scores unless the request clearly favors another). "
            "For each pick give its id and one sentence (under 25 words) on why it fits, using only facts in that "
            "candidate's line. Never mention songs that are not in the list. Then write a one-sentence summary to the listener.\n"
            f"Listener profile: {json.dumps({k: v for k, v in profile.items() if k != 'note_matches'})}\n"
            "CANDIDATES:\n" + "\n".join(lines)
        )

    def _template_reason(self, song: Dict, why: str) -> str:
        """Fallback explanation: the top scoring reasons plus the first sentence of the song's notes."""
        note = self.knowledge.song_notes.get(song["id"])
        first = note.text.split(". ")[0].rstrip(".") + "." if note else ""
        reasons = "; ".join(why.split("; ")[:2])
        return f"{first} Matches: {reasons}."

    @staticmethod
    def _template_summary(profile: Dict) -> str:
        """Fallback one-line summary built from the profile."""
        style = " ".join(p for p in (profile.get("mood"), profile.get("genre")) if p)
        text = f"Here are my picks for {style} music" if style else "Here are my picks"
        if profile.get("activity"):
            text += f" for {profile['activity']}"
        clean = " (clean lyrics only)" if profile.get("exclude_explicit") else ""
        return f"{text}{clean}."

    def verify(self, picks: List[Pick], candidates: List, profile: Dict) -> Dict[str, bool]:
        """Self-check the answer: real candidate ids, 3-5 unique picks, explicit filter honored, no invented songs."""
        candidate_ids = {s["id"] for s, _, _ in candidates}
        ids = [p.song.get("id") for p in picks]
        own_titles = {p.song.get("id"): p.song.get("title", "").lower() for p in picks}
        mentions_other = False
        for pick in picks:
            text = pick.why.lower()
            for title, song_id in self.titles.items():
                if song_id != pick.song.get("id") and title in text and title != own_titles.get(pick.song.get("id")):
                    mentions_other = True
        return {
            "ids_from_candidates": all(i in candidate_ids for i in ids),
            "three_to_five_unique_picks": 3 <= len(set(ids)) == len(ids) <= 5 or (len(candidates) < 3 and len(ids) == len(candidates)),
            "explicit_filter_honored": not (profile.get("exclude_explicit") and any(p.song.get("explicit") for p in picks)),
            "reasons_present": all(len(p.why.split()) >= 3 for p in picks),
            "no_other_songs_mentioned": not mentions_other,
        }

    # -- step 5: confidence ------------------------------------------------------------------

    def confidence(self, profile: Dict, candidates: List, parse_mode: str, compose_mode: str, notes: List[str]) -> Tuple[float, str]:
        """How well the best candidate covers what was asked, discounted for fallbacks and genre gaps."""
        if not candidates:
            return 0.0, "low"
        possible = 0.0
        genre = profile.get("genre")
        if genre:
            possible += 2.0 if self.knowledge.in_catalog(genre) else 1.0
        possible += 1.0 if profile.get("mood") else 0.0
        possible += 1.5 if "energy" in profile else 0.0
        possible += 0.5 if "instrumentalness" in profile else 0.0
        possible += 0.5 * len(profile.get("mood_tags", []))
        possible += 0.75 if profile.get("note_matches") else 0.0
        strength = min(candidates[0][1] / possible, 1.0) if possible else 0.0
        factor = 1.0
        factor *= 0.9 if parse_mode == "rules" else 1.0
        factor *= 0.9 if compose_mode == "template" else 1.0
        factor *= 0.8 if genre and not self.knowledge.in_catalog(genre) else 1.0
        factor *= 0.85 if any(n.startswith("unknown genre") for n in notes) else 1.0
        value = round(strength * factor, 2)
        return value, "high" if value >= 0.7 else "medium" if value >= 0.45 else "low"

    # -- logging -----------------------------------------------------------------------------

    def _step(self, result: Result, step: str, level: str = "info", **data) -> None:
        """Append a step to the trace and write it to the log file."""
        entry = {"step": step, **data}
        result.trace.append(entry)
        getattr(self.logger, level)(json.dumps({"request": result.request[:80], **entry}, default=str))
