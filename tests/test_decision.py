"""Tests for decision context and cost-effectiveness summaries."""

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from whatnut.decision import (
    DEFAULT_WILLINGNESS_TO_PAY,
    SINGLE_NUT_ADDITION_DECISION,
    DecisionContext,
    summarize_cost_effectiveness,
    summarize_mutually_exclusive_nmb,
    validate_willingness_to_pay,
)


def test_single_nut_decision_context_is_explicit():
    context = SINGLE_NUT_ADDITION_DECISION

    assert isinstance(context, DecisionContext)
    assert "28 g" in context.intervention
    assert "one nut" in context.intervention
    assert context.comparator == "No modeled daily-nut intervention."
    assert "Gross retail cost" in context.cost_basis
    assert "mortality-derived" in context.outcome.lower()
    assert "expected net monetary benefit" in context.ranking_metric.lower()
    assert "no-intervention comparator" in context.ranking_metric.lower()
    assert "probability" in context.probability_metric.lower()
    assert "mutually exclusive" in context.probability_metric.lower()

    exclusions = " ".join(context.not_modeled).lower()
    for required_exclusion in (
        "current diet",
        "routine",
        "displaced",
        "substitution",
        "morbidity",
        "harms",
        "persistence",
        "baseline risk",
        "mixed nuts",
    ):
        assert required_exclusion in exclusions


def test_decision_context_is_frozen_and_serializable():
    context = SINGLE_NUT_ADDITION_DECISION

    with pytest.raises(FrozenInstanceError):
        context.comparator = "A different comparator."

    assert context.to_dict() == {
        "intervention": context.intervention,
        "comparator": context.comparator,
        "cost_basis": context.cost_basis,
        "not_modeled": context.not_modeled,
        "outcome": context.outcome,
        "ranking_metric": context.ranking_metric,
        "probability_metric": context.probability_metric,
    }


def test_summarize_cost_effectiveness_returns_all_decision_metrics():
    qalys = np.array([-0.2, 0.0, 0.1, 0.3])
    costs = np.array([10.0, 20.0, 30.0, 40.0])

    result = summarize_cost_effectiveness(qalys, costs, willingness_to_pay=1_000)

    assert set(result) == {
        "expected_qaly",
        "expected_cost",
        "expected_cost_per_qaly",
        "p_benefit",
        "p_harm",
        "expected_upside",
        "expected_downside",
        "expected_net_monetary_benefit",
        "p_nmb_positive",
    }
    assert result["expected_qaly"] == pytest.approx(0.05)
    assert result["expected_cost"] == pytest.approx(25.0)
    assert result["expected_cost_per_qaly"] == pytest.approx(500.0)
    assert result["p_benefit"] == pytest.approx(0.5)
    assert result["p_harm"] == pytest.approx(0.25)
    assert result["expected_upside"] == pytest.approx(0.1)
    assert result["expected_downside"] == pytest.approx(-0.05)
    assert result["expected_net_monetary_benefit"] == pytest.approx(25.0)
    assert result["p_nmb_positive"] == pytest.approx(0.5)
    assert all(isinstance(value, float) for value in result.values())


@pytest.mark.parametrize(
    "qalys",
    [
        np.array([-0.4, 0.2, 0.6]),
        np.array([0.0, 0.0, 0.0]),
        np.array([0.2, 0.3, 0.4]),
    ],
)
def test_expected_upside_and_downside_reconstruct_the_mean(qalys):
    result = summarize_cost_effectiveness(
        qalys,
        np.zeros_like(qalys),
        willingness_to_pay=100_000,
    )

    assert result["expected_upside"] + result["expected_downside"] == (
        pytest.approx(result["expected_qaly"])
    )


@pytest.mark.parametrize(
    "qalys",
    [
        np.array([-1.0, 1.0]),
        np.array([-2.0, 1.0]),
    ],
)
def test_expected_cost_per_qaly_is_infinite_for_nonpositive_mean(qalys):
    result = summarize_cost_effectiveness(
        qalys,
        np.array([10.0, 20.0]),
        willingness_to_pay=100_000,
    )

    assert result["expected_cost_per_qaly"] == float("inf")


def test_net_monetary_benefit_probability_uses_strict_positivity():
    result = summarize_cost_effectiveness(
        qalys=np.array([1.0, 0.0, 0.5]),
        costs=np.array([100.0, 0.0, 49.0]),
        willingness_to_pay=100.0,
    )

    assert result["expected_net_monetary_benefit"] == pytest.approx(1 / 3)
    assert result["p_nmb_positive"] == pytest.approx(1 / 3)


@pytest.mark.parametrize(
    ("qalys", "costs", "message"),
    [
        ([], [], "nonempty"),
        (1.0, [1.0], "one-dimensional"),
        ([1.0], 1.0, "one-dimensional"),
        ([[1.0, 2.0]], [[3.0, 4.0]], "one-dimensional"),
        ([1.0, 2.0], [1.0], "same shape"),
        ([1.0, np.nan], [1.0, 2.0], "finite"),
        ([1.0, 2.0], [1.0, np.inf], "finite"),
        ([1.0, 1.0j], [1.0, 2.0], "real numeric"),
        (["not numeric"], [1.0], "numeric"),
    ],
)
def test_invalid_draws_are_rejected(qalys, costs, message):
    with pytest.raises(ValueError, match=message):
        summarize_cost_effectiveness(qalys, costs, willingness_to_pay=100_000)


@pytest.mark.parametrize(
    "willingness_to_pay",
    [0.0, -1.0, np.nan, np.inf, -np.inf, "not numeric", None, True],
)
def test_invalid_willingness_to_pay_is_rejected(willingness_to_pay):
    with pytest.raises(ValueError, match="positive finite"):
        summarize_cost_effectiveness(
            [0.1, 0.2],
            [100.0, 200.0],
            willingness_to_pay=willingness_to_pay,
        )


def test_summary_does_not_mutate_input_arrays():
    qalys = np.array([-0.1, 0.2])
    costs = np.array([10.0, 20.0])
    original_qalys = qalys.copy()
    original_costs = costs.copy()

    summarize_cost_effectiveness(qalys, costs, willingness_to_pay=100_000)

    np.testing.assert_array_equal(qalys, original_qalys)
    np.testing.assert_array_equal(costs, original_costs)


def test_default_willingness_to_pay_is_explicit_and_valid():
    assert DEFAULT_WILLINGNESS_TO_PAY == 50_000
    assert validate_willingness_to_pay(DEFAULT_WILLINGNESS_TO_PAY) == 50_000


def test_mutually_exclusive_summary_uses_paired_draws_and_splits_ties():
    summary = summarize_mutually_exclusive_nmb(
        {
            "no_intervention": [0.0, 0.0, 0.0, 0.0],
            "a": [1.0, 0.0, 2.0, -1.0],
            "b": [0.0, 0.0, 1.0, 3.0],
        }
    )

    assert summary.ranking == ("b", "a", "no_intervention")
    assert summary.recommended_option_ids == ("b",)
    assert summary.expected_nmb == {
        "no_intervention": 0.0,
        "a": 0.5,
        "b": 1.0,
    }
    assert summary.probability_optimal["no_intervention"] == pytest.approx(1 / 12)
    assert summary.probability_optimal["a"] == pytest.approx(7 / 12)
    assert summary.probability_optimal["b"] == pytest.approx(1 / 3)
    assert sum(summary.probability_optimal.values()) == pytest.approx(1.0)


def test_mutually_exclusive_summary_is_order_invariant():
    first = summarize_mutually_exclusive_nmb({"a": [1, 0], "b": [0, 1]})
    second = summarize_mutually_exclusive_nmb({"b": [0, 1], "a": [1, 0]})

    assert first.to_dict() == second.to_dict()


def test_mutually_exclusive_summary_reports_expected_value_ties():
    summary = summarize_mutually_exclusive_nmb({"b": [0, 0], "a": [0, 0]})

    assert summary.recommended_option_ids == ("a", "b")
    assert summary.probability_optimal == {"b": 0.5, "a": 0.5}


def test_mutually_exclusive_summary_rejects_misaligned_draws():
    with pytest.raises(ValueError, match="same shape"):
        summarize_mutually_exclusive_nmb({"a": [1, 2], "b": [1]})
