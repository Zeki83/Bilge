#!/usr/bin/env python3
"""
Bilge OS - Memory Pipeline

Veilige beslislaag voor blijvende geheugenacties.

Deze eerste versie:
- analyseert of een bericht een expliciet geheugenverzoek bevat;
- bepaalt een geschikte geheugencategorie;
- slaat alleen expliciet aangevraagde herinneringen op;
- verwijdert nooit automatisch herinneringen;
- wijzigt Project Memory nog niet automatisch;
- weigert herkenbare geheime informatie;
- gebruikt geen externe apps of diensten.

Belangrijk:
Gewone gesprekken worden niet automatisch permanent onthouden.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from bilge.long_memory import (
    InvalidMemoryError,
    LongMemory,
    LongMemoryError,
    MemoryRecord,
    SensitiveMemoryError,
)
from bilge.models import ContextState


MemoryAction = Literal[
    "none",
    "store_long",
    "forget_request",
    "project_candidate",
]


class MemoryPipelineError(Exception):
    """Basisfout voor problemen binnen de Memory Pipeline."""


class InvalidMemoryPipelineInputError(MemoryPipelineError):
    """De aangeleverde context is ongeldig."""


@dataclass(slots=True)
class MemoryActionPlan:
    """Controleerbaar plan voor één mogelijke geheugenactie."""

    action: MemoryAction = "none"
    category: str = "other"
    content: str = ""
    reason: str = ""
    explicit_request: bool = False
    requires_confirmation: bool = False
    allowed: bool = False
    completed: bool = False


@dataclass(slots=True)
class MemoryPipelineResult:
    """Resultaat van de veilige geheugenverwerking."""

    plan: MemoryActionPlan
    stored_record: MemoryRecord | None = None
    stored: bool = False
    completed: bool = False


class MemoryPipeline:
    """Beoordeelt en verwerkt expliciete geheugenverzoeken."""

    REMEMBER_PREFIXES = (
        "onthoud dat ",
        "onthoud dit: ",
        "onthoud: ",
        "bewaar dat ",
        "bewaar dit: ",
        "remember that ",
        "bunu hatırla: ",
        "şunu hatırla: ",
        "unutma ki ",
    )

    FORGET_PREFIXES = (
        "vergeet dat ",
        "vergeet dit: ",
        "vergeet: ",
        "forget that ",
        "bunu unut: ",
        "şunu unut: ",
    )

    PROJECT_WORDS = {
        "bilge",
        "project",
        "sprint",
        "runtime",
        "module",
        "engine",
        "roadmap",
        "project memory",
    }

    PREFERENCE_SIGNALS = (
        "ik wil dat ",
        "ik heb liever ",
        "mijn voorkeur is ",
        "spreek altijd ",
        "antwoord altijd ",
        "tercihim ",
        "her zaman ",
    )

    GOAL_SIGNALS = (
        "mijn doel is ",
        "ik wil bereiken ",
        "langetermijndoel ",
        "hedefim ",
        "amacım ",
    )

    WORKFLOW_SIGNALS = (
        "werk altijd ",
        "doe voortaan ",
        "vanaf nu ",
        "onze werkwijze ",
        "bundan sonra ",
        "çalışma şeklim ",
    )

    SENSITIVE_PATTERNS = (
        re.compile(
            r"\b(?:password|wachtwoord|passwd|pin(?:code)?)\b"
            r"\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:api[_ -]?key|access[_ -]?token|secret[_ -]?key)\b"
            r"\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:2fa|otp|verification code|verificatiecode)\b"
            r"\s*[:=]?\s*\d{4,8}\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:seed phrase|recovery phrase|herstelzin)\b"
            r"\s*[:=]\s*.+",
            re.IGNORECASE,
        ),
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:cvv|cvc)\b\s*[:=]?\s*\d{3,4}\b",
            re.IGNORECASE,
        ),
    )

    def __init__(
        self,
        long_memory: LongMemory | None = None,
    ) -> None:
        self.long_memory = long_memory or LongMemory()

    @staticmethod
    def normalize_text(value: str) -> str:
        """Normaliseert witruimte."""
        return " ".join(value.strip().split())

    def contains_sensitive_information(self, text: str) -> bool:
        """Controleert op herkenbare geheime informatie."""
        return any(
            pattern.search(text)
            for pattern in self.SENSITIVE_PATTERNS
        )

    @staticmethod
    def starts_with_prefix(
        message: str,
        prefixes: tuple[str, ...],
    ) -> str | None:
        """Geeft het gevonden voorvoegsel terug."""
        lowered = message.casefold()

        for prefix in prefixes:
            if lowered.startswith(prefix.casefold()):
                return prefix

        return None

    @staticmethod
    def strip_prefix(
        message: str,
        prefix: str,
    ) -> str:
        """Verwijdert één gevonden voorvoegsel."""
        return message[len(prefix):].strip(" .:-")

    def determine_category(self, content: str) -> str:
        """Schat de passende Long Memory-categorie."""
        lowered = content.casefold()

        if any(
            signal in lowered
            for signal in self.PREFERENCE_SIGNALS
        ):
            return "preference"

        if any(
            signal in lowered
            for signal in self.GOAL_SIGNALS
        ):
            return "goal"

        if any(
            signal in lowered
            for signal in self.WORKFLOW_SIGNALS
        ):
            return "workflow"

        return "fact"

    def is_project_related(self, content: str) -> bool:
        """Controleert voorzichtig op projectgerelateerde inhoud."""
        words = set(
            re.findall(
                r"[A-Za-zÀ-ÖØ-öø-ÿĞğİıŞşÇç]+",
                content.casefold(),
            )
        )

        return bool(words.intersection(self.PROJECT_WORDS))

    def plan(
        self,
        context: ContextState,
    ) -> MemoryActionPlan:
        """Maakt een veilig geheugenactieplan."""
        if not context.context_completed or not context.successful:
            raise InvalidMemoryPipelineInputError(
                "De ContextState is niet succesvol voltooid."
            )

        message = self.normalize_text(context.user_message)

        if not message:
            raise InvalidMemoryPipelineInputError(
                "Het gebruikersbericht is leeg."
            )

        remember_prefix = self.starts_with_prefix(
            message,
            self.REMEMBER_PREFIXES,
        )

        forget_prefix = self.starts_with_prefix(
            message,
            self.FORGET_PREFIXES,
        )

        if forget_prefix is not None:
            content = self.strip_prefix(
                message,
                forget_prefix,
            )

            return MemoryActionPlan(
                action="forget_request",
                content=content,
                reason=(
                    "Zeki vraagt expliciet om informatie te vergeten. "
                    "Permanente verwijdering vereist eerst bevestiging "
                    "en een concrete geheugenkeuze."
                ),
                explicit_request=True,
                requires_confirmation=True,
                allowed=False,
                completed=True,
            )

        if remember_prefix is None:
            if self.is_project_related(message):
                return MemoryActionPlan(
                    action="project_candidate",
                    content=message,
                    reason=(
                        "Het bericht lijkt projectgerelateerd, maar bevat "
                        "geen expliciete opdracht om het permanent op te slaan."
                    ),
                    explicit_request=False,
                    requires_confirmation=True,
                    allowed=False,
                    completed=True,
                )

            return MemoryActionPlan(
                action="none",
                reason=(
                    "Er is geen expliciete opdracht om dit bericht "
                    "permanent te onthouden."
                ),
                explicit_request=False,
                requires_confirmation=False,
                allowed=False,
                completed=True,
            )

        content = self.strip_prefix(
            message,
            remember_prefix,
        )

        if not content:
            return MemoryActionPlan(
                action="store_long",
                reason=(
                    "Er is wel een geheugenopdracht, maar er ontbreekt "
                    "inhoud om op te slaan."
                ),
                explicit_request=True,
                requires_confirmation=True,
                allowed=False,
                completed=True,
            )

        if self.contains_sensitive_information(content):
            return MemoryActionPlan(
                action="store_long",
                content=content,
                reason=(
                    "De informatie lijkt geheim of gevoelig en mag "
                    "daarom niet permanent worden opgeslagen."
                ),
                explicit_request=True,
                requires_confirmation=False,
                allowed=False,
                completed=True,
            )

        category = self.determine_category(content)

        return MemoryActionPlan(
            action="store_long",
            category=category,
            content=content,
            reason=(
                "Zeki heeft expliciet gevraagd deze niet-geheime "
                "informatie blijvend te onthouden."
            ),
            explicit_request=True,
            requires_confirmation=False,
            allowed=True,
            completed=True,
        )

    def execute(
        self,
        context: ContextState,
    ) -> MemoryPipelineResult:
        """
        Voert uitsluitend veilige, expliciete Long Memory-opslag uit.

        Vergeten en Project Memory-wijzigingen worden nog niet uitgevoerd.
        """
        plan = self.plan(context)

        if not plan.allowed:
            return MemoryPipelineResult(
                plan=plan,
                stored_record=None,
                stored=False,
                completed=True,
            )

        if plan.action != "store_long":
            return MemoryPipelineResult(
                plan=plan,
                stored_record=None,
                stored=False,
                completed=True,
            )

        try:
            record = self.long_memory.add_memory(
                plan.category,
                plan.content,
                context=(
                    "Expliciet geheugenverzoek uit een gesprek met Zeki."
                ),
                source="user",
            )
        except (
            SensitiveMemoryError,
            InvalidMemoryError,
            LongMemoryError,
        ) as exc:
            raise MemoryPipelineError(
                f"Long Memory-opslag mislukt: {exc}"
            ) from exc

        return MemoryPipelineResult(
            plan=plan,
            stored_record=record,
            stored=True,
            completed=True,
        )


def print_result(
    context: ContextState,
    result: MemoryPipelineResult,
) -> None:
    """Toont de geheugenbeslissing overzichtelijk."""
    print()
    print(f"Bericht      : {context.user_message}")
    print(f"Actie        : {result.plan.action}")
    print(f"Categorie    : {result.plan.category}")
    print(f"Expliciet    : {result.plan.explicit_request}")
    print(f"Bevestiging  : {result.plan.requires_confirmation}")
    print(f"Toegestaan   : {result.plan.allowed}")
    print(f"Opgeslagen   : {result.stored}")
    print(f"Reden        : {result.plan.reason}")


def self_test() -> int:
    """Test de Memory Pipeline met tijdelijke lokale opslag."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    print("===== Memory Pipeline-test =====")

    with TemporaryDirectory() as temporary_directory:
        test_file = (
            Path(temporary_directory)
            / "long_memory_test.json"
        )

        pipeline = MemoryPipeline(
            long_memory=LongMemory(test_file)
        )

        tests = [
            (
                ContextState(
                    completed=True,
                    context_completed=True,
                    language="nl",
                    user_message=(
                        "Onthoud dat ik complete bestanden wil "
                        "in plaats van losse regels."
                    ),
                    confidence=1.0,
                ),
                "store_long",
                True,
            ),
            (
                ContextState(
                    completed=True,
                    context_completed=True,
                    language="nl",
                    user_message=(
                        "Vandaag heb ik koffie gedronken."
                    ),
                    confidence=1.0,
                ),
                "none",
                False,
            ),
            (
                ContextState(
                    completed=True,
                    context_completed=True,
                    language="nl",
                    user_message=(
                        "Ga verder met het Bilge Runtime project."
                    ),
                    confidence=1.0,
                ),
                "project_candidate",
                False,
            ),
            (
                ContextState(
                    completed=True,
                    context_completed=True,
                    language="nl",
                    user_message=(
                        "Vergeet dat ik complete bestanden wil."
                    ),
                    confidence=1.0,
                ),
                "forget_request",
                False,
            ),
            (
                ContextState(
                    completed=True,
                    context_completed=True,
                    language="nl",
                    user_message=(
                        "Onthoud dit: wachtwoord: SuperGeheim123"
                    ),
                    confidence=1.0,
                ),
                "store_long",
                False,
            ),
        ]

        for context, expected_action, expected_stored in tests:
            result = pipeline.execute(context)
            print_result(context, result)

            if result.plan.action != expected_action:
                print()
                print(
                    f"FOUT: verwacht actie '{expected_action}', "
                    f"maar kreeg '{result.plan.action}'."
                )
                return 1

            if result.stored != expected_stored:
                print()
                print(
                    f"FOUT: verwacht opgeslagen={expected_stored}, "
                    f"maar kreeg {result.stored}."
                )
                return 1

        if pipeline.long_memory.memory_count() != 1:
            print()
            print(
                "FOUT: er hoort precies één blijvende "
                "herinnering te zijn opgeslagen."
            )
            return 1

    print()
    print("Memory Pipeline-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
