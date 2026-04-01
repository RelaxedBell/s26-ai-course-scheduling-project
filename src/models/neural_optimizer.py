"""Neural network for schedule ranking/optimization.

Takes schedule feature vectors and predicts a quality score (1-10).
Used to rerank schedules produced by the CSP solver.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from src.data.course_loader import Course
from src.data.review_data import CourseSummary
from src.models.constraint_solver import Schedule
from src.models.feature_extractor import FEATURE_DIM, extract_course_features

# Maximum courses per schedule for fixed-size input
MAX_COURSES = 6

# Features per course in schedule context
SCHEDULE_COURSE_FEATURES = FEATURE_DIM + 3  # + time_of_day, gap_before, bayes_score

# Total input dimension
INPUT_DIM = MAX_COURSES * SCHEDULE_COURSE_FEATURES


class ScheduleRankerNet(nn.Module):
    """Feed-forward network that predicts schedule quality."""

    def __init__(self, input_dim: int = INPUT_DIM):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, 1),
            nn.Sigmoid(),  # Output 0-1, scale to 1-10 externally
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


def _extract_schedule_features(
    schedule: Schedule,
    courses: dict[str, Course],
    summaries: dict[str, CourseSummary],
    bayes_scores: dict[str, float],
) -> np.ndarray:
    """Convert a schedule to a fixed-size feature vector."""
    from src.data.section_data import _parse_time

    features = []
    for i, section in enumerate(schedule.sections[:MAX_COURSES]):
        course = courses.get(section.course_code)
        summary = summaries.get(section.course_code)

        if course is not None:
            course_feat = extract_course_features(course, summary)
        else:
            course_feat = np.zeros(FEATURE_DIM, dtype=np.float32)

        # Additional schedule-context features
        time_of_day = _parse_time(section.start_time) / (24 * 60)
        gap_before = 0.0  # Simplified: could compute from previous section
        bayes_score = bayes_scores.get(section.course_code, 0.5)

        combined = np.concatenate([
            course_feat,
            np.array([time_of_day, gap_before, bayes_score], dtype=np.float32),
        ])
        features.append(combined)

    # Pad to MAX_COURSES
    while len(features) < MAX_COURSES:
        features.append(np.zeros(SCHEDULE_COURSE_FEATURES, dtype=np.float32))

    return np.concatenate(features)


class ScheduleRanker:
    """Train and use the neural network for schedule ranking."""

    def __init__(self):
        self._model = ScheduleRankerNet()
        self._is_trained = False

    def train(
        self,
        schedules: list[Schedule],
        labels: list[float],
        courses: dict[str, Course],
        summaries: dict[str, CourseSummary],
        bayes_scores: dict[str, float],
        epochs: int = 50,
        lr: float = 0.001,
    ) -> list[float]:
        """Train the model on schedule-quality pairs.

        Args:
            schedules: List of schedules.
            labels: Quality scores (0-1 normalized).
            courses: Course catalog.
            summaries: Review summaries.
            bayes_scores: Bayes Net scores per course.
            epochs: Training epochs.
            lr: Learning rate.

        Returns:
            List of per-epoch training losses.
        """
        X = np.array([
            _extract_schedule_features(s, courses, summaries, bayes_scores)
            for s in schedules
        ])
        y = np.array(labels, dtype=np.float32).reshape(-1, 1)

        X_tensor = torch.tensor(X, dtype=torch.float32)
        y_tensor = torch.tensor(y, dtype=torch.float32)

        optimizer = torch.optim.Adam(self._model.parameters(), lr=lr)
        loss_fn = nn.MSELoss()

        losses = []
        self._model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            pred = self._model(X_tensor)
            loss = loss_fn(pred, y_tensor)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())

        self._is_trained = True
        return losses

    def rerank_schedules(
        self,
        schedules: list[Schedule],
        courses: dict[str, Course],
        summaries: dict[str, CourseSummary],
        bayes_scores: dict[str, float],
    ) -> list[Schedule]:
        """Rerank schedules using the trained neural network.

        Returns schedules sorted by predicted quality (highest first).
        Does not add or remove schedules.
        """
        if not self._is_trained:
            raise RuntimeError("Model must be trained before reranking")

        X = np.array([
            _extract_schedule_features(s, courses, summaries, bayes_scores)
            for s in schedules
        ])
        X_tensor = torch.tensor(X, dtype=torch.float32)

        self._model.eval()
        with torch.no_grad():
            scores = self._model(X_tensor).squeeze(-1).numpy()

        # Create new Schedule objects with NN scores
        ranked = []
        for schedule, nn_score in zip(schedules, scores):
            ranked.append(Schedule(
                sections=schedule.sections,
                score=float(nn_score),
            ))

        ranked.sort(key=lambda s: s.score, reverse=True)
        return ranked

    def predict_score(
        self,
        schedule: Schedule,
        courses: dict[str, Course],
        summaries: dict[str, CourseSummary],
        bayes_scores: dict[str, float],
    ) -> float:
        """Predict quality score for a single schedule (0-1)."""
        if not self._is_trained:
            raise RuntimeError("Model must be trained before predicting")

        feat = _extract_schedule_features(
            schedule, courses, summaries, bayes_scores
        )
        X_tensor = torch.tensor(feat, dtype=torch.float32).unsqueeze(0)

        self._model.eval()
        with torch.no_grad():
            score = self._model(X_tensor).item()

        return score

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self._model.state_dict(), path)

    def load(self, path: str | Path) -> None:
        path = Path(path)
        self._model.load_state_dict(torch.load(path, weights_only=True))
        self._is_trained = True
