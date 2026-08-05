#!/usr/bin/env python3
"""
Bilge OS - Memory Manager

Bepaalt welke geheugentypen relevant zijn voor een gebruikersbericht.

Deze versie:
- kan meerdere geheugentypen selecteren;
- zet de geheugentypen in prioriteitsvolgorde;
- slaat nog niets op;
- verwijdert niets;
- leest nog geen persoonlijke herinneringen;
- gebruikt geen externe apps of online diensten.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bilge.models import ContextState


class MemoryManagerError(Exception):
    """Basisfout voor problemen binnen de Memory Manager."""


@dataclass(slots=True)
class MemoryDecision:
    """Beslissing van de Memory Manager."""

    memory_types: list[str] = field(default_factory=list)
    reasons: dict[str, str] = field(default_factory=dict)
    required: bool = False

    @property
    def primary_memory(self) -> str:
        """Geeft het geheugen met de hoogste prioriteit terug."""
        if not self.memory_types:
            return "none"

        return self.memory_types[0]


class MemoryManager:
    """Bepaalt welke geheugentypen mogelijk relevant zijn."""

    SHORT_MEMORY_PHRASES = {
        "waar waren we",
        "waar waren we gebleven",
        "ga verder",
        "laten we verder gaan",
        "kom maar op",
        "doe maar",
        "zoals net",
        "wat zei je net",
        "wat bedoelde je net",
        "devam",
        "nerede kalmıştık",
    }

    PROJECT_WORDS = {
        "bilge",
        "project",
        "sprint",
        "runtime",
        "engine",
        "core",
        "context",
        "memory",
        "reasoning",
        "response",
        "safety",
        "vps",
        "server",
        "app",
        "avatar",
        "stem",
    }

    LONG_MEMORY_PHRASES = {
        "wat weet je over mij",
        "wat herinner je je",
        "mijn voorkeur",
        "mijn voorkeuren",
        "zoals ik altijd wil",
        "onthoud dit",
        "vergeet dit",
        "pas mijn voorkeur aan",
        "benim hakkımda ne biliyorsun",
        "bunu hatırla",
        "bunu unut",
    }

    MEMORY_PRIORITY = {
        "long": 1,
        "short": 2,
        "project": 3,
    }

    def normalize_message(self, message: str) -> str:
        """Maakt een bericht geschikt voor eenvoudige analyse."""
        return " ".join(message.lower().strip().split())

    def extract_words(self, message: str) -> set[str]:
        """Haalt losse woorden uit een bericht."""
        return set(
            re.findall(
                r"[A-Za-zÀ-ÖØ-öø-ÿĞğİıŞşÇç]+",
                message.lower(),
            )
        )

    def detect_long_memory(
        self,
        message: str,
    ) -> tuple[bool, str]:
        """Controleert of langdurig geheugen relevant is."""
        if any(
            phrase in message
            for phrase in self.LONG_MEMORY_PHRASES
        ):
            return (
                True,
                "Het bericht verwijst naar blijvende voorkeuren, "
                "persoonlijke herinneringen of geheugenbeheer.",
            )

        return False, ""

    def detect_short_memory(
        self,
        context: ContextState,
        message: str,
    ) -> tuple[bool, str]:
        """Controleert of recente gesprekscontext nodig is."""
        if context.probable_follow_up:
            return (
                True,
                "Het bericht is door de Context Builder herkend als "
                "een waarschijnlijk vervolg op de recente sessie.",
            )

        if any(
            phrase in message
            for phrase in self.SHORT_MEMORY_PHRASES
        ):
            return (
                True,
                "Het bericht verwijst naar iets uit het huidige of "
                "recente gesprek.",
            )

        return False, ""

    def detect_project_memory(
        self,
        words: set[str],
    ) -> tuple[bool, str]:
        """Controleert of projectgeheugen relevant is."""
        matching_words = sorted(
            words.intersection(self.PROJECT_WORDS)
        )

        if matching_words:
            return (
                True,
                "Het bericht bevat projectgerelateerde termen: "
                + ", ".join(matching_words)
                + ".",
            )

        return False, ""

    def decide(self, context: ContextState) -> MemoryDecision:
        """
        Bepaalt welke geheugentypen nodig zijn.

        Meerdere geheugentypen kunnen tegelijk relevant zijn.
        """
        if not context.context_completed:
            raise MemoryManagerError(
                "De ContextState is nog niet voltooid."
            )

        message = self.normalize_message(context.user_message)

        if not message:
            raise MemoryManagerError(
                "De ContextState bevat geen gebruikersbericht."
            )

        words = self.extract_words(message)
        selected: list[str] = []
        reasons: dict[str, str] = {}

        long_needed, long_reason = self.detect_long_memory(
            message
        )
        short_needed, short_reason = self.detect_short_memory(
            context,
            message,
        )
        project_needed, project_reason = self.detect_project_memory(
            words
        )

        if long_needed:
            selected.append("long")
            reasons["long"] = long_reason

        if short_needed:
            selected.append("short")
            reasons["short"] = short_reason

        if project_needed:
            selected.append("project")
            reasons["project"] = project_reason

        selected.sort(
            key=lambda memory_type: self.MEMORY_PRIORITY[
                memory_type
            ]
        )

        return MemoryDecision(
            memory_types=selected,
            reasons=reasons,
            required=bool(selected),
        )


def print_decision(
    context: ContextState,
    decision: MemoryDecision,
) -> None:
    """Toont een MemoryDecision overzichtelijk."""
    print()
    print(f"Bericht          : {context.user_message}")
    print(f"Geheugen nodig   : {decision.required}")
    print(f"Hoofdgeheugen    : {decision.primary_memory}")

    if not decision.memory_types:
        print("Geheugenvolgorde : none")
        print(
            "Reden             : Voor dit bericht is geen geheugen "
            "nodig."
        )
        return

    print(
        "Geheugenvolgorde : "
        + " -> ".join(decision.memory_types)
    )

    for memory_type in decision.memory_types:
        print(
            f"Reden {memory_type:<7}: "
            f"{decision.reasons[memory_type]}"
        )


def self_test() -> int:
    """Voert lokale tests uit zonder geheugenopslag."""
    manager = MemoryManager()

    tests = [
        (
            ContextState(
                completed=True,
                context_completed=True,
                user_message="Waar waren we gebleven?",
                probable_follow_up=True,
            ),
            ["short"],
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                user_message="Ga verder met Bilge Runtime.",
                probable_follow_up=True,
            ),
            ["short", "project"],
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                user_message="Wat weet je over mij?",
            ),
            ["long"],
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                user_message=(
                    "Onthoud mijn voorkeur voor het Bilge-project."
                ),
            ),
            ["long", "project"],
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                user_message="Hoeveel is twee plus twee?",
            ),
            [],
        ),
    ]

    print("===== Memory Manager-test =====")

    for context, expected_types in tests:
        decision = manager.decide(context)
        print_decision(context, decision)

        if decision.memory_types != expected_types:
            print()
            print(
                "FOUT: verwacht "
                f"{expected_types}, maar kreeg "
                f"{decision.memory_types}."
            )
            return 1

    print()
    print("Memory Manager-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
