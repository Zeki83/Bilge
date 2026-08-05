#!/usr/bin/env python3
"""
Bilge OS - Answer Cleaner

Schoont modelantwoorden voorzichtig op voordat ze aan Zeki
worden getoond.

Deze module:
- verwijdert zichtbare taalmetadata zoals 'nl.' en 'tr.';
- verwijdert stijve modelinleidingen;
- normaliseert witruimte;
- beperkt letterlijke herhaling van het gebruikersbericht;
- verwijdert enkele overbodige standaardafsluitingen;
- verandert geen feiten;
- genereert zelf geen nieuwe inhoud.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


class AnswerCleanerError(Exception):
    """Basisfout voor problemen binnen de Answer Cleaner."""


class InvalidAnswerInputError(AnswerCleanerError):
    """Het antwoord of gebruikersbericht is ongeldig."""


@dataclass(slots=True)
class CleanAnswerResult:
    """Resultaat van één opschoonactie."""

    original: str
    cleaned: str
    removed_prefixes: int = 0
    removed_repetitions: int = 0
    removed_closings: int = 0
    completed: bool = False

    @property
    def changed(self) -> bool:
        """Geeft aan of het antwoord is aangepast."""
        return self.original.strip() != self.cleaned.strip()


class AnswerCleaner:
    """Schoont modelantwoorden voorzichtig en voorspelbaar op."""

    LANGUAGE_PREFIX_PATTERNS = (
        re.compile(
            r"^\s*(?:nl|nederlands|dutch)\s*[\.:;-]\s*",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*(?:tr|turks|türkçe|turkish)\s*[\.:;-]\s*",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*(?:taal|language)\s*:\s*"
            r"(?:nl|nederlands|dutch|tr|turks|türkçe|turkish)"
            r"\s*[\.:;-]?\s*",
            re.IGNORECASE,
        ),
    )

    INTRO_PATTERNS = (
        re.compile(
            r"^\s*(?:tuurlijk|natuurlijk|zeker)[,!.\s]*"
            r"(?:hier is|hier volgt)\s+"
            r"(?:het\s+)?(?:definitieve\s+)?antwoord"
            r"(?:\s+op\s+(?:je|jouw)\s+verzoek)?\s*:\s*",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*hier\s+(?:is|volgt)\s+"
            r"(?:het\s+)?(?:definitieve\s+)?antwoord\s*:\s*",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*(?:definitief\s+antwoord|antwoord)\s*:\s*",
            re.IGNORECASE,
        ),
    )

    CLOSING_PATTERNS = (
        re.compile(
            r"\n+\s*als je nog (?:verdere )?"
            r"(?:specificaties|vragen|aanpassingen|wijzigingen)"
            r".*?(?:laat het mij weten|hoor ik het graag)[!.]?\s*$",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r"\n+\s*laat het mij weten als je nog "
            r"(?:vragen|wensen|aanpassingen) hebt[!.]?\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            r"\n+\s*ik help je graag verder[!.]?\s*$",
            re.IGNORECASE,
        ),
    )

    @staticmethod
    def normalize_text(value: str) -> str:
        """Normaliseert regeleinden en overmatige witruimte."""
        text = value.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def validate_input(
        answer: str,
        user_message: str,
    ) -> None:
        """Controleert of de invoer bruikbaar is."""
        if not isinstance(answer, str):
            raise InvalidAnswerInputError(
                "Het modelantwoord moet tekst zijn."
            )

        if not answer.strip():
            raise InvalidAnswerInputError(
                "Het modelantwoord is leeg."
            )

        if not isinstance(user_message, str):
            raise InvalidAnswerInputError(
                "Het gebruikersbericht moet tekst zijn."
            )

    @classmethod
    def remove_prefixes(
        cls,
        text: str,
    ) -> tuple[str, int]:
        """Verwijdert taalmetadata en stijve inleidingen."""
        removed = 0
        current = text

        changed = True

        while changed:
            changed = False

            for pattern in (
                *cls.LANGUAGE_PREFIX_PATTERNS,
                *cls.INTRO_PATTERNS,
            ):
                updated, count = pattern.subn(
                    "",
                    current,
                    count=1,
                )

                if count:
                    current = updated.lstrip()
                    removed += count
                    changed = True
                    break

        return current, removed

    @staticmethod
    def normalized_comparison(value: str) -> str:
        """Maakt tekst geschikt voor voorzichtige vergelijking."""
        value = value.casefold()
        value = re.sub(r"[^\w\s]", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    @classmethod
    def remove_exact_user_repetition(
        cls,
        text: str,
        user_message: str,
    ) -> tuple[str, int]:
        """
        Verwijdert alleen een duidelijke, vrijwel letterlijke herhaling
        van het gebruikersbericht als losse alinea.
        """
        normalized_user = cls.normalized_comparison(
            user_message
        )

        if len(normalized_user) < 12:
            return text, 0

        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(
                r"\n\s*\n",
                text,
            )
            if paragraph.strip()
        ]

        kept: list[str] = []
        removed = 0

        for paragraph in paragraphs:
            normalized_paragraph = cls.normalized_comparison(
                paragraph
            )

            is_exact = (
                normalized_paragraph == normalized_user
            )

            starts_as_quote = (
                normalized_paragraph.startswith(
                    "onthoud dat "
                )
                and normalized_paragraph.endswith(
                    normalized_user
                )
            )

            if is_exact or starts_as_quote:
                removed += 1
                continue

            kept.append(paragraph)

        if not kept:
            return text, 0

        return "\n\n".join(kept), removed

    @classmethod
    def remove_redundant_closings(
        cls,
        text: str,
    ) -> tuple[str, int]:
        """Verwijdert enkele overbodige standaardafsluitingen."""
        current = text
        removed = 0

        for pattern in cls.CLOSING_PATTERNS:
            current, count = pattern.subn(
                "",
                current,
                count=1,
            )
            removed += count

        return current.rstrip(), removed

    @staticmethod
    def remove_duplicate_headings(
        text: str,
    ) -> str:
        """Verwijdert enkele stijve tussenkoppen zonder inhoud."""
        patterns = (
            r"(?im)^\s*definitief antwoord\s*:\s*$\n?",
            r"(?im)^\s*samenvatting\s*:\s*$\n?",
            r"(?im)^\s*complete tekst\s*:\s*$\n?",
        )

        current = text

        for pattern in patterns:
            current = re.sub(
                pattern,
                "",
                current,
            )

        return current

    def clean(
        self,
        answer: str,
        *,
        user_message: str = "",
    ) -> CleanAnswerResult:
        """Schoont één modelantwoord op."""
        self.validate_input(
            answer,
            user_message,
        )

        current = self.normalize_text(answer)

        current, removed_prefixes = self.remove_prefixes(
            current
        )

        current = self.remove_duplicate_headings(
            current
        )

        current, removed_repetitions = (
            self.remove_exact_user_repetition(
                current,
                user_message,
            )
        )

        current, removed_closings = (
            self.remove_redundant_closings(
                current
            )
        )

        current = self.normalize_text(current)

        if not current:
            current = self.normalize_text(answer)

        return CleanAnswerResult(
            original=answer,
            cleaned=current,
            removed_prefixes=removed_prefixes,
            removed_repetitions=removed_repetitions,
            removed_closings=removed_closings,
            completed=True,
        )


def self_test() -> int:
    """Test de belangrijkste opschoonregels."""
    print("===== Answer Cleaner-test =====")

    cleaner = AnswerCleaner()

    tests = [
        {
            "answer": (
                "nl. Hallo Zeki, ik ga prima. "
                "Hoe gaat het met jou?"
            ),
            "user_message": (
                "Hoi Bilge, hoe gaat het met je?"
            ),
            "expected": (
                "Hallo Zeki, ik ga prima. "
                "Hoe gaat het met jou?"
            ),
        },
        {
            "answer": (
                "Tuurlijk, hier is het definitieve antwoord "
                "op jouw verzoek:\n\n"
                "Onthoud dat ik complete bestanden wil "
                "in plaats van losse regels.\n\n"
                "Ik zal voortaan complete bestanden geven.\n\n"
                "Als je nog verdere specificaties wilt toevoegen, "
                "laat het mij weten!"
            ),
            "user_message": (
                "Onthoud dat ik complete bestanden wil "
                "in plaats van losse regels."
            ),
            "expected": (
                "Ik zal voortaan complete bestanden geven."
            ),
        },
        {
            "answer": (
                "tr. Bunu güvenli biçimde hatırladım."
            ),
            "user_message": "Bunu hatırla: kısa cevap ver.",
            "expected": (
                "Bunu güvenli biçimde hatırladım."
            ),
        },
    ]

    for index, test in enumerate(
        tests,
        start=1,
    ):
        result = cleaner.clean(
            test["answer"],
            user_message=test["user_message"],
        )

        print()
        print(f"Test {index}")
        print(f"Origineel : {test['answer']}")
        print(f"Opgeschoond: {result.cleaned}")
        print(f"Gewijzigd : {result.changed}")

        if result.cleaned != test["expected"]:
            print()
            print(
                f"FOUT: verwacht '{test['expected']}', "
                f"maar kreeg '{result.cleaned}'."
            )
            return 1

        if not result.completed:
            print("FOUT: opschoonactie is niet voltooid.")
            return 1

    print()
    print("Answer Cleaner-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
