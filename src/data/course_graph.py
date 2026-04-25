"""Build and query a prerequisite DAG from parsed course data."""

from __future__ import annotations

import networkx as nx

from src.data.course_loader import Course
from src.data.prerequisite_ast import AndNode, CourseNode, ReqNode, UnionNode

# Mutually exclusive course groups: taking any one bars the others.
MUTUALLY_EXCLUSIVE_GROUPS: list[frozenset[str]] = [
    frozenset({"CS 1110", "CS 1111", "CS 1112", "CS 1113"}),
]


def _collect_course_nodes(node: ReqNode | None) -> list[CourseNode]:
    """Recursively collect all CourseNode leaves from an AST."""
    if node is None:
        return []
    if isinstance(node, CourseNode):
        return [node]
    if isinstance(node, (UnionNode, AndNode)):
        result = []
        for child in node.value:
            result.extend(_collect_course_nodes(child))
        return result
    return []


def _check_satisfied(node: ReqNode | None, completed: set[str]) -> bool:
    """Check whether a prerequisite AST is satisfied by completed courses.

    - CourseNode: satisfied if the course code is in completed
    - AndNode: all children must be satisfied
    - UnionNode: at least one child must be satisfied
    - ReqNode (free text): assumed satisfied (can't be checked programmatically)
    - None: no prerequisites, always satisfied
    """
    if node is None:
        return True
    if isinstance(node, CourseNode):
        code = f"{node.value[0]} {node.value[1]}"
        return code in completed
    if isinstance(node, AndNode):
        return all(_check_satisfied(child, completed) for child in node.value)
    if isinstance(node, UnionNode):
        return any(_check_satisfied(child, completed) for child in node.value)
    # Plain ReqNode (free text) — assume satisfied
    return True


class CourseGraph:
    """Directed acyclic graph of course prerequisites."""

    def __init__(self, courses: dict[str, Course]):
        self._courses = courses
        self._graph = nx.DiGraph()
        self._build()

    def _build(self) -> None:
        for code in self._courses:
            self._graph.add_node(code)

        for code, course in self._courses.items():
            for cn in _collect_course_nodes(course.prerequisites_parsed):
                prereq_code = f"{cn.value[0]} {cn.value[1]}"
                # Add edge: prereq -> course (must take prereq before course)
                if not self._graph.has_node(prereq_code):
                    self._graph.add_node(prereq_code)
                self._graph.add_edge(prereq_code, code)

    @property
    def graph(self) -> nx.DiGraph:
        return self._graph

    def get_prerequisites(self, course_code: str) -> set[str]:
        """Get all direct prerequisite course codes (all ancestors in the DAG)."""
        if course_code not in self._graph:
            return set()
        return set(self._graph.predecessors(course_code))

    def get_all_prerequisites(self, course_code: str) -> set[str]:
        """Get all transitive prerequisites (all ancestors)."""
        if course_code not in self._graph:
            return set()
        return nx.ancestors(self._graph, course_code)

    def get_dependents(self, course_code: str) -> set[str]:
        """Get courses that directly require this course."""
        if course_code not in self._graph:
            return set()
        return set(self._graph.successors(course_code))

    def topological_order(self) -> list[str]:
        """Return courses in topological order (prerequisites first)."""
        return list(nx.topological_sort(self._graph))

    def prerequisites_satisfied(
        self, course_code: str, completed: set[str]
    ) -> bool:
        """Check if the parsed prerequisite AST is satisfied by completed courses."""
        course = self._courses.get(course_code)
        if course is None:
            return True
        return _check_satisfied(course.prerequisites_parsed, completed)

    def courses_available_after(self, completed: set[str]) -> set[str]:
        """Return courses whose prerequisites are satisfied and not yet taken.

        Excludes courses that are mutually exclusive with already-completed
        courses (e.g. CS 1111 is excluded if CS 1110 was taken).
        """
        # Build the set of codes blocked by mutual exclusion
        excluded: set[str] = set()
        for group in MUTUALLY_EXCLUSIVE_GROUPS:
            if completed & group:
                excluded |= group

        available = set()
        for code in self._courses:
            if code in completed or code in excluded:
                continue
            if self.prerequisites_satisfied(code, completed):
                available.add(code)
        return available
