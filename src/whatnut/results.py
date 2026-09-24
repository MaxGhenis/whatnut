"""Typed read access to results/results.json.

    from whatnut.results import r
    r.verify()
    r.le_gain("male", 40, 28, 0, "calibrated", "mean")   # years
    r.meta["n"], r.meta["seed"]

``r`` loads the file lazily on first use. Set WHATNUT_RESULTS to read another
copy. Regenerate the file with ``python -m whatnut.pipeline``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "results" / "results.json"

SEXES = ("female", "male")


class ResultsError(RuntimeError):
    """results.json is missing, malformed or internally inconsistent."""


def _key(x: float | int | str) -> str:
    if isinstance(x, str):
        return x
    if isinstance(x, bool) or float(x) != float(x):  # bool or NaN
        raise ResultsError(f"bad numeric key {x!r}")
    return f"{float(x):g}"


@dataclass(frozen=True)
class Results:
    path: Path = field(
        default_factory=lambda: Path(os.environ.get("WHATNUT_RESULTS", DEFAULT_PATH))
    )

    @cached_property
    def data(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ResultsError(
                f"{self.path} not found; run python -m whatnut.pipeline"
            ) from exc

    def __getitem__(self, name: str) -> Any:
        return self.data[name]

    @property
    def meta(self) -> dict[str, Any]:
        return self.data["meta"]

    @property
    def days_per_year(self) -> float:
        return self.meta["days_per_year"]

    @property
    def members(self) -> list[str]:
        return self.meta["grid_axes"]["member"]

    @property
    def stats(self) -> list[str]:
        return self.meta["grid_axes"]["stat"]

    # ---- the grid --------------------------------------------------------

    def le_gain(
        self,
        sex: str,
        a0: int,
        delta: float,
        background: float,
        member: str,
        stat: str = "mean",
    ) -> float:
        """Change in remaining life expectancy (years) at age ``a0`` from moving
        from ``background`` to ``background + delta`` g/day of nuts."""
        try:
            return float(
                self.data["grid"][sex][_key(a0)][_key(delta)][_key(background)][member][
                    stat
                ]
            )
        except KeyError as exc:
            axes = self.meta["grid_axes"]
            raise ResultsError(
                f"no grid cell for sex={sex!r}, a0={a0!r}, delta={delta!r}, "
                f"background={background!r}, member={member!r}, stat={stat!r}; "
                f"axes are {axes}"
            ) from exc

    def le_gain_days(self, *args, **kwargs) -> float:
        return self.le_gain(*args, **kwargs) * self.days_per_year

    def marginal(
        self, sex: str, background: float, member: str, stat: str = "mean"
    ) -> float:
        """Years gained from the next ``marginal_step_g`` grams at the reference age."""
        mg = self.data["marginal_10g"]
        return float(mg["by_background"][sex][_key(background)][member][stat])

    @property
    def reference(self) -> dict[str, Any]:
        return self.data["reference"]

    def bracket(self, sex: str, member: str, stat: str = "mean") -> float:
        """The reference case (years)."""
        return float(self.reference["bracket"][sex][member][stat])

    # ---- consistency -----------------------------------------------------

    def verify(self) -> None:
        """Re-derive headline numbers from the grid; raise ResultsError on mismatch."""
        d = self.data
        for k in ("meta", "grid", "reference", "marginal_10g", "cost", "fadnes"):
            if k not in d:
                raise ResultsError(f"results.json has no {k!r} section")
        for k in ("n", "seed", "days_per_year", "evidence_rows", "data_files"):
            if k not in self.meta:
                raise ResultsError(f"results.json meta has no {k!r}")
        problems: list[str] = []

        def check(label: str, got: float, want: float) -> None:
            # exact: both sides come from the same rounded numbers in the file
            if got is None or want is None or got != want:
                problems.append(f"{label}: stored {got!r}, re-derived {want!r}")

        ref = self.reference
        a0, delta, bg = ref["a0"], ref["delta"], ref["background"]
        # 1. the headline days are the grid's reference cell times days per year
        for name, stored in ref["headline_days"].items():
            sex, rest = name.split("_", 1)
            member = rest.removesuffix("_mean_days")
            days = self.le_gain(sex, a0, delta, bg, member) * self.days_per_year
            check(f"reference.headline_days.{name}", stored, float(f"{days:.6g}"))
        # 2. the reference bracket is the grid's reference cell
        for sex in SEXES:
            for member in self.members:
                for stat in self.stats:
                    check(
                        f"reference.bracket.{sex}.{member}.{stat}",
                        self.bracket(sex, member, stat),
                        self.le_gain(sex, a0, delta, bg, member, stat),
                    )
        # 3. marginal value of the next grams is the grid's delta = step column
        mg = d["marginal_10g"]
        for sex in SEXES:
            for b, cells in mg["by_background"][sex].items():
                for member, st in cells.items():
                    for stat, v in st.items():
                        check(
                            f"marginal_10g.{sex}.{b}.{member}.{stat}",
                            v,
                            self.le_gain(sex, mg["a0"], mg["step_g"], b, member, stat),
                        )
        # 4. the dial at c = 1 is face value
        if "c_1" in self.members:
            for sex in SEXES:
                for stat in self.stats:
                    check(
                        f"c_1 vs face_value ({sex}, {stat})",
                        self.le_gain(sex, a0, delta, bg, "c_1", stat),
                        self.le_gain(sex, a0, delta, bg, "face_value", stat),
                    )
        if problems:
            raise ResultsError(
                "results.json is internally inconsistent:\n  " + "\n  ".join(problems)
            )


r = Results()
