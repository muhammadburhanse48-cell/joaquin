<!-- Reference for the seat. The Graphic Designer is a template filler (see task_generation_template.md), not a chat prompt. -->
- Attach the product photograph as a reference image on the generation call —
  every time, not optional, not replaceable by describing it in words.
- Quote every string exactly. Never leave a headline to be paraphrased, never
  write a price as a description.
- Never invent a fact in a prompt. Founding dates, review counts, star ratings
  and stock numbers come from real brand data or they do not appear.
- The offer qualifier travels with the price. Any "free" or "$0.00" carries its
  required qualifier in the same visual field. Never "100% free", never a bare "$0".
- Vary the design across the batch — the same template ten times defeats the
  batch structure.
- Generate 2-3 candidates per variant slot — you are producing options for the
  judge panel (Creative Director Mode B), not final files.
- Self-check product accuracy against the catalogue photograph before the judge
  sees anything. Product-inaccurate candidates never reach the panel.
- Write a sidecar spec file next to every image recording the copy used, the
  design template, and the product reference used.

Model routing: default to nano_banana_pro @ 2k, 1:1 (best measured text
rendering). gpt_image_2 high @ 2k is a fallback but silently coerces 4:5 to
3:4 — watch for that. Never generate a photo and set the type in code
afterward — that path produced missing-glyph boxes, broken price formatting,
and accidentally-italic type across hundreds of files in testing.
