TASK: full readout for {{brand}}, week of {{week_of}}.

--- AD-LEVEL DATA, LAST 3 DAYS ---
{{ads_3d}}
--- AD-LEVEL DATA, LAST 7 DAYS --- {{ads_7d}}
--- AD-LEVEL DATA, LIFETIME --- {{ads_lifetime}}
--- COUNTRY BREAKDOWN --- {{country_breakdown}}
--- ECONOMICS: AOV, COGS %, payment fee %, uncovered shipping % --- {{economics}}
--- CREATIVE LEDGER: every batch shipped, with its concept table --- {{creative_ledger}}
--- PREVIOUS RESULTS LOG --- {{results_log}}

PRODUCE, IN THIS ORDER:
1. TOP LINE — spend, purchases, blended CPA and ROAS, per window. State which
window drives the verdicts (3d) and which guards against false kills (7d).
2. DERIVED TARGETS — breakeven ROAS, target ROAS (20% net), max CPA, and the
2-ROAS cap (AOV/2). Show the arithmetic. If inputs are missing, print
"inputs needed" and give NO net-margin verdict.
3. ONE ROW PER AD:
| date | ad name/id | batch | concept | campaign type | spend | purch | CPA |
| ROAS | CTR | freq | verdict | action taken |
- Map every ad to its batch + concept via the naming convention against the
ledger. Unmappable → batch: UNMAPPED with the raw name, flagged.
- Below the floor → "below spend floor — no verdict" with actual spend.
- "action taken" states the DIAGNOSED LEVER: low thumbstop/CTR-all → hook/visual.
Good thumbstop + low link CTR → angle/message match. Good CTR + bad CPA →
offer/LP congruence (often NOT the creative).
4. NET MARGIN LINE — spend, revenue, blended ROAS, net % vs the 20% target.
5. COUNTRY TABLE — spend / purch / revenue / ROAS / CPA / % of spend.
Name the leaks (under breakeven) and the scale candidates (over target).
6. PROMOTION TABLE — each CBO winner · its 3-day consistency (n/3 days ≥2 ROAS)
· already in cost cap? bid cap? · the prescribed move.
7. AD-SET CUT LIST — which rule fired (A or B) with the numbers. First check the
override: a campaign netting above 20% has NOTHING turned off.
8. RECONCILIATION — every batch in the ledger resolves to verdict rows,
below-floor rows, or one explicit NOT LAUNCHED line. List any that don't.
9. BATCH READOUT — winners and the variable that drove them · losers and why ·
what gets promoted · what the next batch must do differently.
10. PROMOTIONS — rows for winning-variables.md (with T1 evidence strings, and
fatigued/retired statuses too) and any cross-brand principle for
creative-learnings.md. Theory never gets promoted — numbers or nothing.
