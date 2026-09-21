<!-- GAP-FILL: the client supplies the brief template but no task prompt for expanding concepts into briefs; this wrapper task is orchestration glue. -->
Expand concept {{concept_number}} of batch B{{batch}} into exactly {{variants}} creative brief(s): one brief per variant (V1 to V{{variants}}), each using EXACTLY the brief template below and starting with its own '# Creative Brief' title line. Each variant must differ from its siblings on at least three variation axes and the variants must be visibly distinct at thumbnail size. 'Copy slots for the image' must hold the exact strings that will be baked on the image. Do not write generation prompts.

--- THE CONCEPT ROW ---
{{concept_row}}
--- BRAND / OFFER / QUALIFIER ---
{{offer}}
--- PERSONA CARDS ---
{{persona_cards}}
--- CUSTOMER LANGUAGE ---
{{customer_language}}
--- ANGLE BANK ---
{{angle_bank}}
--- VISUAL PATTERN LIBRARY ---
{{pattern_library}}
--- SWIPE VAULT MANIFEST ---
{{swipe_manifest}}
--- CREATIVE LEDGER ---
{{creative_ledger}}
--- BRIEF TEMPLATE ---
One brief per creative. One screen. It is the single source production works
from, and it is what makes a result readable later.

# Creative Brief — <NN>_<Brand>_<Concept>_v<N>

Batch: B<NN>   Date: YYYY-MM-DD
Type: [ ] Iteration of winner <which>          [ ] Net-new bet   (batch ≈ 70/30)

## The bet
- Hypothesis: if we show <audience> <message>, then <expected outcome>,
  because <evidence>.
- Success metric & floor: CPA ≤ <X> at ≥ <spend floor>
- Awareness stage / persona: <stage> / <persona card ref>

## The variables
- Hook (≤5 words, baked on image): "<hook>"
- Angle: <angle + family>
- Format archetype: <from format-radar / pattern library>
- Proven-concept basis: adapted from <competitor or own winner>
  evidence: <tier + figure> — differentiated by <how>
- Scene intent: <setting, focal point, composition, where the clear zone is>
- Proof device: <demo / before-after / number / review / authority / guarantee>
- CTA: <cta>

## Variation axes for this variant (must differ from siblings on ≥3)
setting: <…> composition: <…> camera: <…> light: <…>
hook mechanism: <…> proof device: <…> format archetype: <…>

## Customer language to use (verbatim)
- "<quote>"    · "<quote>"

## Style references
- swipe-vault <niche>/<NN> — because <the manifest's reason>
- swipe-vault <niche>/<NN> — because <reason>
  Style and layout conditioning ONLY. Never the competitor's product or logo.

## Copy slots for the image
eyebrow: "…"  headline: "…"   proof: "…"   was: "…"  now: "…"

## Compliance notes
<claims that will need human review, flagged not blocked>

Variation axes to pick from: setting/world, composition, camera/lens,
light/mood, hook mechanism, proof device, format archetype. Each variant
of a concept must diverge on at least three of these, and V1/V2/V3 must be
visibly distinct at thumbnail size.

--- THE CRITIC'S NAMED FIX (apply exactly this one change, nothing else) ---
{{psych_fix}}
--- CURRENT BRIEFS FOR THIS CONCEPT ---
{{current_briefs}}
