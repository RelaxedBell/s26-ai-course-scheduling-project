"""Recursive-descent parser for UVA prerequisite strings.

Converts free-text prerequisite descriptions into structured AST nodes.
Extracted and improved from the original preprocessor.ipynb.
"""

from __future__ import annotations

import re

from src.data.prerequisite_ast import AndNode, CourseNode, ReqNode, UnionNode

COURSE_EXACT_PATTERN = re.compile(r"^([A-Z]{2,4})\s*(\d{4})$")
COURSE_ANY_PATTERN = re.compile(r"\b[A-Z]{2,4}\s*\d{4}\b")
IMPLIED_DEPT_LIST_PATTERN = re.compile(
    r"^([A-Z]{2,4})\s*((?:\d{4}\s*,\s*)*\d{4}\s*,?\s*or\s*\d{4})$",
    re.IGNORECASE,
)
OP_PATTERN = re.compile(r"(?i)\b(and|or)\b")
PERMISSION_PATTERN = re.compile(
    r"(?i)\b(instructor permission|permission of instructor"
    r"|consent of instructor|instructor consent)\b"
)


def _parse_implied_department_list(text: str) -> UnionNode | None:
    match = IMPLIED_DEPT_LIST_PATTERN.fullmatch(text)
    if not match:
        return None
    dept = match.group(1).upper()
    number_chunk = match.group(2)
    numbers = re.findall(r"\d{4}", number_chunk)
    if len(numbers) < 2:
        return None
    return UnionNode(value=tuple(CourseNode(value=(dept, num)) for num in numbers))


def _to_node(text: str) -> ReqNode:
    text = text.strip(" ,.;")
    implied = _parse_implied_department_list(text)
    if implied is not None:
        return implied
    match = COURSE_EXACT_PATTERN.fullmatch(text)
    if match:
        return CourseNode(value=(match.group(1), match.group(2)))
    return ReqNode(value=text)


def _has_permission_phrase(fragment: str) -> bool:
    return PERMISSION_PATTERN.search(fragment) is not None


def _is_logical_operator(left_fragment: str, right_fragment: str, op: str) -> bool:
    left = left_fragment.strip()
    right = right_fragment.strip()
    if not left or not right:
        return False
    if left.endswith(",") or right.startswith(","):
        return False

    left_has_course = COURSE_ANY_PATTERN.search(left) is not None
    right_has_course = COURSE_ANY_PATTERN.search(right) is not None
    left_group = left.endswith(")")
    right_group = right.startswith("(")
    left_has_permission = _has_permission_phrase(left)
    right_has_permission = _has_permission_phrase(right)

    if op == "and":
        return (left_has_course or left_group) and (right_has_course or right_group)
    return (
        (left_has_course and right_has_course)
        or (left_group and right_group)
        or ((left_has_course or left_group) and right_has_permission)
        or ((right_has_course or right_group) and left_has_permission)
    )


def _peek_right_fragment(expr: str, start: int) -> str:
    i = start
    n = len(expr)
    while i < n and expr[i].isspace():
        i += 1
    if i < n and expr[i] == "(":
        return "("
    j = i
    while j < n:
        if expr[j] in "()":
            break
        match = OP_PATTERN.match(expr, j)
        if match:
            break
        j += 1
    return expr[i:j]


def _tokenize(expr: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    buffer: list[str] = []
    i = 0
    n = len(expr)

    def flush_text():
        text = "".join(buffer).strip()
        if text:
            tokens.append(("TEXT", text))
        buffer.clear()

    while i < n:
        ch = expr[i]

        if ch == "(":
            flush_text()
            tokens.append(("LPAREN", ch))
            i += 1
            continue

        if ch == ")":
            flush_text()
            tokens.append(("RPAREN", ch))
            i += 1
            continue

        op_match = OP_PATTERN.match(expr, i)
        if op_match:
            op_text = op_match.group(1)
            op = op_text.lower()
            left_fragment = "".join(buffer)
            if not left_fragment.strip() and tokens and tokens[-1][0] == "RPAREN":
                left_fragment = ")"

            right_fragment = _peek_right_fragment(expr, op_match.end())
            if not right_fragment.strip():
                j = op_match.end()
                while j < n and expr[j].isspace():
                    j += 1
                if j < n and expr[j] == "(":
                    right_fragment = "("

            if _is_logical_operator(left_fragment, right_fragment, op):
                flush_text()
                tokens.append((op.upper(), op))
            else:
                buffer.append(op_text)

            i = op_match.end()
            continue

        buffer.append(ch)
        i += 1

    flush_text()
    return tokens


def _collapse_union(nodes: list[ReqNode]) -> ReqNode:
    flat: list[ReqNode] = []
    for node in nodes:
        if isinstance(node, UnionNode):
            flat.extend(node.value)
        else:
            flat.append(node)
    if len(flat) == 1:
        return flat[0]
    return UnionNode(value=tuple(flat))


def _collapse_and(nodes: list[ReqNode]) -> ReqNode:
    flat: list[ReqNode] = []
    for node in nodes:
        if isinstance(node, AndNode):
            flat.extend(node.value)
        else:
            flat.append(node)
    if len(flat) == 1:
        return flat[0]
    return AndNode(value=tuple(flat))


class PrereqParser:
    """Recursive-descent parser for prerequisite expressions."""

    def __init__(self, expr: str):
        self.tokens = _tokenize(expr)
        self.i = 0

    def _peek(self) -> tuple[str, str] | None:
        if self.i >= len(self.tokens):
            return None
        return self.tokens[self.i]

    def _consume(self) -> tuple[str, str] | None:
        token = self._peek()
        if token is None:
            return None
        self.i += 1
        return token

    def parse(self) -> ReqNode:
        if not self.tokens:
            return ReqNode(value="")
        node = self._parse_or()
        if self._peek() is not None:
            raise ValueError(f"Unexpected token near {self._peek()}")
        return node

    def _parse_or(self) -> ReqNode:
        left = self._parse_and()
        options = [left]
        while self._peek() and self._peek()[0] == "OR":
            self._consume()
            options.append(self._parse_and())
        return _collapse_union(options)

    def _parse_and(self) -> ReqNode:
        left = self._parse_atom()
        terms = [left]
        while self._peek() and self._peek()[0] == "AND":
            self._consume()
            terms.append(self._parse_atom())
        return _collapse_and(terms)

    def _parse_atom(self) -> ReqNode:
        token = self._peek()
        if token is None:
            raise ValueError("Unexpected end of expression")

        token_type, token_text = token
        if token_type == "LPAREN":
            self._consume()
            node = self._parse_or()
            close = self._consume()
            if close is None or close[0] != "RPAREN":
                raise ValueError("Missing closing parenthesis")
            return node

        if token_type == "TEXT":
            self._consume()
            return _to_node(token_text)

        raise ValueError(f"Unexpected token {token_text!r}")


def parse_prerequisite(expr: str) -> ReqNode | None:
    """Parse a prerequisite string into an AST node.

    Returns None for empty or 'None' prerequisites.
    Falls back to a plain ReqNode for unparseable text.
    """
    if not isinstance(expr, str):
        return None
    cleaned = " ".join(expr.split())
    if not cleaned or cleaned.lower().startswith("none"):
        return None

    # Strip trailing period that causes parse failures (e.g. CS 3100 prereqs)
    cleaned = cleaned.rstrip(".")

    parser = PrereqParser(cleaned)
    try:
        return parser.parse()
    except ValueError:
        return ReqNode(value=cleaned)
