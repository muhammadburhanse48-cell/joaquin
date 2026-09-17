from types import SimpleNamespace

import pytest

from agents.base_seat import BaseSeat
from agents.seats.ecommerce_psychologist import EcommercePsychologist
from orchestrator.brand_state import initialize_brand
from orchestrator.gates import flywheel_gate


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="ok")])


class FakeClient:
    def __init__(self):
        self.messages = FakeMessages()


def test_stateless_request_has_one_user_message():
    client = FakeClient()
    seat = BaseSeat("test", __import__("pathlib").Path("agents/prompts/creative_strategist"), client=client)
    seat.run("hello <brand>", {"brand": "Demo"})
    assert len(client.messages.calls) == 1
    assert len(client.messages.calls[0]["messages"]) == 1
    assert client.messages.calls[0]["messages"][0]["content"][0]["text"] == "hello Demo"


def test_critic_rejects_author_context():
    with pytest.raises(ValueError):
        EcommercePsychologist(client=FakeClient()).psych_review({"hypothesis": "leak"})


def test_brand_tree_and_first_cycle_gate(tmp_path):
    brand = initialize_brand(tmp_path, "Demo")
    assert (brand / "07_results/results-log.md").exists()
    assert flywheel_gate(brand) == (True, "brand has never launched a batch")