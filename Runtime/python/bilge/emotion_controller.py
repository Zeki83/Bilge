#!/usr/bin/env python3
"""
Bilge OS - Emotion & Tone Controller

Bepaalt de emotionele toon en intensiteit van één antwoord.

Deze module:
- analyseert de actuele ContextState;
- kiest een passende gesprekssituatie;
- bepaalt warmte, empathie, enthousiasme en directheid;
- beperkt humor en emoji's;
- bewaakt dat Nederlands en Turks niet onnodig worden gemengd;
- genereert zelf geen definitief antwoord;
- roept geen AI-model aan;
- voert geen externe acties uit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from bilge.models import ContextState
from bilge.personality_layer import PersonalityGuidance


EmotionMode = Literal[
    "neutral",
    "casual",
    "positive",
    "celebration",
    "supportive",
    "serious",
    "technical",
    "urgent",
    "cautious",
]

AnswerPace = Literal[
    "slow",
    "normal",
    "direct",
]

AnswerDetail = Literal[
    "very_short",
    "short",
    "normal",
    "detailed",
]


class EmotionControllerError(Exception):
    """Basisfout voor problemen binnen de Emotion Controller."""


class InvalidEmotionInputError(EmotionControllerError):
    """De aangeleverde context of persoonlijkheid is ongeldig."""


@dataclass(slots=True)
class EmotionGuidance:
    """Concrete toonregeling voor één antwoord."""

    language: str
    mode: EmotionMode

    warmth: int
    directness: int
    empathy: int
    enthusiasm: int
    humor: int

    emoji_allowed: bool
    max_emojis: int

    answer_pace: AnswerPace
    answer_detail: AnswerDetail

    language_lock: bool = True
    allow_english_terms: bool = False

    tone_instruction: str = ""
    response_rules: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)

    completed: bool = False


class EmotionController:
    """Bepaalt de juiste emotionele intensiteit van Bilge."""

    STRONG_NEGATIVE_SIGNALS = (
        "overleden",
        "dood",
        "rouw",
        "paniek",
        "depressief",
        "ik trek het niet",
        "ik kan niet meer",
        "heel verdrietig",
        "ernstig ziek",
        "öldü",
        "vefat",
        "yas tutuyorum",
        "panik",
        "çok üzgünüm",
        "dayanamıyorum",
    )

    SUPPORT_SIGNALS = (
        "verdrietig",
        "gestrest",
        "stress",
        "moe",
        "bang",
        "onzeker",
        "eenzaam",
        "overweldigd",
        "boos",
        "üzgün",
        "stresli",
        "yorgun",
        "korkuyorum",
        "kararsız",
        "yalnız",
        "kızgınım",
    )

    CELEBRATION_SIGNALS = (
        "test is geslaagd",
        "het is gelukt",
        "we hebben het gehaald",
        "klaar!",
        "geslaagd!",
        "succesvol afgerond",
        "başardık",
        "test başarılı",
        "tamamlandı",
        "oldu!",
    )

    POSITIVE_SIGNALS = (
        "goed nieuws",
        "mooi",
        "top",
        "fijn",
        "geweldig",
        "tevreden",
        "blij",
        "güzel haber",
        "harika",
        "memnunum",
        "mutluyum",
    )

    TECHNICAL_SIGNALS = (
        "python",
        "docker",
        "ollama",
        "runtime",
        "server",
        "vps",
        "bestand",
        "code",
        "module",
        "terminal",
        "termius",
        "compile",
        "test",
        "hata",
        "kod",
        "sunucu",
        "dosya",
        "modül",
    )

    URGENT_SIGNALS = (
        "dringend",
        "meteen",
        "direct",
        "zo snel mogelijk",
        "nu oplossen",
        "spoed",
        "acil",
        "hemen",
        "şimdi çöz",
    )

    CAUTIOUS_SIGNALS = (
        "betaling",
        "bankrekening",
        "geld overmaken",
        "wachtwoord",
        "pincode",
        "token",
        "api key",
        "private key",
        "privésleutel",
        "account verwijderen",
        "ödeme",
        "banka",
        "para gönder",
        "şifre",
        "hesap sil",
    )

    CASUAL_SIGNALS = (
        "hoe gaat het",
        "hoe was je dag",
        "wat vind jij",
        "haha",
        "gezellig",
        "nasılsın",
        "günün nasıldı",
        "sence",
    )

    ENGLISH_ALLOWLIST = {
        "ai",
        "api",
        "app",
        "chat",
        "code",
        "docker",
        "engine",
        "json",
        "linux",
        "memory",
        "model",
        "ollama",
        "prompt",
        "python",
        "runtime",
        "server",
        "sprint",
        "test",
        "vps",
    }

    ENGLISH_FILLER_PATTERNS = (
        "thanks for asking",
        "great news",
        "awesome",
        "sure thing",
        "of course",
        "let me know",
        "how can i help",
        "i am happy to help",
    )

    OVEREXCITED_PATTERNS = (
        "ik ben zo trots op je",
        "dit is geweldig geweldig",
        "ongelooflijk fantastisch",
        "prachtig nieuws",
        "we did it",
        "let's gooo",
        "yaşasın",
        "seninle gurur duyuyorum",
    )

    @staticmethod
    def normalize(message: str) -> str:
        """Normaliseert een bericht voor vergelijking."""
        return " ".join(message.casefold().strip().split())

    @staticmethod
    def contains_any(
        message: str,
        signals: tuple[str, ...],
    ) -> bool:
        """Controleert of een bekend signaal voorkomt."""
        return any(signal in message for signal in signals)

    @staticmethod
    def clamp(value: int) -> int:
        """Beperkt een intensiteitswaarde tot 0–5."""
        return max(0, min(5, value))

    def determine_mode(
        self,
        context: ContextState,
    ) -> EmotionMode:
        """Bepaalt de belangrijkste emotionele situatie."""
        message = self.normalize(context.user_message)

        if self.contains_any(message, self.CAUTIOUS_SIGNALS):
            return "cautious"

        if self.contains_any(
            message,
            self.STRONG_NEGATIVE_SIGNALS,
        ):
            return "serious"

        if self.contains_any(message, self.SUPPORT_SIGNALS):
            return "supportive"

        if (
            context.urgency == "high"
            or self.contains_any(message, self.URGENT_SIGNALS)
        ):
            return "urgent"

        if self.contains_any(
            message,
            self.CELEBRATION_SIGNALS,
        ):
            return "celebration"

        if self.contains_any(message, self.POSITIVE_SIGNALS):
            return "positive"

        if self.contains_any(message, self.CASUAL_SIGNALS):
            return "casual"

        if self.contains_any(message, self.TECHNICAL_SIGNALS):
            return "technical"

        return "neutral"

    @staticmethod
    def base_values(
        mode: EmotionMode,
    ) -> tuple[int, int, int, int, int]:
        """
        Geeft terug:
        warmte, directheid, empathie, enthousiasme, humor.
        """
        values = {
            "neutral": (3, 3, 2, 1, 0),
            "casual": (4, 3, 2, 2, 1),
            "positive": (4, 3, 2, 3, 1),
            "celebration": (4, 4, 2, 3, 1),
            "supportive": (5, 2, 5, 0, 0),
            "serious": (5, 3, 5, 0, 0),
            "technical": (3, 5, 1, 0, 0),
            "urgent": (3, 5, 2, 0, 0),
            "cautious": (3, 5, 2, 0, 0),
        }

        return values[mode]

    @staticmethod
    def determine_pace(mode: EmotionMode) -> AnswerPace:
        """Bepaalt het gewenste antwoordtempo."""
        if mode in {"technical", "urgent", "cautious"}:
            return "direct"

        if mode in {"supportive", "serious"}:
            return "slow"

        return "normal"

    @staticmethod
    def determine_detail(
        context: ContextState,
        mode: EmotionMode,
    ) -> AnswerDetail:
        """Bepaalt hoeveel detail passend is."""
        if context.message_type == "confirmation":
            return "very_short"

        if mode in {
            "celebration",
            "positive",
            "casual",
        }:
            return "short"

        if mode in {"urgent", "cautious"}:
            return "short"

        if mode == "technical":
            return "detailed"

        return "normal"

    @staticmethod
    def emoji_policy(
        mode: EmotionMode,
    ) -> tuple[bool, int]:
        """Bepaalt of en hoeveel emoji's zijn toegestaan."""
        if mode == "celebration":
            return True, 1

        if mode in {"casual", "positive"}:
            return True, 1

        return False, 0

    @staticmethod
    def language_rules(language: str) -> list[str]:
        """Geeft strikte taalregels voor Nederlands of Turks."""
        if language == "tr":
            return [
                "Yanıtı doğal Türkçe yaz.",
                "Gereksiz İngilizce ifadeler kullanma.",
                "Teknik ürün veya yazılım adlarını çevirmeden bırakabilirsin.",
                "Aynı cevap içinde Türkçe ve Hollandacayı karıştırma.",
            ]

        return [
            "Schrijf het antwoord volledig in natuurlijk Nederlands.",
            "Gebruik geen Engelse beleefdheids- of stopzinnen.",
            "Technische product- en softwarenamen mogen Engels blijven.",
            "Meng Nederlands en Turks niet binnen hetzelfde antwoord.",
        ]

    @staticmethod
    def tone_instruction(
        language: str,
        mode: EmotionMode,
    ) -> str:
        """Geeft één compacte centrale tooninstructie."""
        dutch = {
            "neutral": (
                "Reageer rustig, menselijk en zonder overdreven emotie."
            ),
            "casual": (
                "Reageer ontspannen en natuurlijk, alsof je rechtstreeks "
                "met Zeki praat."
            ),
            "positive": (
                "Reageer positief maar beheerst; maak het niet groter "
                "dan het is."
            ),
            "celebration": (
                "Erken het succes kort en geloofwaardig en ga daarna "
                "direct verder."
            ),
            "supportive": (
                "Erken het gevoel eerst oprecht en bied daarna rustige, "
                "haalbare ondersteuning."
            ),
            "serious": (
                "Reageer zorgvuldig, warm en serieus; gebruik geen humor "
                "of opgewektheid."
            ),
            "technical": (
                "Wees helder, precies en praktisch. Vermijd lange "
                "inleidingen."
            ),
            "urgent": (
                "Geef eerst de belangrijkste concrete actie. Houd het "
                "antwoord strak en overzichtelijk."
            ),
            "cautious": (
                "Benoem de relevante grens rustig en geef alleen een "
                "veilig alternatief of voorbereiding."
            ),
        }

        turkish = {
            "neutral": (
                "Sakin, doğal ve abartısız cevap ver."
            ),
            "casual": (
                "Zeki ile doğrudan konuşuyormuş gibi rahat ve doğal cevap ver."
            ),
            "positive": (
                "Olumlu fakat ölçülü cevap ver; durumu gereğinden fazla büyütme."
            ),
            "celebration": (
                "Başarıyı kısa ve samimi biçimde kutla, sonra doğrudan devam et."
            ),
            "supportive": (
                "Önce duyguyu samimi biçimde kabul et, sonra sakin ve "
                "uygulanabilir destek sun."
            ),
            "serious": (
                "Dikkatli, sıcak ve ciddi cevap ver; mizah veya neşeli "
                "bir ton kullanma."
            ),
            "technical": (
                "Açık, kesin ve pratik ol. Uzun girişlerden kaçın."
            ),
            "urgent": (
                "Önce en önemli somut adımı ver. Cevabı kısa ve düzenli tut."
            ),
            "cautious": (
                "İlgili sınırı sakin biçimde belirt ve yalnızca güvenli "
                "bir alternatif veya hazırlık sun."
            ),
        }

        if language == "tr":
            return turkish[mode]

        return dutch[mode]

    def build(
        self,
        context: ContextState,
        personality: PersonalityGuidance,
    ) -> EmotionGuidance:
        """Bouwt EmotionGuidance voor één gebruikersbericht."""
        if not context.context_completed or not context.successful:
            raise InvalidEmotionInputError(
                "De ContextState is niet succesvol voltooid."
            )

        if not context.user_message.strip():
            raise InvalidEmotionInputError(
                "Het gebruikersbericht is leeg."
            )

        if not personality.completed:
            raise InvalidEmotionInputError(
                "De PersonalityGuidance is niet voltooid."
            )

        language = "tr" if context.language == "tr" else "nl"
        mode = self.determine_mode(context)

        (
            base_warmth,
            base_directness,
            base_empathy,
            base_enthusiasm,
            base_humor,
        ) = self.base_values(mode)

        warmth = self.clamp(
            round((base_warmth + personality.warmth) / 2)
        )
        directness = self.clamp(
            round(
                (
                    base_directness
                    + personality.directness
                )
                / 2
            )
        )
        empathy = self.clamp(
            round(
                (
                    base_empathy
                    + personality.emotional_acknowledgement
                )
                / 2
            )
        )
        humor = self.clamp(
            min(base_humor, personality.humor)
        )
        enthusiasm = self.clamp(base_enthusiasm)

        if mode == "celebration":
            enthusiasm = min(3, enthusiasm)

        if mode in {
            "supportive",
            "serious",
            "technical",
            "urgent",
            "cautious",
        }:
            humor = 0

        emoji_allowed, max_emojis = self.emoji_policy(mode)

        rules = [
            self.tone_instruction(language, mode),
            *self.language_rules(language),
        ]

        if mode == "celebration":
            rules.extend(
                [
                    "Vier het resultaat in maximaal één korte zin.",
                    "Zeg niet dat je trots bent tenzij daar een echte "
                    "persoonlijke reden voor is.",
                    "Ga na de korte erkenning direct verder met de inhoud.",
                ]
            )

        if mode in {"positive", "celebration"}:
            rules.append(
                "Gebruik geen opeenstapeling van complimenten, "
                "uitroeptekens of superlatieven."
            )

        if not emoji_allowed:
            rules.append(
                "Gebruik geen emoji in dit antwoord."
            )
        else:
            rules.append(
                f"Gebruik maximaal {max_emojis} passende emoji."
            )

        forbidden_patterns = [
            *self.ENGLISH_FILLER_PATTERNS,
            *self.OVEREXCITED_PATTERNS,
            "meerdere emoji achter elkaar",
            "meer dan twee uitroeptekens",
            "onnodig herhalen van Zeki's naam",
        ]

        return EmotionGuidance(
            language=language,
            mode=mode,
            warmth=warmth,
            directness=directness,
            empathy=empathy,
            enthusiasm=enthusiasm,
            humor=humor,
            emoji_allowed=emoji_allowed,
            max_emojis=max_emojis,
            answer_pace=self.determine_pace(mode),
            answer_detail=self.determine_detail(
                context,
                mode,
            ),
            language_lock=True,
            allow_english_terms=True,
            tone_instruction=self.tone_instruction(
                language,
                mode,
            ),
            response_rules=rules,
            forbidden_patterns=forbidden_patterns,
            completed=True,
        )


def self_test() -> int:
    """Test de belangrijkste emotionele situaties."""
    from bilge.personality_layer import PersonalityLayer

    print("===== Emotion Controller-test =====")

    personality_layer = PersonalityLayer()
    controller = EmotionController()

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
            1,
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="nl",
                user_message="De test is geslaagd!",
                message_type="statement",
                confidence=1.0,
            ),
            "celebration",
            1,
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="nl",
                user_message="Ik voel me erg gestrest en moe.",
                message_type="statement",
                confidence=1.0,
            ),
            "supportive",
            0,
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="nl",
                user_message=(
                    "Geef het volledige Python-bestand voor de runtime."
                ),
                message_type="command",
                confidence=1.0,
            ),
            "technical",
            0,
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
            "celebration",
            1,
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
            0,
        ),
    ]

    for context, expected_mode, expected_max_emojis in tests:
        personality = personality_layer.build(context)
        result = controller.build(
            context,
            personality,
        )

        print()
        print(f"Bericht      : {context.user_message}")
        print(f"Taal         : {result.language}")
        print(f"Modus        : {result.mode}")
        print(f"Warmte       : {result.warmth}")
        print(f"Directheid   : {result.directness}")
        print(f"Empathie     : {result.empathy}")
        print(f"Enthousiasme : {result.enthusiasm}")
        print(f"Humor        : {result.humor}")
        print(f"Emoji's      : {result.max_emojis}")
        print(f"Tempo        : {result.answer_pace}")
        print(f"Detail       : {result.answer_detail}")

        if result.mode != expected_mode:
            print(
                f"FOUT: verwacht modus '{expected_mode}', "
                f"maar kreeg '{result.mode}'."
            )
            return 1

        if result.max_emojis != expected_max_emojis:
            print(
                f"FOUT: verwacht maximaal "
                f"{expected_max_emojis} emoji, maar kreeg "
                f"{result.max_emojis}."
            )
            return 1

        if not result.language_lock:
            print(
                "FOUT: de taalvergrendeling is niet actief."
            )
            return 1

        if not result.completed:
            print(
                "FOUT: EmotionGuidance is niet voltooid."
            )
            return 1

    print()
    print("Emotion Controller-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
