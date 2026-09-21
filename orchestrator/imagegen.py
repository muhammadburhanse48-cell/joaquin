"""Where candidate images come from.

The client's stack names nano_banana_pro (Gemini) at 2k 1:1 with the product photo attached,
and gpt_image_2 as a fallback. Neither key is configured in this repo, so the default
source is ManualImageSource: the pipeline writes each generation prompt to disk, stops with
AwaitingInput, and resumes when candidate files appear. Plug a real generator in by
implementing ImageSource.generate() and passing it to Pipeline(image_source=...).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .errors import AwaitingInput

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


class ImageSource(Protocol):
    def generate(self, prompt: str, product_photo: Path, n: int, out_dir: Path) -> list[Path]:
        """Write n candidate images (2048x2048, 1:1) into out_dir and return their paths.

        Implementations MUST attach product_photo as a reference image on the call.
        """


class ManualImageSource:
    def generate(self, prompt: str, product_photo: Path, n: int, out_dir: Path) -> list[Path]:
        raise AwaitingInput(f"drop {n} candidate images into {out_dir}")


def candidates(out_dir: Path) -> list[Path]:
    return sorted(p for p in out_dir.glob("*") if p.suffix.lower() in IMAGE_SUFFIXES) if out_dir.exists() else []
