"""Canonical representations for provenance-checked scalars.

Why this module exists
----------------------
C9 says: any decision-relevant scalar written to more than one provenance
channel has a **canonical representation**, and each channel is checked
against it. Not against each other -- two channels and no designated truth is
worse than one channel, because a disagreement then has no resolvable side
and the arrangement only manufactures the appearance of verification.

The canonical form for θ is the **exact decimal** passed to
`--effect_sizes`. `metadata.json` and `panel_seeds.csv` are serialisations of
it. `results.jsonl` is a copy of the JSON serialisation.

Why decimal and not float
--------------------------
F17 was a decimal-rounding defect: `jsonlite::toJSON(digits = 4)` turned
−0.03125 into −0.0312. The natural bound on that is *half the last retained
digit*, which is exactly 0.00005. In binary it is not::

    >>> 0.03125 - 0.0312
    5.0000000000000375e-05

so a float check written as `<= 5e-5` rejects the single case the check
exists for. The first version of the closure check did exactly that, and was
then "fixed" with an epsilon -- which would have left the C9 checker carrying
the very representation ambiguity C9 exists to remove. An epsilon there would
have been a fitting punchline and a bad contract.

`decimal.Decimal` built from `repr(float)` is exact for every value in play:
Python's float repr is the shortest string that round-trips, so
`Decimal(str(-0.03125))` is `Decimal('-0.03125')` and
`Decimal(str(-0.0312))` is `Decimal('-0.0312')`. Their difference is
`Decimal('0.00005')`, and the comparison needs no tolerance at all.
"""

from __future__ import annotations

from decimal import Decimal

#: The nine M8 truths, as the exact decimal strings passed to
#: `--effect_sizes`. This is the canonical representation; every provenance
#: channel is checked against it.
CANONICAL_THETA_M8: tuple[str, ...] = (
    "-0.15", "-0.03125", "-0.02", "-0.01",
    "0.01", "0.0125", "0.051875", "0.10", "0.104375",
)

#: The seven M7 truths. All are exact at four decimal places, which is why
#: M7 escaped F17 -- by luck, not by design.
CANONICAL_THETA_M7: tuple[str, ...] = (
    "-0.10", "-0.05", "0.0", "0.02", "0.05", "0.075", "0.15",
)

#: Half of the last digit retained by `jsonlite::toJSON(digits = 4)`. The
#: largest a value can move under that rounding, exactly.
FOUR_DP_ROUNDING_BOUND = Decimal("0.00005")


def dec(x) -> Decimal:
    """Exact Decimal for a float, int or string.

    Goes through `repr` for floats deliberately: `Decimal(0.1)` is
    `0.1000000000000000055511151231257827021181583404541015625`, which is the
    true binary value and useless for asking "is this the decimal the
    experiment specified". `Decimal(str(0.1))` is `Decimal('0.1')`, which is
    the question actually being asked.
    """
    if isinstance(x, Decimal):
        return x
    if isinstance(x, float):
        # float(x) first, deliberately. numpy.float64 subclasses float, and
        # under numpy 2 its repr is "np.float64(-0.03125)", which Decimal
        # cannot parse -- so a canonicaliser that trusted repr() would raise
        # on the first array scalar it met. Narrowing to the builtin gives a
        # repr that round-trips and carries the same value.
        return Decimal(repr(float(x)))
    if isinstance(x, int):
        return Decimal(x)
    return Decimal(str(x))


def canon_str(x) -> str:
    """The canonical STRING for a value: normalised, never exponential.

    A canonical representation has to be unique or it is not canonical, and
    the first version of this module missed that. `--effect_sizes` was given
    "0.10"; `metadata.json` records `0.1`. Those are the same number, and
    `str(dec(...))` renders them as different strings, so the extension gate
    refused a state that had not changed -- a false alarm from the very
    contract written to prevent false confidence.

    `normalize()` strips the trailing zero; `format(..., "f")` keeps the
    result out of exponential notation, which `normalize()` would otherwise
    produce for values like 100 (`1E+2`).
    """
    return format(dec(x).normalize(), "f")


def canonical_set(thetas=CANONICAL_THETA_M8) -> set[Decimal]:
    return {Decimal(t) for t in thetas}


def matches_canonical(value, thetas=CANONICAL_THETA_M8) -> bool:
    """True when `value` IS one of the canonical thetas, exactly."""
    return dec(value) in canonical_set(thetas)


def rounding_of_canonical(value, thetas=CANONICAL_THETA_M8) -> Decimal | None:
    """The canonical θ that `value` is a legal 4-dp rounding of, if any.

    Returns None when `value` is not within half the last retained digit of
    any canonical θ -- which means it is not a rounding at all but a
    different number, and that is a corruption rather than a serialisation.
    """
    v = dec(value)
    for t in canonical_set(thetas):
        if abs(v - t) <= FOUR_DP_ROUNDING_BOUND:
            return t
    return None
