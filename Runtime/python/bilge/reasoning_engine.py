#!/usr/bin/env python3
"""
Bilge OS - Reasoning Engine

Maakt een veilig en gestructureerd antwoordplan op basis van:
- de ContextState;
- de beslissing van de Memory Manager;
- eenvoudige kenmerken van het gebruikersbericht.

Deze module:
- genereert nog geen definitief antwoord;
- gebruikt nog geen AI-model;
- voert geen externe acties uit;
- toont geen verborgen interne redeneerstappen;
- geeft alleen een compacte, begrijpelijke onderbouwing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from bilge.memory_manager import MemoryDecision
from bilge.models import ContextState


ResponseStyle = Literal[
    "concise",
    "normal",
    "detailed",
    "step_by_step",
    "comparison",
    "supportive",
    "clarifying",
]

ResponseTone = Literal[
    "warm",
    "neutral",
    "professional",
    "motivating",
    "empathetic",
    "cautious",
]


class ReasoningEngineError(Exception):
    """Basisfout voor problemen binnen de Reasoning Engine."""


class InvalidReasoningInputError(ReasoningEngineError):
    """De aangeleverde context of geheugenbeslissing is ongeldig."""


@dataclass(slots=True)
class ReasoningPlan:
    """Compact antwoordplan van de Reasoning Engine."""

    objective: str = ""
    response_style: ResponseStyle = "normal"
    tone: ResponseTone = "warm"
    should_ask_question: bool = False
    clarification_question: str = ""
    use_memory_types: list[str] = field(default_factory=list)
    include_explanation: bool = True
    include_steps: bool = False
    include_comparison: bool = False
    acknowledge_emotion: bool = False
    safety_attention: bool = False
    answer_allowed: bool = True
    concise_rationale: list[str] = field(default_factory=list)
    completed: bool = False


class ReasoningEngine:
    """Bepaalt hoe Bilge het beste op een bericht kan reageren."""

    EMOTION_WORDS = {
        "bang",
        "boos",
        "eenzaam",
        "gestrest",
        "moe",
        "onzeker",
        "overweldigd",
        "verdrietig",
        "zenuwachtig",
        "korkuyorum",
        "kızgınım",
        "stresli",
        "üzgün",
        "yalnız",
        "yorgun",
    }

    DECISION_PHRASES = {
        "ik twijfel",
        "welke moet ik kiezen",
        "wat zou jij kiezen",
        "wat zou jij doen",
        "voor- en nadelen",
        "vergelijk",
        "kararsızım",
        "hangisini seçmeliyim",
        "sen olsan ne yapardın",
        "karşılaştır",
    }

    PLANNING_WORDS = {
        "plan",
        "planning",
        "stappenplan",
        "roadmap",
        "schema",
        "agenda",
        "plannen",
        "takvim",
        "planlama",
        "yol haritası",
    }

    EXPLANATION_WORDS = {
        "hoe",
        "waarom",
        "leg uit",
        "uitleg",
        "wat is",
        "nasıl",
        "neden",
        "açıkla",
        "nedir",
    }

    HIGH_RISK_WORDS = {
        "wachtwoord",
        "pincode",
        "api key",
        "api-key",
        "token",
        "seed phrase",
        "herstelzin",
        "privésleutel",
        "private key",
        "betaling",
        "bankrekening",
        "geld overmaken",
        "password",
        "şifre",
        "ödeme",
        "banka",
    }

    EXTERNAL_ACTION_WORDS = {
        "verstuur",
        "verzend",
        "boek",
        "betaal",
        "maak een afspraak",
        "stuur een mail",
        "whatsapp",
        "wijzig mijn agenda",
        "sil",
        "gönder",
        "öde",
        "randevu oluştur",
    }

    SIMPLE_CONFIRMATIONS = {
        "ja",
        "nee",
        "ok",
        "oke",
        "oké",
        "goed",
        "top",
        "doe maar",
        "kom maar op",
        "laat maar komen",
        "evet",
        "hayır",
        "tamam",
        "olur",
        "devam",
    }

    @staticmethod
    def normalize_message(message: str) -> str:
        """Normaliseert het gebruikersbericht."""
        return " ".join(message.lower().strip().split())

    @staticmethod
    def extract_words(message: str) -> set[str]:
        """Haalt woorden uit een bericht."""
        return set(
            re.findall(
                r"[A-Za-zÀ-ÖØ-öø-ÿĞğİıŞşÇç]+",
                message.lower(),
            )
        )

    def contains_phrase(
        self,
        message: str,
        phrases: set[str],
    ) -> bool:
        """Controleert of minstens één bekende frase aanwezig is."""
        return any(phrase in message for phrase in phrases)

    def detect_emotional_support(
        self,
        message: str,
        words: set[str],
    ) -> bool:
        """Controleert of empathische ondersteuning passend is."""
        if words.intersection(self.EMOTION_WORDS):
            return True

        emotional_phrases = {
            "ik voel me",
            "ik zit niet lekker",
            "het gaat niet goed",
            "ik trek het niet",
            "kendimi kötü hissediyorum",
            "iyi hissetmiyorum",
        }

        return self.contains_phrase(message, emotional_phrases)

    def detect_decision_request(self, message: str) -> bool:
        """Controleert of de gebruiker hulp bij een keuze vraagt."""
        return self.contains_phrase(
            message,
            self.DECISION_PHRASES,
        )

    def detect_planning_request(
        self,
        message: str,
        words: set[str],
    ) -> bool:
        """Controleert of een stappenplan waarschijnlijk nuttig is."""
        if words.intersection(self.PLANNING_WORDS):
            return True

        return "stap voor stap" in message

    def detect_explanation_request(self, message: str) -> bool:
        """Controleert of inhoudelijke uitleg gevraagd wordt."""
        return self.contains_phrase(
            message,
            self.EXPLANATION_WORDS,
        )

    def detect_safety_attention(self, message: str) -> bool:
        """Controleert of extra veiligheidsaandacht nodig is."""
        return self.contains_phrase(
            message,
            self.HIGH_RISK_WORDS,
        )

    def requests_external_action(self, message: str) -> bool:
        """
        Controleert of een externe actie wordt gevraagd.

        Bilge v1 mag zulke acties niet zelfstandig uitvoeren.
        """
        return self.contains_phrase(
            message,
            self.EXTERNAL_ACTION_WORDS,
        )

    def determine_objective(
        self,
        context: ContextState,
        *,
        emotional: bool,
        decision: bool,
        planning: bool,
        explanation: bool,
    ) -> str:
        """Bepaalt het hoofddoel van het antwoord."""
        if emotional:
            return "emotional_support"

        if decision:
            return "decision_support"

        if planning:
            return "create_plan"

        if explanation:
            return "explain_clearly"

        objective_by_intent = {
            "continue_previous_task": "continue_task",
            "request_information": "provide_information",
            "request_action": "prepare_requested_work",
            "conversation": "natural_conversation",
            "share_information": "acknowledge_and_respond",
        }

        return objective_by_intent.get(
            context.intent,
            "respond_helpfully",
        )

    def build(
        self,
        context: ContextState,
        memory_decision: MemoryDecision,
    ) -> ReasoningPlan:
        """Maakt een antwoordplan voor één gebruikersbericht."""
        if not context.context_completed or not context.successful:
            raise InvalidReasoningInputError(
                "De ContextState is niet succesvol voltooid."
            )

        if not context.user_message.strip():
            raise InvalidReasoningInputError(
                "De ContextState bevat geen gebruikersbericht."
            )

        message = self.normalize_message(context.user_message)
        words = self.extract_words(message)

        emotional = self.detect_emotional_support(
            message,
            words,
        )
        decision = self.detect_decision_request(message)
        planning = self.detect_planning_request(
            message,
            words,
        )
        explanation = self.detect_explanation_request(message)
        safety_attention = self.detect_safety_attention(message)
        external_action = self.requests_external_action(message)

        objective = self.determine_objective(
            context,
            emotional=emotional,
            decision=decision,
            planning=planning,
            explanation=explanation,
        )

        style: ResponseStyle = "normal"
        tone: ResponseTone = "warm"
        include_steps = False
        include_comparison = False
        should_ask_question = False
        clarification_question = ""
        rationale: list[str] = []

        if emotional:
            style = "supportive"
            tone = "empathetic"
            rationale.append(
                "Het bericht bevat een emotioneel signaal; "
                "een warme en empathische reactie past beter."
            )

        elif decision:
            style = "comparison"
            tone = "neutral"
            include_comparison = True
            rationale.append(
                "Zeki vraagt hulp bij een keuze; een vergelijking "
                "met voor- en nadelen is passend."
            )

        elif planning:
            style = "step_by_step"
            tone = "motivating"
            include_steps = True
            rationale.append(
                "Het bericht gaat over plannen; een duidelijk "
                "stappenplan is passend."
            )

        elif explanation:
            style = "detailed"
            tone = "warm"
            rationale.append(
                "Het bericht vraagt om uitleg; helderheid en "
                "voldoende context zijn belangrijk."
            )

        elif message in self.SIMPLE_CONFIRMATIONS:
            style = "concise"
            tone = "warm"
            rationale.append(
                "Het bericht is een korte bevestiging; een kort "
                "antwoord voorkomt onnodige tekst."
            )

        if context.clarification_required:
            style = "clarifying"
            should_ask_question = True
            clarification_question = (
                "Kun je één detail verduidelijken zodat ik je "
                "betrouwbaar kan helpen?"
            )
            rationale.append(
                "De Context Builder geeft aan dat belangrijke "
                "informatie ontbreekt."
            )

        if context.confidence < 0.55:
            should_ask_question = True

            if not clarification_question:
                clarification_question = (
                    "Kun je iets meer vertellen over wat je precies "
                    "wilt bereiken?"
                )

            rationale.append(
                "De contextanalyse heeft een lage zekerheid; "
                "een verduidelijkende vraag voorkomt aannames."
            )

        answer_allowed = True

        if external_action:
            safety_attention = True
            rationale.append(
                "Het bericht lijkt om een externe actie te vragen. "
                "Bilge v1 mag alleen adviseren of voorbereiden."
            )

        if safety_attention:
            tone = "cautious"
            rationale.append(
                "Het onderwerp vraagt extra aandacht voor privacy, "
                "geheime gegevens of financiële veiligheid."
            )

        if memory_decision.memory_types:
            rationale.append(
                "Relevante geheugenbronnen: "
                + ", ".join(memory_decision.memory_types)
                + "."
            )
        else:
            rationale.append(
                "Voor dit antwoord is geen geheugenbron nodig."
            )

        return ReasoningPlan(
            objective=objective,
            response_style=style,
            tone=tone,
            should_ask_question=should_ask_question,
            clarification_question=clarification_question,
            use_memory_types=list(
                memory_decision.memory_types
            ),
            include_explanation=style != "concise",
            include_steps=include_steps,
            include_comparison=include_comparison,
            acknowledge_emotion=emotional,
            safety_attention=safety_attention,
            answer_allowed=answer_allowed,
            concise_rationale=rationale,
            completed=True,
        )


def print_plan(
    context: ContextState,
    plan: ReasoningPlan,
) -> None:
    """Toont een antwoordplan zonder verborgen redeneerstappen."""
    print()
    print(f"Bericht       : {context.user_message}")
    print(f"Doel          : {plan.objective}")
    print(f"Stijl         : {plan.response_style}")
    print(f"Toon          : {plan.tone}")
    print(f"Doorvragen    : {plan.should_ask_question}")
    print(f"Stappen       : {plan.include_steps}")
    print(f"Vergelijking  : {plan.include_comparison}")
    print(f"Emotie        : {plan.acknowledge_emotion}")
    print(f"Safety        : {plan.safety_attention}")
    print(
        "Geheugen      : "
        + (
            " -> ".join(plan.use_memory_types)
            if plan.use_memory_types
            else "none"
        )
    )
    print(f"Antwoord mag  : {plan.answer_allowed}")
    print(f"Gereed        : {plan.completed}")

    if plan.clarification_question:
        print(
            f"Verduidelijking: {plan.clarification_question}"
        )


def self_test() -> int:
    """Voert lokale tests uit zonder AI-model of externe verbindingen."""
    from bilge.memory_manager import MemoryManager

    engine = ReasoningEngine()
    manager = MemoryManager()

    tests = [
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="nl",
                user_message="Ik twijfel tussen twee auto's.",
                intent="request_information",
                message_type="statement",
                confidence=0.9,
            ),
            "comparison",
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="nl",
                user_message="Help me een planning maken.",
                intent="request_action",
                message_type="command",
                confidence=1.0,
            ),
            "step_by_step",
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="nl",
                user_message="Ik voel me vandaag gestrest.",
                intent="share_information",
                message_type="statement",
                confidence=0.9,
            ),
            "supportive",
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="nl",
                user_message="Oké",
                intent="continue_previous_task",
                message_type="confirmation",
                confidence=1.0,
                probable_follow_up=True,
            ),
            "concise",
        ),
        (
            ContextState(
                completed=True,
                context_completed=True,
                language="nl",
                user_message=(
                    "Betaal deze factuur via mijn bankrekening."
                ),
                intent="request_action",
                message_type="command",
                confidence=1.0,
            ),
            "normal",
        ),
    ]

    print("===== Reasoning Engine-test =====")

    for context, expected_style in tests:
        memory_decision = manager.decide(context)
        plan = engine.build(context, memory_decision)
        print_plan(context, plan)

        if plan.response_style != expected_style:
            print()
            print(
                f"FOUT: verwacht stijl '{expected_style}', "
                f"maar kreeg '{plan.response_style}'."
            )
            return 1

    financial_context = tests[-1][0]
    financial_decision = manager.decide(financial_context)
    financial_plan = engine.build(
        financial_context,
        financial_decision,
    )

    if not financial_plan.safety_attention:
        print(
            "FOUT: financiële of externe actie activeerde "
            "geen Safety-aandacht."
        )
        return 1

    print()
    print("Reasoning Engine-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
