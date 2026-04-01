"""Tests for course loading and prerequisite DAG."""

from pathlib import Path

from src.data.course_graph import CourseGraph
from src.data.course_loader import Course, CourseType, load_courses

COURSES_JSON = Path(__file__).resolve().parent.parent / "courses.json"


class TestCourseLoader:
    def test_load_courses(self):
        courses = load_courses(COURSES_JSON)
        assert len(courses) > 100
        assert "CS 1110" in courses

    def test_course_fields(self):
        courses = load_courses(COURSES_JSON)
        cs1110 = courses["CS 1110"]
        assert cs1110.name == "Introduction to Programming"
        assert cs1110.credits == 3
        assert cs1110.course_type == CourseType.PREREQUISITE

    def test_all_courses_have_code(self):
        courses = load_courses(COURSES_JSON)
        for code, course in courses.items():
            assert course.code == code

    def test_cs3100_prereqs_parsed(self):
        """CS 3100 had a trailing period bug — verify it parses now."""
        courses = load_courses(COURSES_JSON)
        from src.data.prerequisite_ast import AndNode
        cs3100 = courses["CS 3100"]
        assert cs3100.prerequisites_parsed is not None
        assert isinstance(cs3100.prerequisites_parsed, AndNode)


class TestCourseGraph:
    def setup_method(self):
        self.courses = load_courses(COURSES_JSON)
        self.graph = CourseGraph(self.courses)

    def test_topological_order(self):
        order = self.graph.topological_order()
        assert len(order) > 0
        # CS 1110 should come before CS 2100
        assert order.index("CS 1110") < order.index("CS 2100")

    def test_prerequisites_of_cs2100(self):
        prereqs = self.graph.get_prerequisites("CS 2100")
        assert "CS 1110" in prereqs or "CS 1111" in prereqs or "CS 1112" in prereqs

    def test_dependents_of_cs1110(self):
        deps = self.graph.get_dependents("CS 1110")
        assert "CS 2100" in deps
        assert "CS 2120" in deps

    def test_courses_available_with_nothing(self):
        available = self.graph.courses_available_after(set())
        # Courses with no prereqs should be available
        assert "CS 1110" in available
        # Courses with prereqs should not
        assert "CS 2100" not in available

    def test_courses_available_after_cs1110(self):
        available = self.graph.courses_available_after({"CS 1110"})
        assert "CS 2100" in available
        assert "CS 2120" in available
        assert "CS 2130" in available

    def test_prereqs_satisfied(self):
        assert self.graph.prerequisites_satisfied("CS 1110", set())
        assert not self.graph.prerequisites_satisfied("CS 3100", {"CS 2100"})
        assert self.graph.prerequisites_satisfied(
            "CS 2100", {"CS 1110"}
        )

    def test_transitive_prerequisites(self):
        all_prereqs = self.graph.get_all_prerequisites("CS 3100")
        # CS 3100 requires CS 2100 which requires CS 1110
        assert "CS 2100" in all_prereqs
        assert "CS 1110" in all_prereqs

    def test_no_cycles(self):
        assert self.graph.graph.is_directed()
        import networkx as nx
        assert nx.is_directed_acyclic_graph(self.graph.graph)
