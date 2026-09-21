<!-- ORCHESTRATION: evidence block added so the call is stateless. -->
--- TEARDOWN ROWS ---
{{teardown_rows}}
--- PATTERN LIBRARY (its 'use first' list) ---
{{pattern_library}}
--- EVIDENCE PER IMAGE ---
{{evidence_per_image}}

From the {{n_images}} images torn down, select the 8-15 that become the permanent swipe
vault for this niche.

Curation bar, in order:
1. Strongest signal tier available
2. ARCHETYPE DIVERSITY — not five copies of one format
3. Execution a top-1% direct-response brand would ship
4. At least one exemplar per pattern the library marked "use first"

For each selection give me a manifest entry:
{
"file": "<NN>_<archetype>_<advertiser>.png",
"source_ad_id": "...", "source_url": "...", "advertiser": "...",
"format_archetype": "...", "signal_tier": "T2|T3",
"evidence": "<the actual figure — days running, variant count, or EU spend>",
"why_it_earned_its_slot": "<one sentence, specific to this image>",
"date_added": "YYYY-MM-DD"
}

Then tell me which images you REJECTED and the one-line reason each — I want to
know what the bar excluded, not just what it let through.
