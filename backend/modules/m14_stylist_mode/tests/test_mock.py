"""mock.py answers have the real contract shapes, so the other BOs can code against them offline."""

import pytest

from modules.m14_stylist_mode import mock
from modules.m14_stylist_mode.contract import (
    ClientBrief,
    Dashboard,
    Escalation,
    Handoff,
    InstoreOut,
    Look,
    Pro,
    Review,
)


@pytest.mark.parametrize(
    ("fn", "model"),
    [
        (mock.pro, Pro),
        (mock.brief, ClientBrief),
        (mock.review, Review),
        (mock.look, Look),
        (mock.instore, InstoreOut),
        (mock.dashboard, Dashboard),
        (mock.escalation, Escalation),
        (mock.handoff, Handoff),
    ],
)
def test_mock_matches_contract(fn, model):
    model.model_validate(fn())
