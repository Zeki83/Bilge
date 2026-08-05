#!/usr/bin/env python3
"""
Bilge OS - Interface Check

Controleert de actuele interfaces van de belangrijkste Bilge-modules.

Deze module:
- wijzigt geen bestanden;
- schrijft niet naar geheugen;
- roept Ollama niet aan;
- gebruikt geen externe verbindingen;
- toont constructors, methoden en dataclass-velden.
"""

from __future__ import annotations

import inspect
from dataclasses import fields, is_dataclass
from typing import Any

from bilge.boot_loader import BootLoader
from bilge.context_builder import ContextBuilder
from bilge.memory_manager import MemoryDecision, MemoryManager
from bilge.model_client import ModelResponse, OllamaModelClient
from bilge.models import BootState, ContextState, RuntimeState
from bilge.prompt_builder import PromptBuilder, PromptPackage
from bilge.reasoning_engine import ReasoningEngine, ReasoningPlan
from bilge.response_formatter import ResponseFormatter
from bilge.response_types import ResponseDraft, ResponseInstructions


CLASSES_TO_CHECK = [
    BootLoader,
    ContextBuilder,
    MemoryManager,
    ReasoningEngine,
    ResponseFormatter,
    PromptBuilder,
    OllamaModelClient,
]

DATACLASSES_TO_CHECK = [
    BootState,
    ContextState,
    RuntimeState,
    MemoryDecision,
    ReasoningPlan,
    ResponseInstructions,
    ResponseDraft,
    PromptPackage,
    ModelResponse,
]


def format_signature(value: Any) -> str:
    """Geeft veilig de Python-signature terug."""
    try:
        return str(inspect.signature(value))
    except (TypeError, ValueError):
        return "<geen signature beschikbaar>"


def public_methods(cls: type[Any]) -> list[tuple[str, str]]:
    """Geeft publieke methoden en hun signatures terug."""
    methods: list[tuple[str, str]] = []

    for name, member in inspect.getmembers(cls):
        if name.startswith("_"):
            continue

        if inspect.isfunction(member) or inspect.ismethod(member):
            methods.append(
                (name, format_signature(member))
            )

    return methods


def print_class_interface(cls: type[Any]) -> None:
    """Toont constructor en publieke methoden van één klasse."""
    print()
    print("=" * 72)
    print(f"KLASSE: {cls.__module__}.{cls.__name__}")
    print(f"Constructor: {format_signature(cls)}")
    print("Publieke methoden:")

    methods = public_methods(cls)

    if not methods:
        print("- Geen")
        return

    for name, signature in methods:
        print(f"- {name}{signature}")


def print_dataclass_interface(cls: type[Any]) -> None:
    """Toont alle velden van één dataclass."""
    print()
    print("=" * 72)
    print(f"DATACLASS: {cls.__module__}.{cls.__name__}")
    print(f"Constructor: {format_signature(cls)}")

    if not is_dataclass(cls):
        print("FOUT: dit object is geen dataclass.")
        return

    print("Velden:")

    for item in fields(cls):
        print(
            f"- {item.name}: {item.type!s}"
        )


def import_test() -> None:
    """Bevestigt dat alle benodigde imports werken."""
    print("===== Bilge Interface Check =====")
    print()
    print("Alle vereiste modules zijn succesvol geïmporteerd.")


def self_test() -> int:
    """Voert de volledige alleen-lezen interfacecontrole uit."""
    import_test()

    print()
    print("KLASSEN")

    for cls in CLASSES_TO_CHECK:
        print_class_interface(cls)

    print()
    print("DATAMODELLEN")

    for cls in DATACLASSES_TO_CHECK:
        print_dataclass_interface(cls)

    print()
    print("=" * 72)
    print("Interface Check geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
