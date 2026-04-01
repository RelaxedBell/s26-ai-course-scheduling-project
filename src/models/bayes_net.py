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

    def score_courses(
        self,
        candidate_courses: dict[str, Course],
        summaries: dict[str, CourseSummary],
    ) -> list[tuple[str, float]]:
        """Score candidate courses by P(liked | features).

        Returns a list of (course_code, probability) sorted by score descending.
        """
        if not self._is_trained:
            raise RuntimeError("Model must be trained before scoring")

        results = []
        for code, course in candidate_courses.items():
            summary = summaries.get(code)
            feat = extract_course_features(course, summary).reshape(1, -1)
            prob = self._model.predict_proba(feat)[0]

            # prob[1] = P(liked=1 | features)
            liked_prob = prob[1] if len(prob) > 1 else prob[0]
            results.append((code, float(liked_prob)))

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
