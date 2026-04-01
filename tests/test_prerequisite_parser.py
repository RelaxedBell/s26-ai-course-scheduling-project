"""Tests for the prerequisite parser and AST nodes."""

from src.data.prerequisite_ast import AndNode, CourseNode, ReqNode, UnionNode
from src.data.prerequisite_parser import parse_prerequisite


class TestParsePrerequisite:
    def test_none_string(self):
        assert parse_prerequisite("None") is None

    def test_empty_string(self):
        assert parse_prerequisite("") is None

    def test_non_string_input(self):
        assert parse_prerequisite(None) is None

    def test_single_course(self):
        result = parse_prerequisite("CS 2100")
        assert isinstance(result, CourseNode)
        assert result.value == ("CS", "2100")

    def test_implied_department_list(self):
        result = parse_prerequisite("CS 1110, 1111, 1112, or 1113.")
        assert isinstance(result, UnionNode)
        codes = [c.value for c in result.value]
        assert ("CS", "1110") in codes
        assert ("CS", "1113") in codes
        assert len(codes) == 4

    def test_or_expression(self):
        result = parse_prerequisite("MUSI 3390 or instructor permission")
        assert isinstance(result, UnionNode)
        assert isinstance(result.value[0], CourseNode)
        assert result.value[0].value == ("MUSI", "3390")
        assert isinstance(result.value[1], ReqNode)

    def test_complex_and_or(self):
        text = (
            "(STAT 1100 or STAT 1120 or STAT 2020) "
            "and (CS 1110 or CS 1111)"
        )
        result = parse_prerequisite(text)
        assert isinstance(result, AndNode)
        assert len(result.value) == 2
        assert isinstance(result.value[0], UnionNode)
        assert isinstance(result.value[1], UnionNode)

    def test_trailing_period_fix(self):
        """CS 3100 prereq had a trailing period causing parse failure."""
        text = "CS 2100 and CS 2120 and (APMA 1090 OR MATH 1310 OR MATH 1210)."
        result = parse_prerequisite(text)
        assert isinstance(result, AndNode)
        assert len(result.value) == 3

    def test_narrative_text_fallback(self):
        text = "3rd or 4th year Psychology or Cognitive Science major"
        result = parse_prerequisite(text)
        assert isinstance(result, ReqNode)
        assert not isinstance(result, (CourseNode, UnionNode, AndNode))

    def test_multiple_or_with_permission(self):
        text = "MUSI 3390 or MUSI 4543 or MUSI 4547 or instructor permission"
        result = parse_prerequisite(text)
        assert isinstance(result, UnionNode)
        assert len(result.value) == 4

    def test_parenthesized_text_and_courses(self):
        text = "(One semester of calculus) and (PHYS 1710 or PHYS 1420)"
        result = parse_prerequisite(text)
        assert isinstance(result, AndNode)
        assert isinstance(result.value[0], ReqNode)
        assert isinstance(result.value[1], UnionNode)


class TestAstSerialization:
    def test_course_node_roundtrip(self):
        node = CourseNode(value=("CS", "2100"))
        d = node.to_dict()
        restored = ReqNode.from_dict(d)
        assert isinstance(restored, CourseNode)
        assert restored.value == ("CS", "2100")

    def test_union_node_roundtrip(self):
        node = UnionNode(value=(
            CourseNode(value=("CS", "1110")),
            CourseNode(value=("CS", "1111")),
        ))
        d = node.to_dict()
        restored = ReqNode.from_dict(d)
        assert isinstance(restored, UnionNode)
        assert len(restored.value) == 2

    def test_and_node_roundtrip(self):
        node = AndNode(value=(
            CourseNode(value=("CS", "2100")),
            CourseNode(value=("CS", "2120")),
        ))
        d = node.to_dict()
        restored = ReqNode.from_dict(d)
        assert isinstance(restored, AndNode)
        assert len(restored.value) == 2

    def test_req_node_roundtrip(self):
        node = ReqNode(value="instructor permission")
        d = node.to_dict()
        restored = ReqNode.from_dict(d)
        assert restored.value == "instructor permission"

    def test_course_node_str(self):
        node = CourseNode(value=("CS", "2100"))
        assert str(node) == "CS 2100"

    def test_frozen_immutability(self):
        node = CourseNode(value=("CS", "2100"))
        try:
            node.value = ("CS", "3100")
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass
