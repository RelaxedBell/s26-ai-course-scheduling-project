"""Evaluation framework: compare model schedules vs random baseline."""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EvaluationResult:
    """Aggregated evaluation metrics."""

    model_ratings: list[float]
    random_ratings: list[float]

    @property
    def model_avg(self) -> float:
        return statistics.mean(self.model_ratings) if self.model_ratings else 0.0

    @property
    def random_avg(self) -> float:
        return statistics.mean(self.random_ratings) if self.random_ratings else 0.0

    @property
    def improvement(self) -> float:
        """Percentage improvement of model over random."""
        if self.random_avg == 0:
            return 0.0
        return ((self.model_avg - self.random_avg) / self.random_avg) * 100

    @property
    def model_stdev(self) -> float:
        if len(self.model_ratings) < 2:
            return 0.0
        return statistics.stdev(self.model_ratings)

    @property
    def random_stdev(self) -> float:
        if len(self.random_ratings) < 2:
            return 0.0
        return statistics.stdev(self.random_ratings)

    def summary(self) -> str:
        lines = [
            "=== Evaluation Report ===",
            f"Model schedules:  avg={self.model_avg:.2f}, "
            f"stdev={self.model_stdev:.2f}, n={len(self.model_ratings)}",
            f"Random schedules: avg={self.random_avg:.2f}, "
            f"stdev={self.random_stdev:.2f}, n={len(self.random_ratings)}",
            f"Improvement: {self.improvement:+.1f}%",
        ]
        if self.model_avg > self.random_avg:
            lines.append("Result: Model outperforms random baseline.")
        elif self.model_avg < self.random_avg:
            lines.append("Result: Random baseline outperforms model (needs improvement).")
        else:
            lines.append("Result: No significant difference.")
        return "\n".join(lines)


@dataclass
class RatingCollector:
    """Collect and persist user ratings."""

    ratings: list[dict] = field(default_factory=list)

    def add_rating(
        self,
        schedule_type: str,  # "model" or "random"
        schedule_id: int,
        rating: int,
        comment: str = "",
    ) -> None:
        self.ratings.append({
            "type": schedule_type,
            "schedule_id": schedule_id,
            "rating": rating,
            "comment": comment,
        })

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.ratings, f, indent=2)

    def load(self, path: str | Path) -> None:
        path = Path(path)
        if path.exists():
            with open(path, encoding="utf-8") as f:
                self.ratings = json.load(f)

    def evaluate(self) -> EvaluationResult:
        model_ratings = [
            r["rating"] for r in self.ratings if r["type"] == "model"
        ]
        random_ratings = [
            r["rating"] for r in self.ratings if r["type"] == "random"
        ]
        return EvaluationResult(
            model_ratings=model_ratings,
            random_ratings=random_ratings,
        )
