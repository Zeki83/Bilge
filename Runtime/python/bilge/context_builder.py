#!/usr/bin/env python3
"""
Bilge OS - Context Builder

Analyseert een gebruikersbericht en bouwt een ContextState.

Deze versie:
- controleert lege berichten;
- normaliseert tekst;
- herkent voorlopig Nederlands en Turks;
- bepaalt een eenvoudig berichttype;
- schat de intentie;
- herkent mogelijke vervolgberichten;
- schat urgentie;
- gebruikt geen externe apps, diensten, geheugen of AI-model.
"""

from __future__ import annotations

import re

from bilge.models import ContextState


class ContextBuilderError(Exception):
    """Basisfout voor problemen binnen de Context Builder."""


class EmptyMessageError(ContextBuilderError):
    """Het ontvangen gebruikersbericht is leeg."""


class ContextBuilder:
    """Bouwt basiscontext voor een bericht van Zeki."""

    DUTCH_WORDS = {
        "aan", "als", "ben", "dat", "de", "dit", "een", "en",
        "gaan", "heb", "het", "hoe", "ik", "is", "kan", "kom",
        "kunnen", "laat", "laten", "maar", "me", "met", "mijn",
        "niet", "nu", "of", "om", "op", "te", "van", "voor",
        "wat", "we", "wil", "zijn",
    }

    TURKISH_WORDS = {
        "ama", "ben", "bir", "bu", "çok", "da", "de", "değil",
        "devam", "evet", "hayır", "için", "ile", "iyi", "mı",
        "mi", "mu", "mü", "nasıl", "ne", "olur", "sen", "şimdi",
        "tamam", "ve", "var", "yok",
    }

    TURKISH_CHARACTERS = set("çğıöşüÇĞİÖŞÜ")

    FOLLOW_UP_PHRASES = {
        "dat is goed",
        "doe maar",
        "ga verder",
        "gas erop",
        "kom maar op",
        "laat maar komen",
        "laten we verder gaan",
        "ok",
        "oke",
        "oké",
        "ja",
        "nee",
        "tamam",
        "devam",
        "olur",
        "evet",
        "hayır",
    }

    COMMAND_STARTERS = {
        "maak", "geef", "laat", "doe", "controleer", "vervang",
        "schrijf", "bouw", "start", "stop", "help", "toon",
    }

    TURKISH_COMMAND_STARTERS = {
        "yap", "göster", "başlat", "durdur", "yardım", "devam",
    }

    URGENT_WORDS = {
        "dringend", "spoed", "meteen", "direct", "nu", "urgent",
        "acil", "hemen", "şimdi",
    }

    def normalize_message(self, user_message: str) -> str:
        """Verwijdert overbodige witruimte."""
        return " ".join(user_message.strip().split())

    def extract_words(self, user_message: str) -> list[str]:
        """Haalt eenvoudige woorden uit een bericht."""
        return re.findall(
            r"[A-Za-zÀ-ÖØ-öø-ÿĞğİıŞşÇç]+",
            user_message.lower(),
        )

    def detect_language(self, user_message: str) -> tuple[str, float]:
        """Schat of het bericht Nederlands of Turks is."""
        words = self.extract_words(user_message)

        dutch_score = sum(word in self.DUTCH_WORDS for word in words)
        turkish_score = sum(word in self.TURKISH_WORDS for word in words)

        if any(char in self.TURKISH_CHARACTERS for char in user_message):
            turkish_score += 2

        total_score = dutch_score + turkish_score

        if turkish_score > dutch_score:
            confidence = (
                turkish_score / total_score if total_score else 0.6
            )
            return "tr", round(confidence, 2)

        confidence = dutch_score / total_score if total_score else 0.5
        return "nl", round(max(confidence, 0.5), 2)

    def detect_message_type(self, user_message: str) -> str:
        """Bepaalt het globale type van het bericht."""
        normalized = user_message.lower().strip()
        words = self.extract_words(normalized)

        if normalized in self.FOLLOW_UP_PHRASES:
            return "confirmation"

        if normalized.endswith("?"):
            return "question"

        if words:
            first_word = words[0]

            if (
                first_word in self.COMMAND_STARTERS
                or first_word in self.TURKISH_COMMAND_STARTERS
            ):
                return "command"

        return "statement"

    def detect_intent(
        self,
        user_message: str,
        message_type: str,
    ) -> str:
        """Schat wat Zeki met het bericht probeert te bereiken."""
        normalized = user_message.lower()

        if message_type == "confirmation":
            return "continue_previous_task"

        if message_type == "question":
            return "request_information"

        if message_type == "command":
            return "request_action"

        conversational_phrases = {
            "hoe gaat het",
            "nasılsın",
            "goedemorgen",
            "goedenavond",
            "merhaba",
            "selam",
        }

        if any(
            phrase in normalized
            for phrase in conversational_phrases
        ):
            return "conversation"

        return "share_information"

    def detect_urgency(self, user_message: str) -> str:
        """Schat of het bericht normale of hoge urgentie heeft."""
        words = set(self.extract_words(user_message))

        if words.intersection(self.URGENT_WORDS):
            return "high"

        return "normal"

    def is_probable_follow_up(self, user_message: str) -> bool:
        """Herkent duidelijke korte vervolgreacties."""
        return user_message.lower().strip() in self.FOLLOW_UP_PHRASES

    def build(self, user_message: str) -> ContextState:
        """Bouwt een ContextState voor één gebruikersbericht."""
        normalized_message = self.normalize_message(user_message)

        if not normalized_message:
            raise EmptyMessageError(
                "Het gebruikersbericht is leeg."
            )

        language, language_confidence = self.detect_language(
            normalized_message
        )
        message_type = self.detect_message_type(normalized_message)
        intent = self.detect_intent(
            normalized_message,
            message_type,
        )
        probable_follow_up = self.is_probable_follow_up(
            normalized_message
        )
        urgency = self.detect_urgency(normalized_message)

        confidence = language_confidence

        if message_type != "statement":
            confidence = min(1.0, confidence + 0.1)

        state = ContextState(
            completed=True,
            context_completed=True,
            language=language,
            user_message=normalized_message,
            topic="",
            intent=intent,
            message_type=message_type,
            urgency=urgency,
            confidence=round(confidence, 2),
            probable_follow_up=probable_follow_up,
            memory_required=probable_follow_up,
            clarification_required=False,
            active_project=None,
            relevant_documents=[],
        )

        return state


def self_test() -> int:
    """Voert lokale tests uit zonder externe verbindingen."""
    builder = ContextBuilder()

    test_messages = [
        "Laten we verder gaan",
        "Nasılsın Bilge?",
        "Help me met mijn planning.",
        "Dit moet nu direct gebeuren.",
    ]

    print("===== Context Builder-test =====")

    for message in test_messages:
        state = builder.build(message)

        print()
        print(f"Bericht      : {state.user_message}")
        print(f"Taal         : {state.language}")
        print(f"Type         : {state.message_type}")
        print(f"Intentie     : {state.intent}")
        print(f"Urgentie     : {state.urgency}")
        print(f"Vervolg      : {state.probable_follow_up}")
        print(f"Zekerheid    : {state.confidence}")
        print(f"Gereed       : {state.context_completed}")

    try:
        builder.build("   ")
    except EmptyMessageError:
        print()
        print("Leeg bericht correct geweigerd.")
    else:
        print()
        print("FOUT: leeg bericht werd niet geweigerd.")
        return 1

    print()
    print("Context Builder-test geslaagd.")

    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
