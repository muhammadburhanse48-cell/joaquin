"""Shared isolated runtime for every pipeline seat."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SeatResult:
    seat_name: str
    output_text: str
    raw_response: Any


class BaseSeat:
    """One prompt plus one explicit evidence base per fresh API call."""

    def __init__(
        self,
        seat_name: str,
        prompts_dir: Path,
        model: str = "claude-sonnet-4-6",
        client: Any | None = None,
    ) -> None:
        self.seat_name = seat_name
        self.prompts_dir = Path(prompts_dir)
        self.system_prompt = (self.prompts_dir / "system.md").read_text()
        self.model = model
        self.client = client or self._create_client()

    @staticmethod
    def _create_client() -> Any:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic is required to run seats; install requirements.txt"
            ) from exc
        return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def run(
        self,
        task_prompt_template: str,
        evidence: dict[str, Any],
        attached_images: list[bytes] | None = None,
        max_tokens: int = 8000,
    ) -> SeatResult:
        """Run one isolated request; no history is retained or forwarded."""
        filled_prompt = self._fill_template(task_prompt_template, evidence)
        content: list[dict[str, Any]] = [{"type": "text", "text": filled_prompt}]
        for image_bytes in attached_images or []:
            content.insert(
                0,
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": self._b64(image_bytes),
                    },
                },
            )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=self.system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        return SeatResult(self.seat_name, text, response)

    @staticmethod
    def _fill_template(template: str, evidence: dict[str, Any]) -> str:
        output = template
        for key, value in evidence.items():
            output = output.replace(f"<{key}>", str(value))
        return output

    @staticmethod
    def _b64(data: bytes) -> str:
        return base64.b64encode(data).decode()


def assert_isolated_evidence(evidence: dict[str, Any]) -> None:
    """Reject author context before a critic request can reach the API."""
    forbidden = ("brief", "hypothesis", "rationale", "director_notes")
    leaked = [key for key in evidence if any(token in key.lower() for token in forbidden)]
    if leaked:
        raise ValueError(f"critic evidence contains forbidden author context: {leaked}")