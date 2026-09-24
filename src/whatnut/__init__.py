"""What nut: how much life eating nuts buys a US adult.

Modules:
    data       loaders for data/ (sha256-checked against each folder's MANIFEST.json)
               and evidence rows from data/evidence.yaml
    lifetable  remaining life expectancy from single-year death probabilities under
               age-specific hazard multipliers
    model      dose curves, the bracket of causal multipliers, Monte Carlo draws
    pipeline   writes results/results.json and paper/figures/*.png
    results    typed accessors over results/results.json
               (``from whatnut.results import r``)

Regenerate everything with ``python -m whatnut.pipeline``.
"""

__version__ = "0.3.0"
