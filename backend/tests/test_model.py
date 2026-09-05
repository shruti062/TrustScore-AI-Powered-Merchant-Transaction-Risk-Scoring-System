"""
tests/test_model.py

Tests for the model's non-ML logic: how a risk score gets turned into
an action, and how the rule-based explanations get built. These don't
require a trained model file, so they run fast and don't depend on
generate_data.py / model.py having been run first.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import model as risk_model


def test_decide_action_allow_below_review_threshold():
    action = risk_model.decide_action(20, {"block_threshold": 70, "review_threshold": 35})
    assert action == "allow"


def test_decide_action_review_between_thresholds():
    action = risk_model.decide_action(50, {"block_threshold": 70, "review_threshold": 35})
    assert action == "review"


def test_decide_action_block_at_or_above_block_threshold():
    action = risk_model.decide_action(85, {"block_threshold": 70, "review_threshold": 35})
    assert action == "block"


def test_decide_action_boundary_values():
    thresholds = {"block_threshold": 70, "review_threshold": 35}
    assert risk_model.decide_action(35, thresholds) == "review"  # exactly at review threshold
    assert risk_model.decide_action(70, thresholds) == "block"   # exactly at block threshold
    assert risk_model.decide_action(34.9, thresholds) == "allow"


def test_decide_action_uses_defaults_when_no_thresholds_given():
    # Defaults inside decide_action() are block=70, review=35
    assert risk_model.decide_action(80) == "block"
    assert risk_model.decide_action(50) == "review"
    assert risk_model.decide_action(10) == "allow"


def test_explain_score_flags_odd_hour():
    features = {
        "is_odd_hour": 1, "location_mismatch": 0, "new_device_flag": 0,
        "velocity_last_hour": 1, "amount_deviation_ratio": 1.0,
    }
    reasons = risk_model.explain_score(features)
    assert any("hours" in r for r in reasons)


def test_explain_score_flags_location_mismatch():
    features = {
        "is_odd_hour": 0, "location_mismatch": 1, "new_device_flag": 0,
        "velocity_last_hour": 1, "amount_deviation_ratio": 1.0,
    }
    reasons = risk_model.explain_score(features)
    assert any("city" in r for r in reasons)


def test_explain_score_no_flags_when_all_normal():
    features = {
        "is_odd_hour": 0, "location_mismatch": 0, "new_device_flag": 0,
        "velocity_last_hour": 1, "amount_deviation_ratio": 1.0,
    }
    reasons = risk_model.explain_score(features)
    assert reasons == ["No major red flags detected"]


def test_explain_score_flags_high_velocity():
    features = {
        "is_odd_hour": 0, "location_mismatch": 0, "new_device_flag": 0,
        "velocity_last_hour": 6, "amount_deviation_ratio": 1.0,
    }
    reasons = risk_model.explain_score(features)
    assert any("transactions from this customer" in r for r in reasons)
