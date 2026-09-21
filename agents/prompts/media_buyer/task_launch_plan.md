<!-- ORCHESTRATION: the ad-name delimiter is not fixed by the handbook; this contract line pins it so the readout can parse names. -->
TASK: turn shipped batch B{{batch}} into a launch plan I can execute manually.

--- THE SHIPPING FILES (numbered) --- {{shipping_files}}
--- THE COPY SHEET --- {{copy_sheet}}
--- DESTINATIONS per angle --- {{destinations}}
--- DERIVED TARGETS: target CPA, target ROAS, spend floor per creative --- {{derived_targets}}
--- WHAT THE ACCOUNT'S OWN RESULTS PROVE about structure --- {{account_results}}
--- CURRENT ACCOUNT STATE: live campaigns, spend cap headroom, page ad limits ---
{{account_state}}

PRODUCE:
1. Structure table — campaign (buying type, objective, CBO) → ad sets (one per
angle/concept family, broad targeting — the creative IS the targeting) →
ads (which numbered files and which copy-sheet rows go where).
2. Prescribed ad names — every ad name carries the B{{batch}} batch marker AND the
NN_<Concept> file marker. This is a contract with the readout: next month's
reconciliation maps ads back to concepts BY NAME, and the names are set here.
A launch plan with unparseable ad names is a defect.
3. Budget math, shown — daily budget = spend floor × creatives ÷ days to verdict,
with the arithmetic visible. Respect spend-cap headroom; state it or flag it
unknown.
4. Test matrix — which lever each ad set isolates (angle vs format vs persona),
and what each possible result would mean.
5. Launch-readiness flags — LP live? pixel firing? flows live? page ad-limit
headroom? These are flags, never blocks. I decide.
6. Execution checklist — the exact manual click-path to stand it up, in order.

PROPOSAL ONLY. Do not attempt to create, activate or modify anything.

AD-NAME CONTRACT: write every ad name exactly as `B<NN> · <NN>_<Concept>` (e.g. `B07 · 03_FitAnxiety`), where <NN> is the concept number from the file name.
