"""Conservative railway track-crossing detection from Hafnia VLM summaries.

The Gateway ``GET /api/Summaries/{id}`` payload documented in ``gateway-api.md``
returns text in ``Response``. It does not include a video frame, snapshot, or
image URL, and no other Gateway endpoint is documented for fetching a still
from XProtect. Evidence-frame helpers therefore only surface an image when a
payload actually contains one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

STATUS_CONFIRMED = "confirmed"
STATUS_NEGATIVE = "negative"
STATUS_UNCERTAIN = "uncertain"

# Explicit statements that a crossing did *not* happen, or the person stayed
# on the platform. Checked before any positive match.
_NEGATIVE_PATTERNS = (
    re.compile(r"\bno (?:track |railway )?crossing\b"),
    re.compile(r"\bno crossing (?:occurred|detected|took place|is visible|was visible|happened)\b"),
    re.compile(r"\bdid not (?:cross|step onto|enter the (?:tracks|rails))\b"),
    re.compile(r"\bdidn't (?:cross|step onto)\b"),
    re.compile(r"\bdoes not (?:cross|step onto)\b"),
    re.compile(r"\bdoesn't (?:cross|step onto)\b"),
    re.compile(r"\bnever (?:cross(?:ed|es)?|step(?:ped|s)? onto)\b"),
    re.compile(r"\bwithout (?:crossing|stepping onto)\b"),
    re.compile(r"\bnot (?:a |an )?(?:track |railway )?crossing\b"),
    re.compile(r"\bremained on (?:the )?platform\b"),
    re.compile(r"\bremains on (?:the )?platform\b"),
    re.compile(r"\bstayed on (?:the )?platform\b"),
    re.compile(r"\bstays on (?:the )?platform\b"),
    re.compile(r"\bstaying on (?:the )?platform\b"),
    re.compile(r"\bdid not (?:leave|exit) (?:the )?platform\b"),
    re.compile(r"\bno one (?:crossed|stepped onto)\b"),
    re.compile(r"\bperson remained on (?:the )?(?:platform|paving)\b"),
)

# Hedging / inability to confirm. Any of these blocks a confirmed alert.
_UNCERTAIN_PATTERNS = (
    re.compile(r"\bit is unclear\b"),
    re.compile(r"\bunclear (?:if|whether|that)\b"),
    re.compile(r"\buncertain\b"),
    re.compile(r"\bambiguous\b"),
    re.compile(r"\binconclusive\b"),
    re.compile(r"\bcannot (?:tell|determine|confirm|see|be confirmed)\b"),
    re.compile(r"\bcan't (?:tell|determine|confirm|see)\b"),
    re.compile(r"\bunable to (?:tell|determine|confirm|see)\b"),
    re.compile(r"\bno (?:clear|definitive) (?:evidence|indication|view|confirmation)\b"),
    re.compile(r"\bnot (?:enough|sufficient) (?:(?:evidence|information|detail) )?(?:to )?(?:confirm|determine)\b"),
    re.compile(r"\bappears to (?:have )?(?:step(?:ped)?|cross(?:ed)?)\b"),
    re.compile(r"\bseems to (?:have )?(?:step(?:ped)?|cross(?:ed)?)\b"),
    re.compile(r"\bmight have (?:stepped|crossed)\b"),
    re.compile(r"\bpossibly (?:stepped|crossed|a crossing)\b"),
    re.compile(r"\bcould have (?:stepped|crossed)\b"),
)

# Strong, affirmative crossing language. Mentioning "tracks" alone is not enough.
_POSITIVE_PATTERNS = (
    re.compile(r"\bsteps onto (?:the )?(?:railway )?(?:tracks|rails|track)\b"),
    re.compile(r"\bstepped onto (?:the )?(?:railway )?(?:tracks|rails|track)\b"),
    re.compile(r"\bstepping onto (?:the )?(?:railway )?(?:tracks|rails|track)\b"),
    re.compile(r"\bstepping onto and crossing (?:the )?rails\b"),
    re.compile(r"\bcrosses (?:the )?(?:railway )?(?:tracks|rails)\b"),
    re.compile(r"\bcrossed (?:the )?(?:railway )?(?:tracks|rails)\b"),
    re.compile(r"\bcrossing (?:the )?(?:railway )?(?:tracks|rails)\b"),
    re.compile(r"\bwalks across (?:the )?(?:railway )?(?:tracks|rails)\b"),
    re.compile(r"\bwalked across (?:the )?(?:railway )?(?:tracks|rails)\b"),
    re.compile(r"\bwalking across (?:the )?(?:railway )?(?:tracks|rails)\b"),
    re.compile(r"\bcrosses from (?:the )?(?:near |far |one )?platform\b"),
    re.compile(r"\bcrossed from (?:the )?(?:near |far |one )?platform\b"),
    re.compile(r"\btrack crossing\b"),
    re.compile(r"\bonto and crossing (?:the )?rails\b"),
)

_IMAGE_KEYS = (
    "Frame",
    "Image",
    "Snapshot",
    "Thumbnail",
    "EvidenceFrame",
    "FrameJpeg",
    "ImageBase64",
    "ImageUrl",
    "FrameUrl",
)


@dataclass(frozen=True)
class CrossingAssessment:
    """Result of rule-based classification of a Hafnia summary."""

    is_crossing: bool
    status: str
    description: str


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def concise_event_description(summary: str, *, max_chars: int = 280) -> str:
    """Return a short description taken from the Hafnia summary text."""
    text = " ".join((summary or "").split())
    if not text:
        return "A person stepped onto or crossed the railway tracks."

    sentences = re.split(r"(?<=[.!?])\s+", text)
    preferred = next(
        (
            sentence
            for sentence in sentences
            if _matches_any(sentence.lower(), _POSITIVE_PATTERNS)
        ),
        sentences[0],
    )
    if len(preferred) <= max_chars:
        return preferred
    return preferred[: max_chars - 1].rstrip() + "…"


def classify_track_crossing(summary: str) -> CrossingAssessment:
    """Classify a Hafnia summary as a confirmed crossing, a negative, or uncertain.

    Conservative rules:
    * Explicit "no crossing" / "remained on the platform" → not an alert.
    * Hedged or inconclusive language → not an alert.
    * Mere mention of tracks/rails without stepping onto or crossing them → not an alert.
    * Only clear affirmative crossing language, with none of the above, is confirmed.
    """
    text = (summary or "").strip()
    if not text:
        return CrossingAssessment(False, STATUS_UNCERTAIN, "")

    lower = text.lower()
    if _matches_any(lower, _NEGATIVE_PATTERNS):
        return CrossingAssessment(False, STATUS_NEGATIVE, concise_event_description(text))
    if _matches_any(lower, _UNCERTAIN_PATTERNS):
        return CrossingAssessment(False, STATUS_UNCERTAIN, concise_event_description(text))
    if _matches_any(lower, _POSITIVE_PATTERNS):
        return CrossingAssessment(True, STATUS_CONFIRMED, concise_event_description(text))
    return CrossingAssessment(False, STATUS_UNCERTAIN, concise_event_description(text))


def is_track_crossing_event(summary: str) -> bool:
    """True only when the summary is a confirmed railway track crossing."""
    return classify_track_crossing(summary).is_crossing


def _usable_image_value(value: Any) -> Optional[Any]:
    if value is None or value is False:
        return None
    if isinstance(value, (bytes, bytearray)) and value:
        return bytes(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.startswith(("http://", "https://", "data:image")):
            return stripped
        # Long base64 payloads are only treated as evidence when clearly tagged
        # by the caller key; a generic string is not an image.
        return None
    return None


def extract_evidence_frame(payload: Optional[dict[str, Any]]) -> Optional[Any]:
    """Return image bytes or an http(s) URL if the Gateway payload includes one.

    Typical completed summaries only contain ``Response`` text, in which case
    this returns ``None``. ``xprotect://`` URIs are not fetchable stills.
    """
    if not isinstance(payload, dict):
        return None

    candidates: list[Any] = []
    for key in _IMAGE_KEYS:
        if key in payload:
            candidates.append(payload.get(key))

    request = payload.get("Request")
    if isinstance(request, dict):
        for key in _IMAGE_KEYS:
            if key in request:
                candidates.append(request.get(key))

    response = payload.get("Response")
    if isinstance(response, dict):
        for key in _IMAGE_KEYS:
            if key in response:
                candidates.append(response.get(key))

    for value in candidates:
        image = _usable_image_value(value)
        if image is not None:
            return image
    return None
