"""Graphic Designer — fills the image-generation template. Never scores or ships candidates.

This seat is a template filler, not a chat prompt: no model call is made here. The real
product photograph must travel with every generation call (never described in words only).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from agents.base_seat import BaseSeat

_BANNED_FREE = re.compile(r"100%\s*free|totally free|absolutely free|no cost", re.I)
_BARE_ZERO = re.compile(r"\$0(?:\.00)?(?!\d)")


@dataclass
class GenerationRequest:
    prompt: str
    sidecar: dict  # copy used, design template, product reference — written next to the image


class GraphicDesigner(BaseSeat):
    def __init__(self, **kwargs):
        super().__init__("graphic_designer", **kwargs)

    def build_prompt(self, spec: dict, product_reference: str) -> GenerationRequest:
        """spec holds every {{slot}} of task_generation_template.md."""
        if not product_reference:
            raise ValueError("a product photograph reference is required on every generation")
        self._check_offer_strings(spec)
        template, spec = self._drop_absent_elements(self.task_prompt("task_generation_template.md"), spec)
        prompt = self.fill_template(template, spec)
        sidecar = {
            "copy": {k: spec.get(k, "") for k in ("eyebrow", "headline", "proof", "was", "now", "qualifier")},
            "design_template": "task_generation_template.md",
            "product_reference": product_reference,
        }
        return GenerationRequest(prompt, sidecar)

    @staticmethod
    def _drop_absent_elements(template: str, spec: dict) -> tuple[str, dict]:
        """A creative may have no eyebrow, proof badge, old price or offer lockup. Remove that
        element from the template rather than send an empty quoted string for the image model to
        fill with something invented."""
        spec = dict(spec)
        blank = lambda k: not str(spec.get(k, "")).strip()  # noqa: E731
        if blank("eyebrow"):
            template = re.sub(r"(?m)^Eyebrow[^\n]*\{\{eyebrow\}\}[^\n]*\n", "", template)
            spec.pop("eyebrow", None)
        if blank("proof"):
            template = re.sub(r"(?m)^Proof badge[^\n]*\{\{proof\}\}[^\n]*\n", "", template)
            spec.pop("proof", None)
        if blank("now"):  # no price shown: no lockup, so no qualifier line either
            template = re.sub(r"(?ms)^Offer lockup.*?same field\.\n", "", template)
            for k in ("now", "was", "qualifier"):
                spec.pop(k, None)
        elif blank("was"):
            template = template.replace('struck-through "{{was}}" beside ', "")
            spec.pop("was", None)
        return template, spec

    @staticmethod
    def _check_offer_strings(spec: dict) -> None:
        strings = " ".join(str(spec.get(k, "")) for k in ("headline", "proof", "was", "now", "eyebrow"))
        if _BANNED_FREE.search(strings):
            raise ValueError("banned free-offer phrasing on the image (e.g. '100% free')")
        if _BARE_ZERO.search(strings) and not str(spec.get("qualifier", "")).strip():
            raise ValueError("a bare $0 must carry its qualifier in the same visual field")
