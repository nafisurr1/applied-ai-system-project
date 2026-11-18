"""Retrieval over the knowledge base: BM25 search plus structured lookups into the genre and activity guides."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "i", "in", "is", "it", "its",
    "me", "my", "of", "on", "or", "so", "some", "something", "that", "the", "this", "to", "want", "with",
    "you", "your", "can", "could", "please", "give", "play", "music", "songs", "song", "like", "need",
}
FIELD_LINE = re.compile(r"^([A-Z][A-Za-z ]+):\s*(.+)$")


def tokenize(text: str) -> List[str]:
    """Lowercase word tokens with stopwords removed."""
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


@dataclass
class Chunk:
    """One "## " section of a knowledge file."""
    source: str  # file stem, e.g. "genre_guide"
    title: str
    text: str
    fields: Dict[str, str] = field(default_factory=dict)

    def field_list(self, name: str) -> List[str]:
        """A comma-separated field as a list of lowercase values."""
        return [v.strip().lower() for v in self.fields.get(name, "").split(",") if v.strip()]


def load_chunks(knowledge_dir: Path = KNOWLEDGE_DIR) -> List[Chunk]:
    """Split every knowledge markdown file into one chunk per "## " heading."""
    chunks = []
    for path in sorted(knowledge_dir.glob("*.md")):
        for section in re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.M)[1:]:
            title, _, body = section.partition("\n")
            fields = {}
            for line in body.splitlines():
                match = FIELD_LINE.match(line.strip())
                if match:
                    fields[match[1].strip().lower()] = match[2].strip()
            chunks.append(Chunk(path.stem, title.strip(), body.strip(), fields))
    return chunks


class Retriever:
    """BM25 ranking over knowledge chunks (title + body), filterable by source file."""

    def __init__(self, chunks: Optional[List[Chunk]] = None, k1: float = 1.5, b: float = 0.75):
        """Index the chunks once."""
        self.chunks = chunks if chunks is not None else load_chunks()
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(c.title + " " + c.text)) for c in self.chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = sum(self.lengths) / max(len(self.lengths), 1)
        df = Counter(term for d in self.docs for term in d)
        n = len(self.docs)
        self.idf = {term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    def search(self, query: str, k: int = 4, sources: Optional[List[str]] = None, min_score: float = 0.5) -> List[Tuple[Chunk, float]]:
        """Top k chunks for the query, best first, ignoring weak matches below min_score."""
        terms = tokenize(query)
        scored = []
        for chunk, doc, length in zip(self.chunks, self.docs, self.lengths):
            if sources and chunk.source not in sources:
                continue
            score = 0.0
            for term in terms:
                tf = doc.get(term, 0)
                if tf:
                    score += self.idf[term] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / self.avg_len))
            if score >= min_score:
                scored.append((chunk, score))
        return sorted(scored, key=lambda item: -item[1])[:k]


class Knowledge:
    """Structured views of the guides: genre aliases and relations, activity targets, song notes by id."""

    def __init__(self, chunks: Optional[List[Chunk]] = None):
        """Build lookup tables from the knowledge chunks."""
        chunks = chunks if chunks is not None else load_chunks()
        self.genres = {c.title.lower(): c for c in chunks if c.source == "genre_guide"}
        self.activities = {c.title.lower(): c for c in chunks if c.source == "activity_guide"}
        self.song_notes = {}
        for c in chunks:
            if c.source == "song_notes":
                song_id = c.title.split(".", 1)[0]
                if song_id.isdigit():
                    self.song_notes[int(song_id)] = c
        self.genre_alias = {}
        for name, chunk in self.genres.items():
            self.genre_alias[name] = name
            for alias in chunk.field_list("aliases"):
                self.genre_alias.setdefault(alias, name)
        self.activity_alias = {}
        for name, chunk in self.activities.items():
            self.activity_alias[name] = name
            for alias in chunk.field_list("aliases"):
                self.activity_alias.setdefault(alias, name)

    @staticmethod
    def _key(text: str) -> str:
        """Normalize spelling for alias lookup ("Lo-Fi" -> "lo-fi", "R & B" -> "r&b")."""
        return re.sub(r"\s+", " ", str(text).strip().lower().replace(" & ", "&"))

    def canonical_genre(self, name: Optional[str]) -> Optional[str]:
        """Map any known spelling or alias to its guide genre, or None if unknown."""
        if not name:
            return None
        key = self._key(name)
        return self.genre_alias.get(key) or self.genre_alias.get(key.replace("-", " ")) or self.genre_alias.get(key.replace(" ", "-"))

    def in_catalog(self, genre: str) -> bool:
        """Whether the catalog has songs in this guide genre."""
        chunk = self.genres.get(genre)
        return bool(chunk) and chunk.fields.get("in catalog", "").lower() == "yes"

    def related_genres(self, genre: str) -> List[str]:
        """Catalog genres the guide lists as close to this one."""
        chunk = self.genres.get(genre)
        return [g for g in chunk.field_list("related") if self.in_catalog(g)] if chunk else []

    def canonical_activity(self, name: Optional[str]) -> Optional[str]:
        """Map an activity or alias to its guide entry, or None."""
        if not name:
            return None
        return self.activity_alias.get(self._key(name))

    def activity_targets(self, activity: str) -> Dict:
        """Energy, mood tags, instrumental and explicit guidance for an activity."""
        chunk = self.activities[activity]
        targets = {"mood_tags": chunk.field_list("mood tags")}
        energy = re.match(r"[\d.]+", chunk.fields.get("target energy", ""))
        if energy:
            targets["energy"] = float(energy[0])
        if chunk.fields.get("instrumental", "").lower().startswith("prefer"):
            targets["instrumentalness"] = 0.8
        explicit = chunk.fields.get("explicit", "").lower()
        if explicit.startswith("never"):
            targets["exclude_explicit"] = True
        elif explicit.startswith("avoid"):
            targets["allow_explicit"] = False
        return targets
