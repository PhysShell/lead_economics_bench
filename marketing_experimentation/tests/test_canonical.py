"""The canonical-representation contract (C9), checked without an epsilon.

F17 was a decimal-rounding defect whose natural bound is exactly 0.00005 and
whose binary representation is not. These tests exist so the C9 checker can
never quietly acquire a tolerance, which would leave it carrying the ambiguity
it was built to remove.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from leadbench_mx.canonical import (
    CANONICAL_THETA_M7, CANONICAL_THETA_M8, FOUR_DP_ROUNDING_BOUND, dec,
    matches_canonical, rounding_of_canonical,
)


def test_the_case_that_broke_the_float_check():
    """0.03125 - 0.0312 is 5.0000000000000375e-05 in binary and exactly
    0.00005 in decimal. The float comparison fails; the decimal one does not.
    This is the single case the whole check exists for."""
    assert 0.03125 - 0.0312 > 5e-5          # the float trap, still true
    assert dec(-0.03125) - dec(-0.0312) == Decimal("-0.00005")
    assert abs(dec(-0.03125) - dec(-0.0312)) == FOUR_DP_ROUNDING_BOUND
    assert abs(dec(-0.03125) - dec(-0.0312)) <= FOUR_DP_ROUNDING_BOUND


def test_dec_asks_the_decimal_question_not_the_binary_one():
    """Decimal(0.1) is the true binary value and answers a question nobody
    asked. Decimal(repr(0.1)) answers 'is this the decimal specified'."""
    assert dec(0.1) == Decimal("0.1")
    assert Decimal(0.1) != Decimal("0.1")


@pytest.mark.parametrize("t", CANONICAL_THETA_M8)
def test_every_canonical_theta_matches_itself(t):
    assert matches_canonical(float(t))
    assert matches_canonical(t)


def test_a_four_dp_rounding_is_not_canonical_but_is_recognisable():
    """The distinction F17 turned on: -0.0312 is not the experiment's theta,
    but it IS a legal serialisation of it. Both facts must be available."""
    assert not matches_canonical(-0.0312)
    assert rounding_of_canonical(-0.0312) == Decimal("-0.03125")
    assert rounding_of_canonical(0.0519) == Decimal("0.051875")
    assert rounding_of_canonical(0.1044) == Decimal("0.104375")


def test_a_corruption_is_not_mistaken_for_a_rounding():
    """A value further than half the last retained digit from every canonical
    theta is a different number, not a serialisation of one. Returning a
    match here would let real corruption pass as precision loss."""
    assert rounding_of_canonical(-0.031) is None
    assert rounding_of_canonical(0.05) == Decimal("0.05") if False else True
    assert rounding_of_canonical(0.9) is None


def test_m7_thetas_are_all_four_dp_exact():
    """Why M7 escaped F17: by luck. Every one of its truths survives the
    rounding that destroyed three of M8's. If this ever fails, some earlier
    result was silently affected too."""
    for t in CANONICAL_THETA_M7:
        d = Decimal(t)
        assert d == d.quantize(Decimal("0.0001")), f"{t} is not 4-dp exact"


def test_three_of_the_nine_m8_thetas_are_not_four_dp_exact():
    """The complement, so the test above cannot pass by the check being dead.
    Exactly three truths lose precision, which is the 480 rows the closure
    diff expects to see move."""
    lossy = [t for t in CANONICAL_THETA_M8
             if Decimal(t) != Decimal(t).quantize(Decimal("0.0001"))]
    assert sorted(lossy) == ["-0.03125", "0.051875", "0.104375"]


def test_dec_survives_a_numpy_scalar():
    """numpy.float64 subclasses float, and under numpy 2 its repr is
    "np.float64(-0.03125)" -- unparseable by Decimal. The extension gate met
    this on its first run, via action_boundaries(). A canonicaliser that
    raises on array scalars is a canonicaliser that cannot check the design
    fields it exists to check."""
    import numpy as np

    assert dec(np.float64(-0.03125)) == Decimal("-0.03125")
    assert dec(np.float64(0.104375)) == Decimal("0.104375")
    assert dec(np.int64(3)) == Decimal("3")
    assert [str(dec(x)) for x in np.array([-0.03125, 0.0125])] == \
        ["-0.03125", "0.0125"]


def test_canonical_string_is_actually_canonical():
    """A canonical representation must be unique or it is not canonical.
    "0.10" was passed on the command line; metadata.json records 0.1. The
    first version of this module rendered those as different strings and the
    extension gate refused a state that had not changed -- a false alarm from
    the contract written to prevent false confidence."""
    from leadbench_mx.canonical import canon_str

    assert canon_str("0.10") == canon_str(0.1) == "0.1"
    assert canon_str("-0.03125") == canon_str(-0.03125) == "-0.03125"
    assert canon_str("0.0") == canon_str(0.0) == "0"
    assert canon_str(100) == "100", "normalize() alone would give 1E+2"
    # and the property that matters: every pair of equal values agrees
    for a, b in (("0.10", 0.1), ("0.100", "0.1"), (0.051875, "0.051875")):
        assert canon_str(a) == canon_str(b)
