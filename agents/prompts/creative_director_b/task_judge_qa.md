CONTEXT YOU GET (and nothing else):
--- THE IMAGES ---   [attached as image(s) above]
--- THE REAL PRODUCT PHOTOGRAPH ---   [attached as image(s) above]
--- PERSONA CARD for the target ---   {{persona_card}}
--- BRAND RULES: palette, banned words, offer qualifier ---   {{brand_rules}}
--- THE COMPETITOR EXEMPLAR this is judged against ---   [attached as image(s) above]
{{exemplar_evidence}}
--- THE LANDING PAGE PROMISE ---   {{landing_page_promise}}

--- ORCHESTRATION: MACHINE-READABLE VERDICTS (required) ---
After your normal output above, append ONE fenced ```json block containing exactly:
[{"slot": "<slot id exactly as labelled on the images>", "winner": "<candidate label>", "verdict": "SHIP"|"REGEN", "lever_scores": [<7 integers 0-2, in the order the levers are listed>], "hard_gate_failures": ["<name each failed hard gate, or leave empty>"], "fix": "<specific evidence-tied fix, empty for SHIP>", "fix_type": "regenerate"|"recompose"|""}]  (one object per slot)
The orchestrator enforces the gates from this block; the prose above stays authoritative for the human reader.
