"""Writing-style profile built from the user's own past letters (no model involved)."""
from __future__ import annotations

import json
import re

from app.core.config import DATA_DIR
from app.models.schemas import VoiceProfile

SAMPLES_PATH = DATA_DIR / "writing_samples.json"
SEPARATOR = re.compile(r"^\s*-{3,}\s*$", re.M)
MAX_SAMPLES = 5
CONTRACTION = re.compile(r"\b\w+['’](?:s|t|re|ve|ll|d|m)\b|\b[cdjlmnst]['’]\w+", re.I)
CASUAL = ("lol", "awesome", "super", "cool", "hey", "thrilled", "stoked")
FIRST_PERSON = re.compile(r"\b(?:i|my|me|je|mon|ma|mes|j['’])\b", re.I)


def split_samples(raw: str) -> list[str]:
    parts = [p.strip() for p in SEPARATOR.split(raw or "")]
    return [p for p in parts if len(p) >= 80][:MAX_SAMPLES]


def load_samples() -> list[str]:
    try:
        data = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [s for s in data if isinstance(s, str)] if isinstance(data, list) else []


def save_samples(samples: list[str]) -> None:
    SAMPLES_PATH.write_text(json.dumps(samples, ensure_ascii=False, indent=1), encoding="utf-8")


def _openers(samples: list[str]) -> list[str]:
    openers = []
    for sample in samples:
        paragraphs = [p for p in re.split(r"\n\s*\n", sample) if p.strip()]
        body = paragraphs[1] if len(paragraphs) > 1 and len(paragraphs[0]) < 60 else (paragraphs[0] if paragraphs else "")
        words = body.split()[:6]
        if words:
            openers.append(" ".join(words))
    return openers


def analyze(samples: list[str]) -> VoiceProfile:
    samples = [s for s in samples if s and s.strip()]
    if not samples:
        return VoiceProfile()
    text = " ".join(samples)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    words = re.findall(r"[\w'’-]+", text)
    avg = len(words) / max(1, len(sentences))
    low = text.casefold()
    contractions = len(CONTRACTION.findall(text))
    first_person = len(FIRST_PERSON.findall(text)) / max(1, len(words))
    exclamations = text.count("!")
    technical = sum(low.count(t) for t in ("api", "database", "system", "software", "python", "model", "pipeline", "data"))
    long_words = sum(1 for w in words if len(w) > 9) / max(1, len(words))

    notes = [
        f"Average sentence length is about {round(avg)} words; keep sentences in that range.",
        "Contractions are used; allow them." if contractions >= 3 else "Avoid contractions.",
        "Write mostly in the first person." if first_person > 0.04 else "Keep first-person phrasing sparse.",
    ]
    if exclamations:
        notes.append("Exclamation marks appear occasionally; do not add more.")
    return VoiceProfile(
        formality="conversational" if contractions >= 3 or any(c in low for c in CASUAL) else "professional",
        directness="high" if avg < 22 else "moderate",
        technicality="high" if technical >= 4 else "moderate",
        enthusiasm="high" if exclamations >= 2 else "moderate",
        sentence_length="short" if avg < 15 else "medium" if avg < 25 else "long",
        vocabulary="technical but accessible" if long_words < 0.12 else "formal and precise",
        average_sentence_words=round(avg, 1),
        uses_contractions=contractions >= 3,
        sample_count=len(samples),
        typical_openers=list(dict.fromkeys(_openers(samples)))[:3],
        style_notes=notes,
    )

