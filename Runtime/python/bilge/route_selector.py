"""
Routekeuze voor Bilge.

Bepaalt of een bericht via de snelle of uitgebreide route moet lopen.
Deze module roept geen model aan en verandert geen geheugen.
"""

from __future__ import annotations

from dataclasses import dataclass


FAST_ROUTE = "fast"
FULL_ROUTE = "full"


@dataclass(slots=True)
class RouteDecision:
    """Resultaat van de routekeuze."""

    route: str
    reason: str
    confidence: float

    @property
    def use_fast_route(self) -> bool:
        return self.route == FAST_ROUTE

    @property
    def use_full_route(self) -> bool:
        return self.route == FULL_ROUTE


class RouteSelector:
    """Kiest een snelle of uitgebreide antwoordroute."""

    FULL_ROUTE_SIGNALS = (
        "planning",
        "weekplanning",
        "dagplanning",
        "stappenplan",
        "leg uitgebreid uit",
        "analyseer",
        "vergelijk",
        "onderzoek",
        "rapport",
        "strategie",
        "businessplan",
        "ondernemingsplan",
        "begroting",
        "voor- en nadelen",
        "help me kiezen",
        "wat zou jij doen",
        "bouw een",
        "maak een website",
        "contract",
        "juridisch",
        "medisch",
        "financieel",
        "veiligheid",
        "wachtwoord",
        "token",
        "privésleutel",
        "api key",
        "stap voor stap",
        "van a tot z",
        "detaylı açıkla",
        "adım adım",
        "analiz et",
        "karşılaştır",
        "plan yap",
        "iş planı",
    )

    FAST_ROUTE_SIGNALS = (
        "hoi",
        "hallo",
        "hey",
        "goedemorgen",
        "goedemiddag",
        "goedenavond",
        "hoe gaat het",
        "hoe was je dag",
        "dank je",
        "bedankt",
        "top",
        "ok",
        "prima",
        "ja",
        "nee",
        "merhaba",
        "selam",
        "nasılsın",
        "teşekkür",
        "tamam",
        "evet",
        "hayır",
    )

    QUESTION_WORDS = (
        "wie",
        "wat",
        "waar",
        "wanneer",
        "waarom",
        "hoe",
        "welke",
        "kaç",
        "kim",
        "ne",
        "nerede",
        "neden",
        "nasıl",
        "hangi",
    )

    @staticmethod
    def normalize(message: str) -> str:
        """Normaliseert een gebruikersbericht."""
        return " ".join(message.casefold().strip().split())

    @classmethod
    def select(cls, message: str) -> RouteDecision:
        """Kiest de meest passende route."""
        normalized = cls.normalize(message)

        if not normalized:
            return RouteDecision(
                route=FAST_ROUTE,
                reason="Leeg of betekenisloos bericht.",
                confidence=1.0,
            )

        for signal in cls.FULL_ROUTE_SIGNALS:
            if signal in normalized:
                return RouteDecision(
                    route=FULL_ROUTE,
                    reason=f"Complexiteitssignaal gevonden: {signal}",
                    confidence=0.95,
                )

        word_count = len(normalized.split())
        character_count = len(normalized)

        if character_count > 280 or word_count > 45:
            return RouteDecision(
                route=FULL_ROUTE,
                reason="Het bericht is lang en waarschijnlijk complex.",
                confidence=0.90,
            )

        if normalized.count("?") >= 2:
            return RouteDecision(
                route=FULL_ROUTE,
                reason="Het bericht bevat meerdere vragen.",
                confidence=0.85,
            )

        for signal in cls.FAST_ROUTE_SIGNALS:
            if (
                normalized == signal
                or normalized.startswith(signal + " ")
            ):
                return RouteDecision(
                    route=FAST_ROUTE,
                    reason=f"Normaal gesprekssignaal gevonden: {signal}",
                    confidence=0.95,
                )

        first_word = normalized.split(maxsplit=1)[0]

        if (
            first_word in cls.QUESTION_WORDS
            and word_count <= 18
            and character_count <= 120
        ):
            return RouteDecision(
                route=FAST_ROUTE,
                reason="Korte enkelvoudige vraag.",
                confidence=0.82,
            )

        if word_count <= 12 and character_count <= 90:
            return RouteDecision(
                route=FAST_ROUTE,
                reason="Kort normaal gesprek.",
                confidence=0.78,
            )

        return RouteDecision(
            route=FULL_ROUTE,
            reason="Geen veilig snel-routepatroon gevonden.",
            confidence=0.70,
        )


def self_test() -> int:
    """Controleert de belangrijkste routes."""
    tests = (
        ("Hallo Bilge", FAST_ROUTE),
        ("Hoe gaat het met je?", FAST_ROUTE),
        ("Wat is mijn voorkeur voor code?", FAST_ROUTE),
        (
            "Maak een uitgebreide weekplanning voor mij.",
            FULL_ROUTE,
        ),
        (
            "Vergelijk deze twee zakelijke strategieën.",
            FULL_ROUTE,
        ),
        ("Adım adım bir iş planı yap.", FULL_ROUTE),
    )

    for message, expected in tests:
        result = RouteSelector.select(message)

        print(
            f"{message!r:<48} -> "
            f"{result.route:<4} | {result.reason}"
        )

        if result.route != expected:
            print(
                f"FOUT: verwacht {expected}, "
                f"maar kreeg {result.route}."
            )
            return 1

    print()
    print("Route Selector-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
