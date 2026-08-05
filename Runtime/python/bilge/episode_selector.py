#!/usr/bin/env python3
"""
Bilge OS - Episode Selector

Bepaalt of een afgeronde gespreksronde geschikt is voor Episodic Memory.

Deze module:
- bewaart zelf nog niets;
- roept geen taalmodel aan;
- voert geen externe acties uit;
- weigert mogelijk gevoelige inhoud;
- voorkomt opslag van korte, triviale gesprekken;
- herkent voorkeuren, doelen, beslissingen, mijlpalen en projectwerk;
- produceert een controleerbaar EpisodeSelectionPlan.

De daadwerkelijke opslag gebeurt later via EpisodicMemory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


EpisodeDecision = Literal[
    "store",
    "skip",
    "reject_sensitive",
]


class EpisodeSelectorError(Exception):
    """Basisfout voor problemen binnen de Episode Selector."""


class InvalidEpisodeSelectorInputError(EpisodeSelectorError):
    """De aangeleverde gespreksinhoud is ongeldig."""


@dataclass(slots=True)
class EpisodeSelectionPlan:
    """Controleerbaar selectieplan voor één gespreksronde."""

    decision: EpisodeDecision
    should_store: bool

    summary: str = ""
    topic: str = "general"
    language: str = "unknown"
    keywords: list[str] = field(default_factory=list)
    importance: int = 1

    reasons: list[str] = field(default_factory=list)
    completed: bool = False


class EpisodeSelector:
    """Selecteert betekenisvolle gesprekservaringen."""

    MIN_USER_CHARACTERS = 8
    MIN_ASSISTANT_CHARACTERS = 8
    MAX_SUMMARY_CHARACTERS = 280
    MAX_KEYWORDS = 8

    TRIVIAL_MESSAGES = {
        "ok",
        "oke",
        "oké",
        "goed",
        "top",
        "prima",
        "ja",
        "nee",
        "hoi",
        "hallo",
        "hey",
        "thanks",
        "bedankt",
        "dank je",
        "dankjewel",
        "lets go",
        "let's go",
        "kom maar op",
        "ga verder",
        "doorgaan",
        "devam",
        "tamam",
        "evet",
        "hayır",
        "merhaba",
        "selam",
        "teşekkürler",
    }

    PREFERENCE_SIGNALS = (
        "ik wil dat",
        "ik wil voortaan",
        "ik heb liever",
        "mijn voorkeur",
        "antwoord altijd",
        "spreek altijd",
        "vanaf nu wil ik",
        "tercihim",
        "bundan sonra",
        "her zaman",
    )

    GOAL_SIGNALS = (
        "mijn doel",
        "ik wil bereiken",
        "ik wil bouwen",
        "ik wil ontwikkelen",
        "langetermijndoel",
        "uiteindelijk wil ik",
        "hedefim",
        "amacım",
        "geliştirmek istiyorum",
    )

    DECISION_SIGNALS = (
        "ik kies",
        "we kiezen",
        "besloten",
        "beslissing",
        "optie",
        "we gaan voor",
        "ik ga voor",
        "karar verdim",
        "seçiyorum",
    )

    MILESTONE_SIGNALS = (
        "test is geslaagd",
        "test geslaagd",
        "succesvol toegevoegd",
        "succesvol gekoppeld",
        "snapshot voltooid",
        "staat op github",
        "werkt nu",
        "klaar met",
        "mijlpaal",
        "başarıyla tamamlandı",
        "test başarılı",
    )

    PROJECT_SIGNALS = (
        "bilge",
        "runtime",
        "python",
        "module",
        "engine",
        "memory",
        "github",
        "ollama",
        "qwen",
        "docker",
        "vps",
        "roadmap",
        "project",
        "bestand",
        "code",
        "test",
    )

    PROBLEM_SOLUTION_SIGNALS = (
        "fout",
        "probleem",
        "bug",
        "opgelost",
        "oplossing",
        "hersteld",
        "werkt niet",
        "werkt weer",
        "error",
        "fixed",
        "çözüldü",
        "hata",
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
            r"\b(?:personal access token|github token)\b"
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
        re.compile(
            r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b",
            re.IGNORECASE,
        ),
    )

    WORD_PATTERN = re.compile(
        r"[A-Za-zÀ-ÖØ-öø-ÿĞğİıŞşÇç0-9_-]+"
    )

    STOPWORDS = {
        "de",
        "het",
        "een",
        "en",
        "of",
        "dat",
        "dit",
        "die",
        "ik",
        "je",
        "jij",
        "mijn",
        "met",
        "voor",
        "van",
        "naar",
        "op",
        "in",
        "is",
        "zijn",
        "was",
        "we",
        "nu",
        "dan",
        "maar",
        "ook",
        "nog",
        "çok",
        "bir",
        "ve",
        "bu",
        "şu",
        "ben",
        "sen",
        "için",
        "ile",
        "olan",
        "olarak",
    }

    @staticmethod
    def normalize_text(
        value: str,
        field_name: str,
    ) -> str:
        """Normaliseert tekst en controleert het datatype."""
        if not isinstance(value, str):
            raise InvalidEpisodeSelectorInputError(
                f"{field_name} moet tekst zijn."
            )

        return " ".join(value.strip().split())

    @staticmethod
    def validate_language(language: str) -> str:
        """Normaliseert de taalcode."""
        normalized = language.strip().casefold()

        if normalized not in {"nl", "tr", "unknown"}:
            return "unknown"

        return normalized

    def contains_sensitive_information(self, text: str) -> bool:
        """Controleert op herkenbare geheime gegevens."""
        return any(
            pattern.search(text)
            for pattern in self.SENSITIVE_PATTERNS
        )

    @staticmethod
    def contains_signal(
        text: str,
        signals: tuple[str, ...],
    ) -> bool:
        """Controleert alleen volledige woorden en woordgroepen."""
        lowered = text.casefold()

        for signal in signals:
            normalized_signal = signal.casefold().strip()

            signal_pattern = (
                r"(?<!\w)"
                + re.escape(normalized_signal)
                + r"(?!\w)"
            )

            if re.search(signal_pattern, lowered):
                return True

        return False

    def is_trivial_message(self, text: str) -> bool:
        """Herkent korte berichten zonder blijvende informatiewaarde."""
        normalized = text.strip(" .,!?:;").casefold()

        if normalized in self.TRIVIAL_MESSAGES:
            return True

        words = normalized.split()

        return (
            len(words) <= 2
            and len(normalized) < 12
        )

    def extract_keywords(
        self,
        user_message: str,
        assistant_message: str,
    ) -> list[str]:
        """Haalt eenvoudige bruikbare trefwoorden uit de gespreksronde."""
        combined = (
            user_message
            + " "
            + assistant_message
        )

        counts: dict[str, int] = {}

        for match in self.WORD_PATTERN.finditer(combined):
            word = match.group(0).casefold()

            if len(word) < 3:
                continue

            if word in self.STOPWORDS:
                continue

            counts[word] = counts.get(word, 0) + 1

        ranked = sorted(
            counts,
            key=lambda word: (
                counts[word],
                len(word),
                word,
            ),
            reverse=True,
        )

        return ranked[:self.MAX_KEYWORDS]

    def determine_topic(
        self,
        user_message: str,
        assistant_message: str,
    ) -> str:
        """Bepaalt een compact onderwerp."""
        combined = (
            user_message
            + " "
            + assistant_message
        ).casefold()

        topic_rules = (
            (
                "bilge memory",
                (
                    "episodic memory",
                    "long memory",
                    "short memory",
                    "geheugen",
                    "memory pipeline",
                ),
            ),
            (
                "bilge development",
                (
                    "bilge",
                    "runtime",
                    "module",
                    "engine",
                    "python",
                ),
            ),
            (
                "version control",
                (
                    "github",
                    "git",
                    "commit",
                    "snapshot",
                    "repository",
                ),
            ),
            (
                "infrastructure",
                (
                    "vps",
                    "docker",
                    "ollama",
                    "server",
                    "termius",
                ),
            ),
            (
                "planning",
                (
                    "planning",
                    "roadmap",
                    "stappenplan",
                    "doel",
                ),
            ),
        )

        for topic, signals in topic_rules:
            if any(
                signal in combined
                for signal in signals
            ):
                return topic

        return "general"

    def build_summary(
        self,
        user_message: str,
        assistant_message: str,
        topic: str,
    ) -> str:
        """Maakt zonder taalmodel een compacte feitelijke samenvatting."""
        user_text = user_message.rstrip(" .")
        assistant_text = assistant_message.rstrip(" .")

        if len(user_text) > 130:
            user_text = user_text[:127].rstrip() + "..."

        if len(assistant_text) > 110:
            assistant_text = (
                assistant_text[:107].rstrip()
                + "..."
            )

        summary = (
            f"Onderwerp: {topic}. "
            f"Zeki: {user_text}. "
            f"Bilge: {assistant_text}."
        )

        if len(summary) > self.MAX_SUMMARY_CHARACTERS:
            summary = (
                summary[
                    : self.MAX_SUMMARY_CHARACTERS - 3
                ].rstrip()
                + "..."
            )

        return summary

    def calculate_importance(
        self,
        combined_text: str,
    ) -> tuple[int, list[str]]:
        """Berekent belang en legt de redenen vast."""
        importance = 1
        reasons: list[str] = []

        if self.contains_signal(
            combined_text,
            self.PREFERENCE_SIGNALS,
        ):
            importance = max(importance, 5)
            reasons.append(
                "De gespreksronde bevat een blijvende voorkeur."
            )

        if self.contains_signal(
            combined_text,
            self.GOAL_SIGNALS,
        ):
            importance = max(importance, 5)
            reasons.append(
                "De gespreksronde bevat een belangrijk doel."
            )

        if self.contains_signal(
            combined_text,
            self.DECISION_SIGNALS,
        ):
            importance = max(importance, 4)
            reasons.append(
                "De gespreksronde bevat een beslissing."
            )

        if self.contains_signal(
            combined_text,
            self.MILESTONE_SIGNALS,
        ):
            importance = max(importance, 4)
            reasons.append(
                "De gespreksronde bevat een bereikte mijlpaal."
            )

        if self.contains_signal(
            combined_text,
            self.PROBLEM_SOLUTION_SIGNALS,
        ):
            importance = max(importance, 3)
            reasons.append(
                "De gespreksronde bevat een probleem of oplossing."
            )

        if self.contains_signal(
            combined_text,
            self.PROJECT_SIGNALS,
        ):
            importance = max(importance, 3)
            reasons.append(
                "De gespreksronde is relevant voor een lopend project."
            )

        return importance, reasons

    def select(
        self,
        user_message: str,
        assistant_message: str,
        *,
        language: str = "unknown",
    ) -> EpisodeSelectionPlan:
        """Selecteert of één afgeronde gespreksronde wordt bewaard."""
        safe_user_message = self.normalize_text(
            user_message,
            "Gebruikersbericht",
        )
        safe_assistant_message = self.normalize_text(
            assistant_message,
            "Assistentantwoord",
        )
        safe_language = self.validate_language(
            language
        )

        if not safe_user_message:
            raise InvalidEpisodeSelectorInputError(
                "Het gebruikersbericht is leeg."
            )

        if not safe_assistant_message:
            raise InvalidEpisodeSelectorInputError(
                "Het assistentantwoord is leeg."
            )

        combined = (
            safe_user_message
            + "\n"
            + safe_assistant_message
        )

        if self.contains_sensitive_information(combined):
            return EpisodeSelectionPlan(
                decision="reject_sensitive",
                should_store=False,
                language=safe_language,
                importance=1,
                reasons=[
                    "De gespreksronde bevat mogelijk geheime informatie."
                ],
                completed=True,
            )

        if (
            len(safe_user_message)
            < self.MIN_USER_CHARACTERS
            or len(safe_assistant_message)
            < self.MIN_ASSISTANT_CHARACTERS
        ):
            return EpisodeSelectionPlan(
                decision="skip",
                should_store=False,
                language=safe_language,
                importance=1,
                reasons=[
                    "De gespreksronde is te kort voor blijvende opslag."
                ],
                completed=True,
            )

        if self.is_trivial_message(safe_user_message):
            return EpisodeSelectionPlan(
                decision="skip",
                should_store=False,
                language=safe_language,
                importance=1,
                reasons=[
                    "Het gebruikersbericht is triviaal of puur sociaal."
                ],
                completed=True,
            )

        importance, reasons = self.calculate_importance(
            combined
        )

        if importance < 3:
            return EpisodeSelectionPlan(
                decision="skip",
                should_store=False,
                language=safe_language,
                importance=importance,
                reasons=(
                    reasons
                    or [
                        "De gespreksronde heeft onvoldoende "
                        "langdurige informatiewaarde."
                    ]
                ),
                completed=True,
            )

        topic = self.determine_topic(
            safe_user_message,
            safe_assistant_message,
        )

        keywords = self.extract_keywords(
            safe_user_message,
            safe_assistant_message,
        )

        summary = self.build_summary(
            safe_user_message,
            safe_assistant_message,
            topic,
        )

        return EpisodeSelectionPlan(
            decision="store",
            should_store=True,
            summary=summary,
            topic=topic,
            language=safe_language,
            keywords=keywords,
            importance=importance,
            reasons=reasons,
            completed=True,
        )


def print_plan(
    user_message: str,
    plan: EpisodeSelectionPlan,
) -> None:
    """Toont het selectieplan overzichtelijk."""
    print()
    print(f"Bericht     : {user_message}")
    print(f"Beslissing : {plan.decision}")
    print(f"Opslaan     : {plan.should_store}")
    print(f"Onderwerp   : {plan.topic}")
    print(f"Taal        : {plan.language}")
    print(f"Belang      : {plan.importance}")
    print(
        "Trefwoorden : "
        + (
            ", ".join(plan.keywords)
            if plan.keywords
            else "geen"
        )
    )

    if plan.summary:
        print(f"Samenvatting: {plan.summary}")

    for reason in plan.reasons:
        print(f"Reden       : {reason}")


def self_test() -> int:
    """Test de belangrijkste selectieregels."""
    print("===== Episode Selector-test =====")

    selector = EpisodeSelector()

    tests = [
        {
            "user": "Ok",
            "assistant": "Prima, dan gaan we verder.",
            "language": "nl",
            "expected_decision": "skip",
            "expected_store": False,
        },
        {
            "user": (
                "Ik wil voortaan complete bestanden ontvangen "
                "in plaats van losse regels."
            ),
            "assistant": (
                "Ik houd die werkwijze aan tijdens de verdere "
                "ontwikkeling van Bilge."
            ),
            "language": "nl",
            "expected_decision": "store",
            "expected_store": True,
        },
        {
            "user": (
                "De Episodic Memory-test is geslaagd en staat "
                "nu veilig op GitHub."
            ),
            "assistant": (
                "De nieuwe geheugenmodule en snapshot zijn "
                "succesvol voltooid."
            ),
            "language": "nl",
            "expected_decision": "store",
            "expected_store": True,
        },
        {
            "user": (
                "Onthoud mijn GitHub-token: "
                "ghp_abcdefghijklmnopqrstuvwxyz123456"
            ),
            "assistant": "Ik zal deze token onthouden.",
            "language": "nl",
            "expected_decision": "reject_sensitive",
            "expected_store": False,
        },
        {
            "user": "Bugün kahve içtim.",
            "assistant": "Afiyet olsun.",
            "language": "tr",
            "expected_decision": "skip",
            "expected_store": False,
        },
        {
            "user": (
                "Bilge için episodik hafıza modülünü "
                "geliştirmek istiyorum."
            ),
            "assistant": (
                "Bu hedef için önce güvenli bir seçim katmanı "
                "oluşturuyoruz."
            ),
            "language": "tr",
            "expected_decision": "store",
            "expected_store": True,
        },
    ]

    for test in tests:
        plan = selector.select(
            test["user"],
            test["assistant"],
            language=test["language"],
        )

        print_plan(
            test["user"],
            plan,
        )

        if plan.decision != test["expected_decision"]:
            print()
            print(
                "FOUT: verkeerde beslissing. "
                f"Verwacht {test['expected_decision']}, "
                f"kreeg {plan.decision}."
            )
            return 1

        if plan.should_store != test["expected_store"]:
            print()
            print(
                "FOUT: verkeerde opslagkeuze. "
                f"Verwacht {test['expected_store']}, "
                f"kreeg {plan.should_store}."
            )
            return 1

        if not plan.completed:
            print()
            print(
                "FOUT: selectieplan is niet voltooid."
            )
            return 1

    print()
    print("Episode Selector-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
