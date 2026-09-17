# Seat: Opportunity Scout
Source: Doc 02 — Pattern Mining
Note: Doc 00's seat table assigns pattern mining / format-radar work to the
Opportunity Scout seat. Doc 02 itself doesn't give this seat a separate
"system" identity prompt distinct from the task prompts below — each task
prompt below opens with its own framing instead. Treat Task 1's opening
paragraph as the closest thing to a system prompt, or write a short wrapper
system prompt using Doc 00's seat-table description: "Hunts new angles,
rising formats, adjacent-niche ideas. Maintains the backlog and the format
radar. Refuses to log an opportunity with no signal behind it."

---

## TASK 1 — The visual teardown pass
Attach 6–8 ad images per message. Repeat until every image has a row.

You are running a VISUAL TEARDOWN of winning competitor ads in the <niche> niche.
You are looking at the images, not describing metadata.

For EVERY image attached, produce one row with these twelve fields. Be specific
and concrete — "the eye hits the yellow price disc first because it's the only
saturated colour on a grey field" is a row; "eye-catching design" is not.

1. format archetype — the structural shape (avatar-callout · us-vs-them split ·
native-UI screenshot · editorial lifestyle · spec-callout product hero ·
meme/native · offer card · guarantee-as-headline · other, name it)
2. layout grid — thirds / centred stack / split / collage; where the product sits
3. focal hierarchy — what the eye hits 1st, 2nd, 3rd, and WHY
4. colour system — bg / accent / contrast; how many colours; brand-hex vs photo-native
5. typography — weight, headline:sub size ratio, max word count on image, personality
6. hook placement — top band / overlaid / inside UI; position relative to safe areas
7. proof devices — review screenshot, stat block, badge, before/after, press, stars
8. product presentation — real photo / render / lifestyle-in-use / flat-lay; angle;
fraction of frame
9. realism level — shot-on-phone ↔ studio ↔ obviously-designed graphic
10. complexity level — element count; busy ↔ minimal
11. why it likely works — the persona-level mechanism, tied to the visual choices
12. signal tier — I am giving you the evidence per image below; restate it

EVIDENCE PER IMAGE (use this, do not guess):
image 01 — advertiser: <domain> · <US: 94 days running, 6 variants> or <EU: €7,645>
image 02 — ...

HARD RULES
- US ads have NO spend data. Never describe a US ad as high-spend. Rank by
longevity / variant count / cross-advertiser repetition only.
- Every row cites its tier and the actual evidence figure.
- If you cannot see something clearly, say so. Do not fill the field with a guess.

Output as a markdown table, one row per image, image number as the first column.

---

## TASK 2 — Cross-ad pattern mining

Here are <N> completed teardown rows for the <niche> niche, from <M> advertisers.
--- TEARDOWN ROWS ---
<paste all rows>

Cluster them into PATTERNS. A pattern is a visual choice recurring across at
least 3 ads, ideally from at least 2 different advertisers. Anything appearing
once is one brand's taste — leave it out, or list it separately as "single
sightings worth watching".

Write the file `visual-pattern-library/<niche>.md`:
Header: run date · ads analysed N · advertisers M · tier mix
Patterns table — columns: pattern | frequency (real count, e.g. 19/31) |
exemplars (image numbers) | when to use | persona fit | do / don't
Anti-patterns section — "what NO winner in this set does". Be specific and
countable: element counts, type sizes, colour counts, layout habits. This section
becomes a QA checklist, so write it as things that can be checked.
Use-first list — the 3-5 patterns you would apply to the very next creative,
and why, each citing its frequency and tier mix.

HARD RULES
- Frequency counts are real counts from the rows above, never estimates.
- Every pattern row names at least 2 exemplar images and its tier mix.
- Zero US-spend claims anywhere in the file.

---

## TASK 3 — Swipe vault curation

From the <N> images torn down, select the 8-15 that become the permanent swipe
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

---

## TASK 4 — Video teardown

Attached: keyframes from <N> winning video ads in the <niche> niche. For each ad
you have (a) the first 3 seconds at 1fps — the HOOK frames — and (b) scene-change
frames covering the whole video.

For EVERY ad, one row:
1. hook (first 3s) — what is on frame 1; hook archetype (face mid-sentence /
problem shot / result-first / "watch me" act / text card); spoken vs caption-led;
word count of the opening caption
2. pacing — duration; cuts per 10s (from the scene-frame count); where pace changes
3. scene structure — shot order mapped to beats; product-reveal timestamp
4. text-overlay style — size, weight, colour, position; word-by-word vs chunked;
progress markers
5. retention devices — re-hooks, pattern interrupts, open loops, proof drops,
WITH timestamps
6. production grade — UGC-handheld ↔ studio; real human vs avatar; talking-head
vs b-roll-led
7. why it likely works — persona-level mechanism
8. signal tier + evidence <given below per ad>

Then mine across all rows into `<niche>-video.md` with exactly four sections —
Hook archetypes · Retention devices · Scene structures · Exemplars and tiers —
each as a table: pattern | frequency | exemplars | when to use | persona fit |
do/don't. Plus an anti-pattern section.

For hook archetypes specifically, distil the FIRST-3-SECONDS RULES as do/don'ts.
That section is the one I will write scripts against.
