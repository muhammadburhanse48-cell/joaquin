"""JSON output schemas for every seat task whose result the orchestrator reads.

A task listed here runs with `output_config.format` (structured outputs): the API constrains
the reply to the schema, so the orchestrator reads fields instead of scraping markdown tables,
headings and fenced blocks. The human-readable writing the client's prompt asks for travels in
the `*_md` fields and is written to the brand files unchanged. Tasks not listed here
(e.g. pattern mining, scripts, motion) return plain markdown that is stored as-is.

Only the schema keywords structured outputs supports are used: no minItems/maxItems/minimum.
Counts and ranges are enforced by the gates in code.
"""

from __future__ import annotations

from typing import Any


def _str(desc: str) -> dict:
    return {"type": "string", "description": desc}


def _obj(props: dict[str, dict], desc: str | None = None) -> dict:
    out: dict[str, Any] = {"type": "object", "properties": props, "required": list(props),
                           "additionalProperties": False}
    if desc:
        out["description"] = desc
    return out


def _arr(items: dict, desc: str) -> dict:
    return {"type": "array", "items": items, "description": desc}


def _enum(values: list, desc: str) -> dict:
    kind = "integer" if all(isinstance(v, int) for v in values) else "string"
    return {"type": kind, "enum": values, "description": desc}


def _num_or_null(desc: str) -> dict:
    return {"anyOf": [{"type": "number"}, {"type": "null"}], "description": desc}


LEVER_SCORES = _arr(_enum([0, 1, 2], "one lever score"),
                    "exactly 7 integers 0-2, in the order the levers are listed")
HARD_GATES = _arr(_str("one failed hard gate, named"), "every failed hard gate; empty if none")

# The copy-sheet row. Keys are the sheet's columns; "number" is the sheet's "#" column.
COPY_ROW = _obj({
    "number": _str("creative number NN, from the file name"),
    "concept": _str("concept name"),
    "angle": _str("angle"),
    "persona": _str("persona"),
    "file_1x1": _str("the shipping file name exactly as given"),
    "on_image": _str("the text baked on the image"),
    "primary_text": _str("the full primary text; blank line between paragraphs"),
    "headline": _str("the ad headline, at most 40 characters"),
    "cta": _str("the call-to-action button text"),
    "link": _str("the explicit destination URL"),
})

SCHEMAS: dict[tuple[str, str], dict] = {
    # ------------------------------------------------------------ Creative Strategist
    ("creative_strategist", "task_mining_pass.md"): _obj({
        "customer_language_md": _str(
            "the complete customer-language.md file (four buckets + headline phrases), markdown"),
        "market_diagnosis_md": _str(
            "the complete market-diagnosis.md file (awareness, sophistication, avatar, dominant "
            "emotion, before/after, angle gap, highest-conviction findings), markdown"),
    }),
    ("creative_strategist", "task_persona_cards.md"): _obj({
        "personas": _arr(_obj({
            "name": _str("'<memorable name> — <one-line identity>', the text after '## Persona: '"),
            "visual_world": _str("the Visual world field: concrete nouns for image generation"),
            "card_md": _str("the rest of the card as markdown bullets (Who, Verbatim language by "
                            "awareness stage, Buying triggers, Objections / false beliefs, "
                            "Evidence base) — no heading and no Visual world line"),
        }), "one entry per persona the evidence supports"),
        "closing_table_md": _str("the closing persona × pain × objection × proof device table"),
    }),
    ("creative_strategist", "task_angle_bank.md"): _obj({
        "angle_bank_md": _str("the complete ranked angle bank in the entry format, with the "
                              "ranking line, the 70%/30% flags and any 'unsupported ideas' list"),
        "angle_ids": _arr(_str("an angle id such as A01"), "the id of every angle in the bank"),
    }),
    # ------------------------------------------------------------- Opportunity Scout
    ("opportunity_scout", "task_visual_teardown.md"): _obj({
        "rows": _arr(_obj({
            "image": _str("the two-digit image number exactly as labelled, e.g. 03"),
            "format archetype": _str("field 1"),
            "layout grid": _str("field 2"),
            "focal hierarchy": _str("field 3"),
            "colour system": _str("field 4"),
            "typography": _str("field 5"),
            "hook placement": _str("field 6"),
            "proof devices": _str("field 7"),
            "product presentation": _str("field 8"),
            "realism level": _str("field 9"),
            "complexity level": _str("field 10"),
            "why it likely works": _str("field 11"),
            "signal tier": _str("field 12: tier + the actual evidence figure"),
        }), "one row per attached image, in image order"),
    }),
    ("opportunity_scout", "task_swipe_vault.md"): _obj({
        "entries": _arr(_obj({
            "file": _str("<NN>_<archetype>_<advertiser>.png, NN = the torn-down image number"),
            "source_ad_id": _str("source ad id"),
            "source_url": _str("source url, or 'unknown'"),
            "advertiser": _str("advertiser"),
            "format_archetype": _str("format archetype"),
            "signal_tier": _str("T2 or T3"),
            "evidence": _str("the actual figure: days running, variant count, or EU spend"),
            "why_it_earned_its_slot": _str("one sentence, specific to this image"),
            "date_added": _str("YYYY-MM-DD"),
        }), "the 8-15 selected images' manifest entries"),
        "rejected_md": _str("the images you rejected, one-line reason each"),
    }),
    # ------------------------------------------------------- Creative Director, Mode A
    ("creative_director_a", "task_concept_portfolio.md"): _obj({
        "concepts": _arr(_obj({
            "concept_name": _str("concept name"),
            "angle_family": _str("angle family"),
            "persona": _str("persona card"),
            "awareness_stage": _str("awareness stage"),
            "format_archetype": _str("format archetype"),
            "hook": _str("hook, verbatim, at most 5 words"),
            "proof_device": _str("proof device"),
            "mix": _enum(["iterate", "new"], "70% iterate of a proven winner, or 30% net-new"),
            "iterates": _str("for iterate: the winner it iterates and the ONE variable it "
                             "changes (name a shipped parent as B<NN>-<NN>); empty for new"),
            "evidence_and_tier": _str("evidence + signal tier"),
        }), "one entry per concept, in order"),
        "objections_md": _str("which top-3 objections are covered by which concepts, and which "
                              "are NOT covered"),
    }),
    # ---------------------------------------------------------- Ecommerce Psychologist
    ("ecommerce_psychologist", "task_psych_review.md"): _obj({
        "review_md": _str("the full review for the human reader"),
        "verdicts": _arr(_obj({
            "concept": {"type": "integer", "description": "the concept number"},
            "verdict": _enum(["PASS", "FIX", "SWAP"], "verdict"),
            "fix": _str("the named change or swap-in; empty for PASS"),
        }), "one verdict per concept"),
    }),
    # ------------------------------------------------------- Creative Director, Mode B
    ("creative_director_b", "task_judge_qa.md"): _obj({
        "report_md": _str("the panel and critique for the human reader"),
        "verdicts": _arr(_obj({
            "slot": _str("slot id exactly as labelled on the images"),
            "winner": _str("the winning candidate's label, e.g. c2"),
            "verdict": _enum(["SHIP", "REGEN"], "verdict"),
            "lever_scores": LEVER_SCORES,
            "hard_gate_failures": HARD_GATES,
            "fix": _str("specific evidence-tied fix; empty for SHIP"),
            "fix_type": _enum(["regenerate", "recompose", ""], "fix type; empty for SHIP"),
        }), "one verdict per slot"),
    }),
    ("creative_director_b", "task_batch_sweep.md"): _obj({
        "sweep_md": _str("the sweep for the human reader"),
        "checks": _arr(_obj({
            "n": _enum(list(range(1, 11)), "check number 1-10"),
            "result": _enum(["PASS", "FAIL"], "result"),
            "files": _arr(_str("a file name"), "the files the check names"),
            "detail": _str("one line"),
        }), "all 10 checks, in order"),
    }),
    # ---------------------------------------------------------------------- Copywriter
    ("copywriter", "task_ad.md"): _obj({
        "rows": _arr(COPY_ROW, "one copy-sheet row per creative"),
        "working_md": _str("everything else the task asks for — the per-concept LONGFORM and "
                           "SHORT DEAL LINE variants, inline VoC tags — except the copy-sheet "
                           "rows, the compliance list and the self-score"),
        "compliance_flags": _arr(_str("one claim for human compliance review"),
                                 "the '→ Human compliance review' list"),
        "self_score_md": _str("your 7-lever self-score"),
    }),
    # ---------------------------------------------------------------------- Copy Editor
    ("copy_editor", "task_edit.md"): _obj({
        "rows": _arr(COPY_ROW, "the edited copy sheet, one row per creative, Tier-1 fixes applied"),
        "edit_report_md": _str("what you changed and why, and the dedupe result — everything "
                               "except the sheet rows, scores, bounces and compliance list"),
        "lever_scores": LEVER_SCORES,
        "hard_gate_failures": _arr(_enum(["invented quote/review/stat", "message-match break",
                                          "wrong awareness structure"], "a failed hard gate"),
                                   "every failed hard gate; empty if none"),
        "bounces": _arr(_obj({
            "defect": _str("the defect"),
            "evidence_line": _str("the evidence line it violates"),
            "source_material": _str("the source material to fix it with"),
        }), "the Tier-2 bounce log; empty if nothing bounces"),
        "compliance_flags": _arr(_str("one claim for human compliance review"),
                                 "the '→ Human compliance review' list"),
    }),
    # -------------------------------------------------------------------- Video Editor
    ("video_editor", "task_script_gate.md"): _obj({
        "report_md": _str("the gate review for the human reader"),
        "scripts": _arr(_obj({
            "script": _str("script id"),
            "verdict": _enum(["SHIP", "REVISE"], "verdict"),
            "message_match": _enum(list(range(0, 11)), "0-10"),
            "hook_strength": _enum(list(range(0, 11)), "0-10"),
            "voc_density": _enum(list(range(0, 11)), "0-10"),
            "failed_checks": _arr(_str("a failed check"), "failed checks"),
            "fix": _str("the fix; empty for SHIP"),
        }), "one result per script"),
    }),
    # ------------------------------------------------------------------------- Analyst
    ("analyst", "task_readout.md"): _obj({
        "readout_md": _str("the full readout for the human reader"),
        "ads": _arr(_obj({
            "date": _str("YYYY-MM-DD"),
            "ad_name": _str("ad name"),
            "ad_id": _str("ad id"),
            "batch": _str("B<NN>, or UNMAPPED"),
            "concept": _str("concept"),
            "campaign_type": _str("campaign type"),
            "spend": {"type": "number", "description": "spend"},
            "purchases": _num_or_null("purchases"),
            "cpa": _num_or_null("CPA"),
            "roas": _num_or_null("ROAS"),
            "ctr": _num_or_null("CTR"),
            "freq": _num_or_null("frequency"),
            "verdict": _enum(["PROMOTE", "SCALE", "ITERATE", "NO-PROMOTE", "KILL", "FATIGUE",
                              "LEARNING", "below floor — no verdict", "NOT LAUNCHED"], "verdict"),
            "action_taken": _str("action taken"),
        }), "one row per ad"),
        "winning_variables": _arr(_obj({
            "variable_type": _str("variable type"),
            "value": _str("value"),
            "batch": _str("batch"),
            "evidence": _str("spend, CPA vs target, CTR — numbers or no row"),
            "tier": _str("T1"),
            "date": _str("YYYY-MM-DD"),
            "status": _enum(["ACTIVE", "fatigued", "RETIRED"], "status"),
        }), "variables promoted with T1 numbers; empty if none"),
        "learnings": _arr(_str("a cross-brand principle with numbers"), "cross-brand learnings"),
        "invalidate_research": {"type": "boolean",
                                "description": "true if this readout invalidates the research"},
    }),
    # --------------------------------------------------------------------- Media Buyer
    ("media_buyer", "task_launch_plan.md"): _obj({
        "plan_md": _str("the full launch plan for the human reader, items 1-6"),
        "ad_names": _arr(_obj({
            "creative": _str("the creative number NN from the file name"),
            "ad_name": _str("the prescribed ad name, exactly 'B<NN> · <NN>_<Concept>'"),
        }), "one prescribed ad name per shipping file"),
    }),
}

_BRIEFS = _obj({
    "briefs": _arr(_obj({
        "brief_md": _str("one complete brief following the template exactly, starting with its "
                         "'# Creative Brief' title line"),
        "copy_slots": _obj({
            "eyebrow": _str("eyebrow text baked on the image; empty if none"),
            "headline": _str("headline text baked on the image"),
            "proof": _str("proof-badge text; empty if none"),
            "was": _str("old price, no strikethrough markers; empty if none"),
            "now": _str("current price; empty if no price is shown"),
        }, "the exact strings in this brief's 'Copy slots for the image'"),
    }), "one brief per variant, V1 first"),
})
SCHEMAS[("creative_director_a", "task_write_briefs.md")] = _BRIEFS
SCHEMAS[("creative_director_a", "task_revise_briefs.md")] = _BRIEFS
SCHEMAS[("copywriter", "task_ad_revision.md")] = SCHEMAS[("copywriter", "task_ad.md")]


def schema_for(seat: str, task_file: str) -> dict | None:
    return SCHEMAS.get((seat, task_file))


def output_instructions(schema: dict) -> str:
    """The format note appended to a structured task, so the model knows where each part of
    its work goes. The schema itself is enforced by the API; this only maps prompt to fields."""
    lines = ["--- ORCHESTRATION: OUTPUT FORMAT ---",
             "Your reply is ONE JSON object matching the enforced response schema. Everything the "
             "task above asks you to write goes into these fields (markdown inside *_md fields):"]
    for name, spec in schema["properties"].items():
        lines.append(f"- {name}: {spec.get('description', '')}")
    return "\n".join(lines)
