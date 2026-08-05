#!/usr/bin/env python3
"""
Bilge OS - Response Types

Gedeelde datamodellen voor het Response System.

Deze module:
- bevat alleen datastructuren;
- maakt nog geen definitief antwoord;
- stuurt geen AI-model aan;
- gebruikt geen externe apps of diensten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ResponseLength = Literal[
    "very_short",
    "short",
    "normal",
    "detailed",
]

ResponseFormat = Literal[
    "plain",
    "paragraphs",
    "steps",
    "comparison",
    "checklist",
    "question",
]

ResponseTone = Literal[
    "warm",
    "neutral",
    "professional",
    "motivating",
    "empathetic",
    "cautious",
]

SafetyMode = Literal[
    "normal",
    "warning",
    "restricted",
]


@dataclass(slots=True)
class ResponseInstructions:
    """
    Concrete instructies voor het formuleren van een antwoord.
    """

    language: str = "nl"
    tone: ResponseTone = "warm"
    length: ResponseLength = "normal"
    format: ResponseFormat = "paragraphs"

    include_explanation: bool = True
    include_steps: bool = False
    include_comparison: bool = False
    acknowledge_emotion: bool = False
    ask_clarifying_question: bool = False

    clarification_question: str = ""
    safety_mode: SafetyMode = "normal"
    safety_message: str = ""

    use_memory_types: list[str] = field(default_factory=list)

    objective: str = ""
    completed: bool = False


@dataclass(slots=True)
class ResponseDraft:
    """
    Voorlopige antwoordstructuur vóór het AI-model antwoord genereert.
    """

    instructions: ResponseInstructions
    opening: str = ""
    body_guidance: list[str] = field(default_factory=list)
    closing_guidance: str = ""
    forbidden_actions: list[str] = field(default_factory=list)
    completed: bool = False


def self_test() -> int:
    """Test of de Response-datamodellen correct werken."""
    instructions = ResponseInstructions(
        language="nl",
        tone="warm",
        length="short",
        format="steps",
        include_steps=True,
        objective="create_plan",
        completed=True,
    )

    draft = ResponseDraft(
        instructions=instructions,
        opening="Reageer warm en direct.",
        body_guidance=[
            "Geef een helder stappenplan.",
            "Gebruik eenvoudige taal.",
        ],
        closing_guidance=(
            "Sluit af zonder een onnodige extra vraag."
        ),
        forbidden_actions=[
            "Geen externe apps aansturen.",
            "Geen betalingen uitvoeren.",
        ],
        completed=True,
    )

    print("===== Response Types-test =====")
    print()
    print("ResponseInstructions:")
    print(instructions)
    print()
    print("ResponseDraft:")
    print(draft)

    if not instructions.completed:
        print("FOUT: ResponseInstructions is niet voltooid.")
        return 1

    if not draft.completed:
        print("FOUT: ResponseDraft is niet voltooid.")
        return 1

    if not draft.instructions.include_steps:
        print("FOUT: stappeninstructie ontbreekt.")
        return 1

    print()
    print("Response Types-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
