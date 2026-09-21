EVIDENCE
--- THE DRAFT --- {{draft}}
--- PERSONA CARDS --- {{persona_cards}}
--- CUSTOMER LANGUAGE (the word bank every claim must trace to) --- {{customer_language}}
--- MARKET DIAGNOSIS (the stage the structure must match) --- {{market_diagnosis}}
--- THE FEEDING CREATIVE + its promise (the message-match contract) --- {{feeding_creative}}
--- ALREADY-SHIPPED COPY (dedupe target) --- {{shipped_copy}}
--- BRAND VOICE DOC, as context only, never as a gate --- {{brand_voice}}

--- ORCHESTRATION: MACHINE-READABLE EDIT RESULT (required) ---
After your normal output above, append ONE fenced ```json block containing exactly:
{"lever_scores": [<7 integers 0-2>], "hard_gate_failures": ["<invented quote/review/stat | message-match break | wrong awareness structure>"], "bounces": [{"defect": "...", "evidence_line": "...", "source_material": "..."}]}
The orchestrator enforces the gates from this block; the prose above stays authoritative for the human reader.
