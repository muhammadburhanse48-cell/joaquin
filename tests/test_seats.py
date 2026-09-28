import re
from pathlib import Path

import pytest

from agents.base_seat import (BaseSeat, IsolationViolation, MissingEvidence, PROMPTS_ROOT,
                              SeatOutputError, assert_isolated_evidence)
from agents.seats.copy_editor import CopyEditor
from agents.seats.creative_director_b import CreativeDirectorB
from agents.seats.creative_strategist import CreativeStrategist
from agents.seats.ecommerce_psychologist import EcommercePsychologist
from agents.seats.graphic_designer import GraphicDesigner
from agents.seats.video_editor import VideoEditor, VideoScriptGate
from agents.schemas import SCHEMAS
from tests.fakes import PNG, StreamingMixin, response


class Echo(StreamingMixin):
    """Client that records the request and returns fixed text ({} for a structured task)."""

    def __init__(self, stop_reason="end_turn", text=None):
        self.calls, self.messages = [], self
        self.stop_reason, self.text = stop_reason, text

    def create(self, **kw):
        self.calls.append(kw)
        text = self.text if self.text is not None else ("{}" if "output_config" in kw else "ok")
        return response(text, self.stop_reason)


def test_request_is_stateless_single_message():
    c = Echo()
    seat = CreativeStrategist(client=c)
    seat.run("hello {{brand}}", {"brand": "Demo"})
    seat.run("again {{brand}}", {"brand": "Demo"})
    assert [len(x["messages"]) for x in c.calls] == [1, 1]
    assert c.calls[1]["messages"][0]["content"][-1]["text"] == "again Demo"  # no carry-over


def test_structured_task_sends_its_schema_and_returns_parsed_data():
    c = Echo(text='{"review_md": "r", "verdicts": [{"concept": 1, "verdict": "PASS", "fix": ""}]}')
    ev = {k: "x" for k in ("concept_portfolio", "persona_cards", "customer_language",
                           "market_diagnosis", "results_log", "landing_page")}
    res = EcommercePsychologist(client=c).psych_review(ev)
    fmt = c.calls[0]["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["schema"] is SCHEMAS[("ecommerce_psychologist", "task_psych_review.md")]
    assert res.data["verdicts"][0]["verdict"] == "PASS"
    sent = c.calls[0]["messages"][0]["content"][-1]["text"]
    assert "OUTPUT FORMAT" in sent and "- verdicts:" in sent  # the model is told where each part goes


def test_plain_task_has_no_schema_and_no_data():
    c = Echo()
    res = CreativeStrategist(client=c).run("hello {{brand}}", {"brand": "Demo"})
    assert "output_config" not in c.calls[0] and res.data is None and res.output_text == "ok"


@pytest.mark.parametrize("stop,text,match", [
    ("max_tokens", '{"a": 1', "cut off"),
    ("refusal", "", "refused"),
    ("end_turn", "not json", "not JSON"),
])
def test_unusable_replies_fail_loudly(stop, text, match):
    seat = EcommercePsychologist(client=Echo(stop_reason=stop, text=text))
    with pytest.raises(SeatOutputError, match=match):
        seat.run("x", {}, schema={"type": "object", "properties": {}, "required": [],
                                  "additionalProperties": False})


def _walk(schema, path="$"):
    yield path, schema
    for k, v in schema.get("properties", {}).items():
        yield from _walk(v, f"{path}.{k}")
    if "items" in schema:
        yield from _walk(schema["items"], f"{path}[]")
    for i, v in enumerate(schema.get("anyOf", [])):
        yield from _walk(v, f"{path}|{i}")


def test_every_schema_is_valid_for_structured_outputs_and_names_a_real_task():
    unsupported = {"minItems", "maxItems", "minimum", "maximum", "minLength", "maxLength", "multipleOf"}
    for (seat, task), schema in SCHEMAS.items():
        assert (PROMPTS_ROOT / seat / task).exists(), (seat, task)
        for path, node in _walk(schema):
            assert not unsupported & set(node), (seat, task, path)
            if node.get("type") == "object":
                assert node["additionalProperties"] is False, (seat, task, path)
                assert set(node["required"]) == set(node["properties"]), (seat, task, path)


def test_no_prompt_still_asks_for_a_fenced_json_block():
    for f in PROMPTS_ROOT.rglob("*.md"):
        assert "```json" not in f.read_text(), f


def test_every_prompt_slot_is_a_named_slot_no_raw_paste_tokens():
    for f in PROMPTS_ROOT.rglob("*.md"):
        assert not re.search(r"<(paste|attach)", f.read_text()), f
        assert "Confirm, then wait" not in f.read_text(), f


def test_fill_is_strict_both_ways():
    with pytest.raises(MissingEvidence, match="no evidence"):
        BaseSeat.fill_template("a {{x}} {{y}}", {"x": "1"})
    with pytest.raises(MissingEvidence, match="not used"):
        BaseSeat.fill_template("a {{x}}", {"x": "1", "z": "2"})
    with pytest.raises(MissingEvidence):
        BaseSeat.fill_template("a {{x}}", {"x": "   "})


def test_task_prompts_reach_the_model_with_evidence_filled():
    c = Echo()
    seat = EcommercePsychologist(client=c)
    ev = {k: f"<<{k}>>" for k in ("concept_portfolio", "persona_cards", "customer_language",
                                  "market_diagnosis", "results_log", "landing_page")}
    seat.psych_review(ev)
    sent = c.calls[0]["messages"][0]["content"][-1]["text"]
    assert all(f"<<{k}>>" in sent for k in ev) and "{{" not in sent
    assert "EVIDENCE — files only" in sent and "You are the Ecommerce Psychologist" not in sent
    assert c.calls[0]["system"].startswith("You are the Ecommerce Psychologist")


def test_system_and_task_are_not_duplicated():
    for seat in PROMPTS_ROOT.iterdir():
        files = {f.name: f.read_text() for f in seat.glob("*.md")}
        system = files.get("system.md", "")
        for name, body in files.items():
            if name.startswith("task_"):
                assert body.strip() != system.strip(), (seat.name, name)


@pytest.mark.parametrize("key", ["brief", "creative_brief", "hypothesis", "rationale", "director_notes"])
def test_critic_rejects_author_context_keys(key):
    for seat in (EcommercePsychologist(client=Echo()), CopyEditor(client=Echo())):
        with pytest.raises(IsolationViolation):
            seat.run("x", {key: "leak"})


def test_critic_rejects_a_brief_hidden_under_an_innocent_key():
    with pytest.raises(IsolationViolation, match="brief text"):
        assert_isolated_evidence({"notes": "# Creative Brief — 01_A_B_v1\n## The bet"})


def test_creative_director_b_refuses_a_brief_and_never_calls_the_api():
    c = Echo()
    seat = CreativeDirectorB(client=c)
    ev = {"persona_card": "p", "brand_rules": "b", "landing_page_promise": "l", "exemplar_evidence": "e"}
    with pytest.raises(IsolationViolation):
        seat.judge_and_qa({**ev, "brief": "why this works"}, [("slot 01 / c1", PNG)])
    assert c.calls == []
    with pytest.raises(ValueError, match="images"):
        seat.judge_and_qa(ev, [])


def test_images_are_sent_in_order_with_labels_before_the_text():
    c = Echo()
    CreativeDirectorB(client=c).judge_and_qa(
        {"persona_card": "p", "brand_rules": "b", "landing_page_promise": "l", "exemplar_evidence": "e"},
        [("slot 01 / c1", PNG), ("slot 01 / c2", PNG)])
    content = c.calls[0]["messages"][0]["content"]
    assert [b["type"] for b in content] == ["text", "image", "text", "image", "text"]
    assert content[0]["text"] == "[slot 01 / c1]" and content[2]["text"] == "[slot 01 / c2]"


def test_seat_client_is_created_lazily(monkeypatch):
    import anthropic

    made = []
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: made.append(kw) or Echo())
    seat = CreativeStrategist()
    assert made == []  # constructing a seat must not need a key
    seat.run("x", {})
    assert made and made[0]["api_key"] == "test-key"


def test_video_script_gate_is_an_isolated_critic_with_its_own_system_prompt():
    gate, editor = VideoScriptGate(client=Echo()), VideoEditor(client=Echo())
    assert gate.critic and not editor.critic
    assert gate.system_prompt != editor.system_prompt and "did not write" in gate.system_prompt
    with pytest.raises(IsolationViolation):
        gate.review({"scripts": "s", "rationale": "r"})


def test_motion_refuses_an_unshipped_or_unproven_creative():
    ve = VideoEditor(client=Echo())
    with pytest.raises(ValueError, match="already won"):
        ve.motion({"result": "", "winning_variable": "hook"}, PNG)


def test_graphic_designer_fills_template_and_enforces_offer_rules():
    gd = GraphicDesigner()
    spec = dict(product_features="matte navy", product_noun="suitcase", background="a gradient",
                niche_tone="premium", palette_ground="#fff", palette_accent="#000", palette_contrast="#111",
                persona_visual_world="airport", qualifier="with free returns", eyebrow="WEEKEND",
                headline="Skip the fee", proof="4.8 stars", was="$90", now="$59")
    req = gd.build_prompt(spec, "front.png")
    assert '"Skip the fee"' in req.prompt and "attached reference image" in req.prompt
    assert req.sidecar["product_reference"] == "front.png"
    with pytest.raises(ValueError, match="product photograph"):
        gd.build_prompt(spec, "")
    with pytest.raises(ValueError, match="free"):
        gd.build_prompt({**spec, "headline": "100% free shipping"}, "front.png")
    with pytest.raises(ValueError, match=r"\$0"):
        gd.build_prompt({**spec, "now": "$0.00", "qualifier": " "}, "front.png")


def test_graphic_designer_drops_an_absent_proof_badge_and_old_price_instead_of_sending_blanks():
    spec = dict(product_features="matte navy", product_noun="suitcase", background="a gradient",
                niche_tone="premium", palette_ground="#fff", palette_accent="#000", palette_contrast="#111",
                persona_visual_world="airport", qualifier="with free returns", eyebrow="WEEKEND",
                headline="Skip the fee", now="$59")
    req = GraphicDesigner().build_prompt(spec, "front.png")
    assert "Proof badge" not in req.prompt and "struck-through" not in req.prompt
    assert 'Offer lockup, lower-right: "$59"' in req.prompt and "{{" not in req.prompt
    assert req.sidecar["copy"]["proof"] == "" and req.sidecar["copy"]["now"] == "$59"


def test_headline_only_creative_drops_eyebrow_proof_and_the_whole_offer_lockup():
    spec = dict(product_features="matte navy", product_noun="suitcase", background="a gradient",
                niche_tone="premium", palette_ground="#fff", palette_accent="#000", palette_contrast="#111",
                persona_visual_world="airport", qualifier="with free returns", eyebrow="", headline="Fits every airline",
                proof="", was="", now="")
    req = GraphicDesigner().build_prompt(spec, "front.png")
    for gone in ("Eyebrow", "Proof badge", "Offer lockup", "qualifier"):
        assert gone not in req.prompt, gone
    assert '"Fits every airline"' in req.prompt and "{{" not in req.prompt
