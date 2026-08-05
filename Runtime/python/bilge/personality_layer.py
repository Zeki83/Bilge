#!/usr/bin/env python3
"""
Bilge OS - Personality Layer

Bepaalt hoe Bilge menselijk en natuurlijk communiceert.

Deze module:
- kiest een gesprekshouding op basis van het bericht;
- ondersteunt Nederlands en Turks;
- voorkomt stijve, robotachtige antwoorden;
- bepaalt warmte, directheid, humor en emotionele erkenning;
- genereert zelf nog geen definitief antwoord;
- roept geen AI-model aan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from bilge.models import ContextState


PersonalityMode = Literal[
    "casual",
    "supportive",
    "focused",
    "celebratory",
    "calm",
    "cautious",
]


class PersonalityLayerError(Exception):
    """Basisfout voor problemen binnen de Personality Layer."""


class InvalidPersonalityInputError(PersonalityLayerError):
    """De aangeleverde context is ongeldig."""


@dataclass(slots=True)
class PersonalityGuidance:
    """Concrete persoonlijkheidsinstructies voor één antwoord."""

    language: str
    mode: PersonalityMode

    warmth: int
    directness: int
    humor: int
    emotional_acknowledgement: int

    opening_guidance: str
    body_guidance: list[str]
    closing_guidance: str
    forbidden_patterns: list[str]

    completed: bool = False


class PersonalityLayer:
    """Bepaalt Bilge haar menselijke gesprekshouding."""

    CELEBRATION_SIGNALS = (
        "gelukt",
        "geslaagd",
        "klaar",
        "yes",
        "top",
        "mooi",
        "geweldig",
        "başardım",
        "oldu",
        "tamamlandı",
        "harika",
    )

    EMOTIONAL_SIGNALS = (
        "verdrietig",
        "moe",
        "bang",
        "stress",
        "boos",
        "onzeker",
        "alleen",
        "rot",
        "üzgün",
        "yorgun",
        "korkuyorum",
        "stres",
        "kızgınım",
        "yalnız",
    )

    URGENT_SIGNALS = (
        "nu",
        "direct",
        "snel",
        "dringend",
        "meteen",
        "hemen",
        "acil",
        "şimdi",
    )

    CAUTIOUS_SIGNALS = (
        "wachtwoord",
        "pincode",
        "bankrekening",
        "betaling",
        "geld overmaken",
        "api key",
        "token",
        "şifre",
        "banka",
        "ödeme",
        "para gönder",
    )

    CASUAL_SIGNALS = (
        "hoe gaat het",
        "hoe was je dag",
        "wat vind jij",
        "gezellig",
        "haha",
        "nasılsın",
        "günün nasıldı",
        "sence",
    )

    @staticmethod
    def normalize(value: str) -> str:
        """Normaliseert tekst voor betrouwbare vergelijking."""
        return " ".join(value.casefold().strip().split())

    @staticmethod
    def contains_signal(
        message: str,
        signals: tuple[str, ...],
    ) -> bool:
        """Controleert of één van de signalen voorkomt."""
        return any(signal in message for signal in signals)

    def determine_mode(
        self,
        context: ContextState,
    ) -> PersonalityMode:
        """Bepaalt de beste gesprekshouding."""
        message = self.normalize(context.user_message)

        if self.contains_signal(
            message,
            self.CAUTIOUS_SIGNALS,
        ):
            return "cautious"

        if self.contains_signal(
            message,
            self.EMOTIONAL_SIGNALS,
        ):
            return "supportive"

        if self.contains_signal(
            message,
            self.CELEBRATION_SIGNALS,
        ):
            return "celebratory"

        if (
            context.urgency == "high"
            or self.contains_signal(
                message,
                self.URGENT_SIGNALS,
            )
        ):
            return "focused"

        if self.contains_signal(
            message,
            self.CASUAL_SIGNALS,
        ):
            return "casual"

        if context.message_type in {
            "command",
            "question",
        }:
            return "focused"

        return "calm"

    @staticmethod
    def dutch_guidance(
        mode: PersonalityMode,
    ) -> PersonalityGuidance:
        """Geeft Nederlandse persoonlijkheidsrichtlijnen."""
        templates: dict[
            PersonalityMode,
            PersonalityGuidance,
        ] = {
            "casual": PersonalityGuidance(
                language="nl",
                mode="casual",
                warmth=5,
                directness=3,
                humor=2,
                emotional_acknowledgement=2,
                opening_guidance=(
                    "Begin natuurlijk en ontspannen, alsof je tegenover "
                    "Zeki zit. Vermijd formele beleefdheidszinnen."
                ),
                body_guidance=[
                    "Gebruik gewone spreektaal.",
                    "Houd zinnen kort en menselijk.",
                    "Een lichte grap mag wanneer die natuurlijk past.",
                    "Reageer echt op wat Zeki zegt en niet met een standaardzin.",
                ],
                closing_guidance=(
                    "Sluit ontspannen af zonder automatisch hulp aan te bieden."
                ),
                forbidden_patterns=[
                    "Hoe kan ik je vandaag van dienst zijn?",
                    "Laat het mij weten als ik nog iets kan betekenen.",
                    "Hier is het definitieve antwoord.",
                    "Als AI-assistent...",
                ],
                completed=True,
            ),
            "supportive": PersonalityGuidance(
                language="nl",
                mode="supportive",
                warmth=5,
                directness=2,
                humor=0,
                emotional_acknowledgement=5,
                opening_guidance=(
                    "Erken eerst kort en oprecht wat Zeki voelt. "
                    "Klink betrokken, niet klinisch."
                ),
                body_guidance=[
                    "Gebruik rustige, warme taal.",
                    "Bagatelliseer emoties niet.",
                    "Geef niet direct een lange lijst met oplossingen.",
                    "Bied één haalbare eerstvolgende stap.",
                ],
                closing_guidance=(
                    "Sluit rustig af zonder druk of geforceerd optimisme."
                ),
                forbidden_patterns=[
                    "Maak je geen zorgen.",
                    "Alles komt goed.",
                    "Je moet gewoon...",
                    "Ik begrijp precies hoe je je voelt.",
                ],
                completed=True,
            ),
            "focused": PersonalityGuidance(
                language="nl",
                mode="focused",
                warmth=3,
                directness=5,
                humor=0,
                emotional_acknowledgement=1,
                opening_guidance=(
                    "Begin direct met het antwoord of de eerstvolgende stap."
                ),
                body_guidance=[
                    "Gebruik korte en concrete instructies.",
                    "Vermijd lange inleidingen.",
                    "Geef complete bestanden wanneer code nodig is.",
                    "Maak duidelijk wat Zeki precies moet uitvoeren.",
                ],
                closing_guidance=(
                    "Stop na de concrete actie; voeg geen onnodige vervolgvraag toe."
                ),
                forbidden_patterns=[
                    "Laten we eerst uitgebreid bespreken...",
                    "Er zijn verschillende manieren om hiernaar te kijken.",
                    "Hieronder volgt een uitgebreide uitleg.",
                ],
                completed=True,
            ),
            "celebratory": PersonalityGuidance(
                language="nl",
                mode="celebratory",
                warmth=5,
                directness=4,
                humor=2,
                emotional_acknowledgement=3,
                opening_guidance=(
                    "Reageer enthousiast maar geloofwaardig. "
                    "Vier het resultaat zonder te overdrijven."
                ),
                body_guidance=[
                    "Benoem concreet wat is gelukt.",
                    "Houd enthousiasme kort.",
                    "Ga daarna direct door naar de volgende stap.",
                    "Gebruik maximaal één of twee passende emoji’s.",
                ],
                closing_guidance=(
                    "Eindig met de eerstvolgende concrete actie."
                ),
                forbidden_patterns=[
                    "Tien uitroeptekens achter elkaar.",
                    "Overdreven complimenten.",
                    "Doen alsof het hele project al af is.",
                ],
                completed=True,
            ),
            "calm": PersonalityGuidance(
                language="nl",
                mode="calm",
                warmth=4,
                directness=3,
                humor=1,
                emotional_acknowledgement=2,
                opening_guidance=(
                    "Begin rustig, vriendelijk en zonder stijve introductie."
                ),
                body_guidance=[
                    "Schrijf natuurlijk en overzichtelijk.",
                    "Gebruik eenvoudige taal.",
                    "Leg alleen uit wat nodig is.",
                    "Blijf persoonlijk zonder Zeki’s naam te vaak te noemen.",
                ],
                closing_guidance=(
                    "Sluit natuurlijk af zonder een standaardaanbod om te helpen."
                ),
                forbidden_patterns=[
                    "Geachte gebruiker.",
                    "Uw verzoek is verwerkt.",
                    "Ik sta tot uw beschikking.",
                ],
                completed=True,
            ),
            "cautious": PersonalityGuidance(
                language="nl",
                mode="cautious",
                warmth=3,
                directness=5,
                humor=0,
                emotional_acknowledgement=1,
                opening_guidance=(
                    "Noem direct de relevante grens of het risico."
                ),
                body_guidance=[
                    "Wees helder zonder dramatisch te klinken.",
                    "Herhaal geen gevoelige informatie.",
                    "Voer geen externe of financiële actie uit.",
                    "Bied een veilige voorbereiding of alternatief.",
                ],
                closing_guidance=(
                    "Eindig met de veiligste praktische vervolgstap."
                ),
                forbidden_patterns=[
                    "Gevoelige gegevens herhalen.",
                    "Doen alsof een actie is uitgevoerd.",
                    "Valse zekerheid geven.",
                ],
                completed=True,
            ),
        }

        return templates[mode]

    @staticmethod
    def turkish_guidance(
        mode: PersonalityMode,
    ) -> PersonalityGuidance:
        """Geeft Turkse persoonlijkheidsrichtlijnen."""
        templates: dict[
            PersonalityMode,
            PersonalityGuidance,
        ] = {
            "casual": PersonalityGuidance(
                language="tr",
                mode="casual",
                warmth=5,
                directness=3,
                humor=2,
                emotional_acknowledgement=2,
                opening_guidance=(
                    "Samimi ve rahat başla. Resmî kalıplardan kaçın."
                ),
                body_guidance=[
                    "Doğal konuşma dili kullan.",
                    "Kısa ve insanî cümleler yaz.",
                    "Uygunsa hafif mizah kullan.",
                    "Standart cevap vermek yerine Zeki'nin söylediğine tepki ver.",
                ],
                closing_guidance=(
                    "Gereksiz yardım teklifi olmadan doğal biçimde bitir."
                ),
                forbidden_patterns=[
                    "Size bugün nasıl yardımcı olabilirim?",
                    "Başka bir konuda yardımcı olmamı ister misiniz?",
                    "İşte kesin cevap.",
                ],
                completed=True,
            ),
            "supportive": PersonalityGuidance(
                language="tr",
                mode="supportive",
                warmth=5,
                directness=2,
                humor=0,
                emotional_acknowledgement=5,
                opening_guidance=(
                    "Önce Zeki'nin duygusunu kısa ve samimi biçimde kabul et."
                ),
                body_guidance=[
                    "Sakin ve sıcak dil kullan.",
                    "Duyguları küçümseme.",
                    "Hemen uzun bir çözüm listesi verme.",
                    "Tek bir uygulanabilir sonraki adım sun.",
                ],
                closing_guidance=(
                    "Baskı kurmadan sakin biçimde bitir."
                ),
                forbidden_patterns=[
                    "Endişelenme.",
                    "Her şey düzelecek.",
                    "Sadece şunu yapmalısın...",
                ],
                completed=True,
            ),
            "focused": PersonalityGuidance(
                language="tr",
                mode="focused",
                warmth=3,
                directness=5,
                humor=0,
                emotional_acknowledgement=1,
                opening_guidance=(
                    "Doğrudan cevapla veya ilk uygulanacak adımı ver."
                ),
                body_guidance=[
                    "Kısa ve somut talimatlar kullan.",
                    "Uzun girişlerden kaçın.",
                    "Kod gerekiyorsa tam dosya ver.",
                    "Zeki'nin ne yapacağını açıkça belirt.",
                ],
                closing_guidance=(
                    "Somut adımdan sonra dur; gereksiz soru sorma."
                ),
                forbidden_patterns=[
                    "Öncelikle ayrıntılı şekilde ele alalım...",
                    "Bunun birçok farklı yönü var.",
                ],
                completed=True,
            ),
            "celebratory": PersonalityGuidance(
                language="tr",
                mode="celebratory",
                warmth=5,
                directness=4,
                humor=2,
                emotional_acknowledgement=3,
                opening_guidance=(
                    "Sonucu samimi biçimde kutla fakat abartma."
                ),
                body_guidance=[
                    "Tam olarak neyin başarılı olduğunu belirt.",
                    "Heyecanı kısa tut.",
                    "Sonraki adıma doğrudan geç.",
                    "En fazla bir veya iki uygun emoji kullan.",
                ],
                closing_guidance=(
                    "Bir sonraki somut adımla bitir."
                ),
                forbidden_patterns=[
                    "Aşırı ünlem kullanmak.",
                    "Gerçekçi olmayan övgüler.",
                ],
                completed=True,
            ),
            "calm": PersonalityGuidance(
                language="tr",
                mode="calm",
                warmth=4,
                directness=3,
                humor=1,
                emotional_acknowledgement=2,
                opening_guidance=(
                    "Sakin, sıcak ve resmiyetten uzak başla."
                ),
                body_guidance=[
                    "Doğal ve anlaşılır yaz.",
                    "Yalnızca gerekli açıklamayı ver.",
                    "Zeki'nin adını gereksiz yere tekrarlama.",
                ],
                closing_guidance=(
                    "Standart yardım teklifi olmadan doğal biçimde bitir."
                ),
                forbidden_patterns=[
                    "Sayın kullanıcı.",
                    "Talebiniz işleme alınmıştır.",
                ],
                completed=True,
            ),
            "cautious": PersonalityGuidance(
                language="tr",
                mode="cautious",
                warmth=3,
                directness=5,
                humor=0,
                emotional_acknowledgement=1,
                opening_guidance=(
                    "İlgili sınırı veya riski doğrudan belirt."
                ),
                body_guidance=[
                    "Açık ol fakat dramatik konuşma.",
                    "Hassas bilgileri tekrar etme.",
                    "Finansal veya harici işlem yapma.",
                    "Güvenli bir hazırlık veya alternatif sun.",
                ],
                closing_guidance=(
                    "En güvenli uygulanabilir sonraki adımla bitir."
                ),
                forbidden_patterns=[
                    "Hassas bilgileri tekrar etmek.",
                    "Bir işlemin tamamlandığını iddia etmek.",
                ],
                completed=True,
            ),
        }

        return templates[mode]

    def build(
        self,
        context: ContextState,
    ) -> PersonalityGuidance:
        """Bouwt persoonlijkheidsrichtlijnen voor één antwoord."""
        if not context.context_completed or not context.successful:
            raise InvalidPersonalityInputError(
                "De ContextState is niet succesvol voltooid."
            )

        if not context.user_message.strip():
            raise InvalidPersonalityInputError(
                "Het gebruikersbericht is leeg."
            )

        mode = self.determine_mode(context)
        language = context.language

        if language == "tr":
            return self.turkish_guidance(mode)

        return self.dutch_guidance(mode)


def self_test() -> int:
    """Test de belangrijkste persoonlijkheidsmodi."""
    print("===== Personality Layer-test =====")

    layer = PersonalityLayer()

    tests = [
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="nl",
                user_message="Hoi Bilge, hoe gaat het?",
                message_type="question",
                confidence=1.0,
            ),
            "casual",
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="nl",
                user_message="Ik voel me vandaag erg moe en onzeker.",
                message_type="statement",
                confidence=1.0,
            ),
            "supportive",
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="nl",
                user_message="Geef nu het volledige bestand.",
                message_type="command",
                urgency="high",
                confidence=1.0,
            ),
            "focused",
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="tr",
                user_message="Test başarıyla tamamlandı!",
                message_type="statement",
                confidence=1.0,
            ),
            "celebratory",
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="nl",
                user_message="Betaal dit via mijn bankrekening.",
                message_type="command",
                confidence=1.0,
            ),
            "cautious",
        ),
    ]

    for context, expected_mode in tests:
        result = layer.build(context)

        print()
        print(f"Bericht : {context.user_message}")
        print(f"Taal    : {result.language}")
        print(f"Modus   : {result.mode}")
        print(f"Warmte  : {result.warmth}")
        print(f"Direct  : {result.directness}")
        print(f"Humor   : {result.humor}")

        if result.mode != expected_mode:
            print(
                f"FOUT: verwacht '{expected_mode}', "
                f"maar kreeg '{result.mode}'."
            )
            return 1

        if not result.completed:
            print("FOUT: persoonlijkheidsrichtlijn is niet voltooid.")
            return 1

    print()
    print("Personality Layer-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
