"""leadbench - a falsification-oriented benchmark for lead-economics decisioning.

The question under test is whether a decision model that combines incremental
effect, contribution margin, agent-time cost and a capacity constraint beats
what end-to-end analytics, lead scoring, uplift modelling and contextual
bandits already give you -- measured in money, not accuracy.

Entry points:

    from leadbench.synthetic.dgp import generate         # data with known truth
    from leadbench.evaluation.runner import run_scenario  # fit -> decide -> score
    from leadbench.models.registry import get_tier        # candidate sets

See ``docs/benchmark-spec.md`` for the preregistered hypotheses, metrics and
kill criteria, and ``reports/latest/report.md`` for what the evidence said.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
