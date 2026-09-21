"""Shared isolated runtime for every pipeline seat.

A seat call is stateless: one system prompt, one user message built only from the
explicit evidence dict, one fresh API request. No history is kept or forwarded.
That is what makes Law 2 ("the critic is never the author") enforceable.
"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROMPTS_ROOT = Path(__file__).resolve().parent / "prompts"

_SLOT = re.compile(r"\{\{([a-z_0-9]+)\}\}")
_COMMENT = re.compile(r"<!--.*?-->\s*", re.S)

# Author context a critic must never see (Law 2). Keys are checked by name; values are
# checked for the brief template's own markers so a brief pasted under an innocent key
# is still caught.
FORBIDDEN_KEYS = ("brief", "hypothesis", "rationale", "director_notes")
BRIEF_MARKERS = ("# Creative Brief —", "## The bet", "director_notes")


class IsolationViolation(ValueError):
    """Author context reached a critic seat. The review is refused."""


class MissingEvidence(ValueError):
    """A prompt slot had no evidence, or evidence was supplied that no slot uses."""


@dataclass
class SeatResult:
    seat_name: str
    output_text: str
    raw_response: Any


def assert_isolated_evidence(evidence: dict[str, Any]) -> None:
    """Reject author context before a critic request can reach the API."""
    leaked = [k for k in evidence if any(tok in k.lower() for tok in FORBIDDEN_KEYS)]
    leaked += [
        f"{k} (value contains brief text)"
        for k, v in evidence.items()
        if isinstance(v, str) and any(marker in v for marker in BRIEF_MARKERS)
    ]
    if leaked:
        raise IsolationViolation(
            f"critic evidence contains forbidden author context: {leaked}"
        )


def _media_type(data: bytes) -> str:
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


class BaseSeat:
    """One system prompt plus one explicit evidence base per fresh API call."""

    #: Critic seats assert isolation inside run(), not only in their wrappers.
    critic = False
    #: Seats that never call the model (template fillers) override this.
    max_tokens = 8000

    def __init__(
        self,
        seat_name: str,
        prompts_dir: Path | None = None,
        model: str = "claude-sonnet-4-6",
        client: Any | None = None,
        system_file: str = "system.md",
    ) -> None:
        self.seat_name = seat_name
        self.prompts_dir = Path(prompts_dir or PROMPTS_ROOT / seat_name)
        self.system_prompt = self._load(self.prompts_dir / system_file)
        self.model = model
        self._client = client

    # -- prompts ---------------------------------------------------------------
    @staticmethod
    def _load(path: Path) -> str:
        return _COMMENT.sub("", path.read_text()).strip()

    def task_prompt(self, task_file: str) -> str:
        return self._load(self.prompts_dir / task_file)

    # -- client ----------------------------------------------------------------
    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = self._create_client()
        return self._client

    @staticmethod
    def _create_client() -> Any:
        from dotenv import load_dotenv

        load_dotenv()
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic is required to run seats; install requirements.txt"
            ) from exc
        return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), max_retries=4)

    # -- running ---------------------------------------------------------------
    def run_task(self, task_file: str, evidence: dict[str, Any], **kwargs: Any) -> SeatResult:
        return self.run(self.task_prompt(task_file), evidence, **kwargs)

    def run(
        self,
        task_prompt_template: str,
        evidence: dict[str, Any],
        attached_images: list[Any] | None = None,
        max_tokens: int | None = None,
    ) -> SeatResult:
        """Run one isolated request; no history is retained or forwarded.

        attached_images: raw bytes, or (label, bytes) pairs. Labels are sent as text
        immediately before their image so a critic can name slots and candidates.
        """
        if self.critic:
            assert_isolated_evidence(evidence)
        filled = self.fill_template(task_prompt_template, evidence)
        content: list[dict[str, Any]] = []
        for item in attached_images or []:
            label, data = item if isinstance(item, tuple) else (None, item)
            if label:
                content.append({"type": "text", "text": f"[{label}]"})
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": _media_type(data),
                           "data": self._b64(data)},
            })
        content.append({"type": "text", "text": filled})
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=self.system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        return SeatResult(self.seat_name, text, response)

    @staticmethod
    def fill_template(template: str, evidence: dict[str, Any]) -> str:
        """Fill {{slots}}. Every slot needs evidence; every evidence key needs a slot.

        Strict on purpose: an unfilled slot means the model works from nothing (a seat
        guessing), and an unused key means the wrong evidence was routed to the wrong seat.
        """
        wanted = set(_SLOT.findall(template))
        missing = sorted(k for k in wanted if not str(evidence.get(k, "")).strip())
        if missing:
            raise MissingEvidence(f"no evidence supplied for slots: {missing}")
        unused = sorted(set(evidence) - wanted)
        if unused:
            raise MissingEvidence(f"evidence keys not used by this prompt: {unused}")
        return _SLOT.sub(lambda m: str(evidence[m.group(1)]), template)

    @staticmethod
    def _b64(data: bytes) -> str:
        return base64.b64encode(data).decode()
