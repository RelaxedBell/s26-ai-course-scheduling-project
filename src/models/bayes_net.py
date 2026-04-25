"""Naive Bayes Net for scoring course-student affinity.

Answers: "Given what this student likes and what they must complete,
how likely is each course to belong in a good schedule?"

Features are assumed conditionally independent given a latent preference class.
"""

from __future__ import annotations

import numpy as np
from sklearn.naive_bayes import GaussianNB

from src.data.course_loader import Course
from src.data.review_data import CourseSummary
from src.models.feature_extractor import (
    compute_preference_alignment,
    extract_course_features,
)
from src.student.preferences import StudentPreferences


class NaiveBayesScorer:
    """Score courses using a Gaussian Naive Bayes classifier.

    The model is trained on course features with binary labels:
    1 = student would like this course, 0 = would not.
    Labels are derived from preference alignment scores.
    """

    def __init__(self):
        self._model = GaussianNB()
        self._is_trained = False
        self._last_preferences = StudentPreferences()

    def train(
        self,
        courses: dict[str, Course],
        summaries: dict[str, CourseSummary],
        preferences: StudentPreferences,
        threshold: float = 0.6,
    ) -> None:
        """Train the model on course features with preference-derived labels.

        Args:
            courses: All available courses.
            summaries: Review summaries per course.
            preferences: Student preferences for deriving labels.
            threshold: Alignment score above which a course is labeled 'liked'.
        """
        features_list = []
        labels = []

        for code, course in courses.items():
            summary = summaries.get(code)
            feat = extract_course_features(course, summary)
            alignment = compute_preference_alignment(
                course, summary, preferences
            )

            features_list.append(feat)
            labels.append(1 if alignment >= threshold else 0)

        X = np.array(features_list)
        y = np.array(labels)

        # Ensure both classes are represented
        if len(set(y)) < 2:
            # If all same class, add a synthetic opposite example
            synthetic = np.mean(X, axis=0, keepdims=True)
            X = np.vstack([X, synthetic])
            y = np.append(y, 1 - y[0])

        self._model.fit(X, y)
        self._is_trained = True
        self._last_preferences = preferences

    def score_courses(
        self,
        candidate_courses: dict[str, Course],
        summaries: dict[str, CourseSummary],
    ) -> list[tuple[str, float]]:
        """Score candidate courses by calibrated affinity in [0, 1].

        Raw Naive Bayes probabilities can saturate near 0/1, so we apply a
        min-max calibration across the current candidate pool to improve
        rank readability in the UI while preserving ordering.

        Returns a list of (course_code, score) sorted by score descending.
        """
        if not self._is_trained:
            raise RuntimeError("Model must be trained before scoring")

        raw_scores: dict[str, float] = {}
        for code, course in candidate_courses.items():
            summary = summaries.get(code)
            feat = extract_course_features(course, summary).reshape(1, -1)
            prob = self._model.predict_proba(feat)[0]

            # prob[1] = P(liked=1 | features)
            liked_prob = prob[1] if len(prob) > 1 else prob[0]
            alignment = compute_preference_alignment(
                course, summary, self._last_preferences
            )
            raw_scores[code] = 0.7 * float(liked_prob) + 0.3 * alignment

        calibrated = self._calibrate_scores(raw_scores)
        results = list(calibrated.items())
        return sorted(results, key=lambda x: x[1], reverse=True)

    def score_single(
        self,
        course: Course,
        summary: CourseSummary | None,
    ) -> float:
        """Score a single course. Returns P(liked | features)."""
        if not self._is_trained:
            raise RuntimeError("Model must be trained before scoring")

        feat = extract_course_features(course, summary).reshape(1, -1)
        prob = self._model.predict_proba(feat)[0]
        return float(prob[1]) if len(prob) > 1 else float(prob[0])

    def _calibrate_scores(self, raw_scores: dict[str, float]) -> dict[str, float]:
        """Rescale raw probabilities to a readable [0.05, 0.95] range."""
        if not raw_scores:
            return {}
        values = list(raw_scores.values())
        low = min(values)
        high = max(values)
        if high - low < 1e-8:
            return {code: 0.5 for code in raw_scores}
        return {
            code: 0.05 + 0.9 * ((score - low) / (high - low))
            for code, score in raw_scores.items()
        }
