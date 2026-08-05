#!/usr/bin/env python3
"""
Bilge OS - Models

Gedeelde datamodellen voor Bilge OS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class BaseState:
    """Basisklasse voor alle Runtime States."""

    completed: bool = False
    warnings: list[str] = field(default_factory=list, repr=False)
    errors: list[str] = field(default_factory=list, repr=False)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        repr=False,
    )

    @property
    def successful(self) -> bool:
        return self.completed and not self.errors


@dataclass(slots=True)
class BootState(BaseState):
    """Resultaat van de Boot Loader."""

    boot_completed: bool = False
    constitution_loaded: bool = False
    core_loaded: bool = False
    architecture_loaded: bool = False
    safety_loaded: bool = False
    loaded_documents: dict[str, str] = field(
        default_factory=dict,
        repr=False,
    )


@dataclass(slots=True)
class ContextState(BaseState):
    """Resultaat van de Context Builder."""

    context_completed: bool = False
    language: str = "nl"
    user_message: str = ""
    topic: str = ""
    intent: str = "unknown"
    message_type: str = "statement"
    urgency: str = "normal"
    confidence: float = 0.0
    probable_follow_up: bool = False
    memory_required: bool = False
    clarification_required: bool = False
    active_project: str | None = None
    relevant_documents: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RuntimeState(BaseState):
    """Centrale toestand van de Bilge Runtime."""

    boot: BootState | None = None
    context: ContextState | None = None


def self_test() -> int:
    boot = BootState()
    context = ContextState()
    runtime = RuntimeState(boot=boot, context=context)

    print("BootState:")
    print(boot)
    print()

    print("ContextState:")
    print(context)
    print()

    print("RuntimeState:")
    print(runtime)

    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
