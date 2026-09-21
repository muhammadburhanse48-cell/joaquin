--- THE SCRIPTS --- {{scripts}}
--- FIRST-3s RULES from the video pattern library --- {{first_3s_rules}}
--- CUSTOMER LANGUAGE (to check density against) --- {{customer_language}}
--- THE LANDING PAGE PROMISE --- {{landing_page_promise}}

--- ORCHESTRATION: MACHINE-READABLE SCRIPT-GATE RESULT (required) ---
After your normal output above, append ONE fenced ```json block containing exactly:
[{"script": "<id>", "verdict": "SHIP"|"REVISE", "message_match": <0-10>, "hook_strength": <0-10>, "voc_density": <0-10>, "failed_checks": ["..."], "fix": "..."}]
The orchestrator enforces the gates from this block; the prose above stays authoritative for the human reader.
