"""Immutable AST node types for representing course prerequisites."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReqNode:
    """A generic requirement node (unparseable free-text fallback)."""

    value: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": "req", "value": self.value}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReqNode:
        node_type = d.get("type", "req")
        if node_type == "course":
            return CourseNode(value=(d["value"][0], d["value"][1]))
        if node_type == "union":
            return UnionNode(value=tuple(ReqNode.from_dict(c) for c in d["value"]))
        if node_type == "and":
            return AndNode(value=tuple(ReqNode.from_dict(c) for c in d["value"]))
        return cls(value=d["value"])


@dataclass(frozen=True, slots=True)
class CourseNode(ReqNode):
    """A single course requirement, e.g. ('CS', '2100')."""

    value: tuple[str, str]

    def __str__(self) -> str:
        return f"{self.value[0]} {self.value[1]}"

    def to_dict(self) -> dict[str, Any]:
        return {"type": "course", "value": list(self.value)}


@dataclass(frozen=True, slots=True)
class UnionNode(ReqNode):
    """Any one of the child requirements suffices (OR)."""

    value: tuple[ReqNode, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"type": "union", "value": [c.to_dict() for c in self.value]}


@dataclass(frozen=True, slots=True)
class AndNode(ReqNode):
    """All child requirements must be satisfied (AND)."""

    value: tuple[ReqNode, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"type": "and", "value": [c.to_dict() for c in self.value]}
