# Seat: Graphic Designer
Source: Doc 03 — Static Creative Batches
Role: Author. Writes generation prompts, generates 2-3 candidates per slot,
executes every regeneration fix. Never scores or ships its own candidates.

Note: this is a TEMPLATE you fill programmatically per creative, not a chat
prompt you send conversationally. Attach the real product photograph to the
generation call every time — never describe the product in words only.

---

## TEMPLATE — Image generation

[1 — INTENT]
A premium, fully art-directed direct-response advertisement. Square 1:1
composition, 2048×2048. A COMPOSED, designed piece — built ground, cut-out
product with its own contact shadow, overlapping badges, leader lines, real
type hierarchy. Not a photograph with a text block laid over it.

[2 — PRODUCT — accuracy clause, always first]
The product must match the attached reference image EXACTLY: <name the specific
features — artwork, colourway, shape, handles, hardware, stitching, finish>.
Do NOT substitute a different <product noun>. Do NOT redesign, restyle or
"improve" any part of it. Real-photography look, true materials and micro-texture,
physically accurate light and shadow. No CGI, plastic, waxy or over-smooth render.

[3 — BACKGROUND]
A built ground: <e.g. a soft vertical gradient from #F7F3EC to #E8DFD2, with a
single large tonal arc behind the product>. This is a constructed studio ground,
NOT a photograph of a room.

[4 — TYPOGRAPHY — every string in quotes, exactly as it must appear]
Eyebrow, small letterspaced caps, top-left:    "<EYEBROW>"
Headline, large, two lines, upper-left third:   "<HEADLINE>"
Proof badge, inside a disc overlapping the product top-right: "<PROOF>"
Offer lockup, lower-right: struck-through "<WAS>" beside "<NOW>",
  with the qualifier "<QUALIFIER>" directly beneath it in the same field.
Set every word correctly. Do not paraphrase, translate or re-word any string.

[5 — STYLE]
<Niche tone: e.g. premium, restrained, editorial>. Palette limited to three
colours: <#hex ground> / <#hex accent> / <#hex contrast>. At most two type
families. One dominant focal point. Keep all text and key visuals inside a 5%
inner margin. Audience: <persona one-liner from the card's visual world>.

[6 — NEGATIVE]
No garbled, warped or duplicated text. No invented logos, brand marks or
watermarks. No starbursts, lens flare, gradient mush or busy background. No fake
UI or buttons. No substituted product. No extra products in frame.

---

## Non-negotiable prompt rules (apply to every generation call)

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
