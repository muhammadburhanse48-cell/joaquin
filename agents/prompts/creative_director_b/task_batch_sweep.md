<!-- ORCHESTRATION: the client's sweep names 'the copy sheet' but has no slot for it. -->
Here are all {{n_creatives}} shipping creatives for batch B{{batch}}, plus the copy sheet.

Run the BATCH-LEVEL checks. Individual creatives can each pass while the batch
is broken. Report each as PASS or FAIL with the specific files named:

1. Headline sameness — is more than a third of the batch sharing a headline or
   an opening phrase? List the clusters.
2. Perceptual duplicates — any two creatives that are effectively the same
   image? Two creatives sharing a photo ARE the same creative.
3. Format spread — count distinct format archetypes. Must be ≥4. List them.
4. Missing glyphs — any box, tofu square or broken character, any file.
5. Dead space — any file where a large region does nothing, including the
   case where three quadrants are empty.
6. Banned terms — check against this list: {{banned_words}}
7. Offer qualifier — every "free" or "$0" carries "{{qualifier}}" in the SAME
   visual field. Name any that don't.
8. Currency — correct for {{market}}. Name any that aren't.
9. Product presence — right product, actually in frame, in every file.
10. Proof devices — how many of the {{n_creatives}} carry one? Name the ones that don't.
    (A missing proof device predicts a weaker creative.)

Any FAIL means the batch does not stage until it's fixed. Don't soften this.

--- THE COPY SHEET ---
{{copy_sheet}}

--- ORCHESTRATION: MACHINE-READABLE SWEEP RESULT (required) ---
After your normal output above, append ONE fenced ```json block containing exactly:
{"checks": [{"n": <1-10>, "result": "PASS"|"FAIL", "files": ["<named files>"], "detail": "<one line>"}]}
The orchestrator enforces the gates from this block; the prose above stays authoritative for the human reader.
