"""Shared isolated runtime for every pipeline seat.

A seat call is stateless: one system prompt, one user message built only from the
explicit evidence dict, one fresh API request. No history is kept or forwarded.
That is what makes Law 2 ("the critic is never the author") enforceable.
"""

from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.schemas import output_instructions, schema_for

PROMPTS_ROOT = Path(__file__).resolve().parent / "prompts"

_SLOT = re.compile(r"\{\{([a-z_0-9]+)\}\}")
_COMMENT = re.compile(r"<!--.*?-->\s*", re.S)

# Author context a critic must never see (Law 2). Keys are checked by name; values are
# checked for the brief template's own markers so a brief pasted under an innocent key
# is still caught.
FORBIDDEN_KEYS = ("brief", "hypothesis", "rationale", "director_notes")
BRIEF_MARKERS = ("# Creative Brief —", "## The bet", "director_notes")


def create_shared_client(max_parallel: int = 4) -> Any:
    """One Anthropic client for every seat call a Pipeline makes: `anthropic.Anthropic`'s sync
    client is thread-safe (seat calls run via asyncio.to_thread, real OS threads), so sharing
    it avoids spinning up a fresh httpx connection pool per call. Sized to `max_parallel` and
    given an explicit timeout — with none, a hung request can hold a semaphore slot forever,
    which becomes a real deadlock once independent stages share that semaphore (Phase 1)."""
    from dotenv import load_dotenv

    load_dotenv()
    try:
        import anthropic
        import httpx2  # anthropic 1.x is built on httpx2 and rejects httpx objects
    except ImportError as exc:
        raise RuntimeError(
            "anthropic>=1.0 is required to run seats; install requirements.txt"
        ) from exc
    http_client = anthropic.DefaultHttpxClient(
        limits=httpx2.Limits(max_connections=max(10, 2 * max_parallel),
                             max_keepalive_connections=max_parallel),
        timeout=httpx2.Timeout(900.0, connect=10.0),
    )
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), max_retries=4,
                               http_client=http_client)


class IsolationViolation(ValueError):
    """Author context reached a critic seat. The review is refused."""


class MissingEvidence(ValueError):
    """A prompt slot had no evidence, or evidence was supplied that no slot uses."""


class SeatOutputError(RuntimeError):
    """The model's reply is unusable: truncated at max_tokens, refused, or not the schema."""


@dataclass
class SeatResult:
    seat_name: str
    output_text: str
    raw_response: Any
    #: The parsed JSON object for a structured task (agents/schemas.py); None otherwise.
    data: Any = None


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
    #: Calls are streamed, so a high cap costs nothing unless the model actually writes that much.
    max_tokens = 16000

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
        """Fallback for a seat constructed with no client (direct/manual use). No connection
        pool sizing or explicit timeout — a Pipeline should use create_shared_client instead,
        one client for every seat call it makes."""
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
        return self.run(self.task_prompt(task_file), evidence,
                        schema=schema_for(self.seat_name, task_file), **kwargs)

    def run(
        self,
        task_prompt_template: str,
        evidence: dict[str, Any],
        attached_images: list[Any] | None = None,
        max_tokens: int | None = None,
        schema: dict | None = None,
    ) -> SeatResult:
        """Run one isolated request; no history is retained or forwarded.

        attached_images: raw bytes, or (label, bytes) pairs. Labels are sent as text
        immediately before their image so a critic can name slots and candidates.
        schema: a JSON schema the reply is constrained to (structured outputs); the parsed
        object is returned as SeatResult.data.
        """
        if self.critic:
            assert_isolated_evidence(evidence)
        filled = self.fill_template(task_prompt_template, evidence)
        if schema:
            filled += "\n\n" + output_instructions(schema)
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
        cap = max_tokens or self.max_tokens
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": cap,
            "system": self.system_prompt,
            "messages": [{"role": "user", "content": content}],
        }
        if schema:
            params["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        # Streamed so long outputs (the copy sheet runs 10k+ tokens) never hit an HTTP timeout.
        with self.client.messages.stream(**params) as stream:
            response = stream.get_final_message()
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        stop = getattr(response, "stop_reason", None)
        if stop == "max_tokens":
            raise SeatOutputError(f"{self.seat_name}: reply was cut off at max_tokens={cap}")
        if stop == "refusal":
            raise SeatOutputError(f"{self.seat_name}: the model refused the request")
        data = None
        if schema:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise SeatOutputError(f"{self.seat_name}: structured reply is not JSON: {exc}") from exc
        return SeatResult(self.seat_name, text, response, data)

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
