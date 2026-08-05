#!/usr/bin/env python3
"""
Bilge OS - Response Formatter

Zet een ContextState en ReasoningPlan om in concrete
ResponseInstructions en een ResponseDraft.

Deze module:
- genereert nog niet het definitieve antwoord;
- stuurt nog geen AI-model aan;
- gebruikt de centrale antwoordtemplates;
- vertaalt redeneerkeuzes naar toon, lengte en structuur;
- bewaakt de huidige veiligheidsgrenzen van Bilge.
"""

from __future__ import annotations

from bilge.models import ContextState
from bilge.reasoning_engine import ReasoningPlan
from bilge.response_templates import (
    ResponseTemplateError,
    ResponseTemplateLibrary,
)
from bilge.response_types import (
    ResponseDraft,
    ResponseFormat,
    ResponseInstructions,
    ResponseLength,
    SafetyMode,
)


class ResponseFormatterError(Exception):
    """Basisfout voor problemen binnen de Response Formatter."""


class InvalidResponseInputError(ResponseFormatterError):
    """De aangeleverde context of het antwoordplan is ongeldig."""


class ResponseFormatter:
    """Bouwt concrete antwoordrichtlijnen voor het AI-model."""

    ALWAYS_FORBIDDEN_ACTIONS = [
        "Doe niet alsof een externe actie is uitgevoerd.",
        "Voer geen betalingen, bankhandelingen of aankopen uit.",
        "Stuur geen e-mails, berichten of agenda-afspraken.",
        "Sla geen wachtwoorden, pincodes, tokens of sleutels op.",
        "Verzin geen functies, herinneringen, feiten of resultaten.",
        "Toon geen verborgen interne redeneerstappen.",
    ]

    DUTCH_SAFETY_MESSAGES = {
        "normal": "",
        "warning": (
            "Benoem het relevante risico kort en help met een veilige "
            "voorbereiding of alternatief."
        ),
        "restricted": (
            "Leg duidelijk uit dat Bilge deze handeling niet uitvoert. "
            "Laat uitvoering en eindbeslissing volledig bij Zeki."
        ),
    }

    TURKISH_SAFETY_MESSAGES = {
        "normal": "",
        "warning": (
            "İlgili riski kısaca belirt ve güvenli bir hazırlık veya "
            "alternatif sun."
        ),
        "restricted": (
            "Bilge'nin bu işlemi yapmadığını açıkça belirt. Uygulamayı "
            "ve son kararı tamamen Zeki'ye bırak."
        ),
    }

    @staticmethod
    def validate_input(
        context: ContextState,
        plan: ReasoningPlan,
    ) -> None:
        """Controleert of de invoer volledig en betrouwbaar is."""
        if not context.context_completed or not context.successful:
            raise InvalidResponseInputError(
                "De ContextState is niet succesvol voltooid."
            )

        if not context.user_message.strip():
            raise InvalidResponseInputError(
                "De ContextState bevat geen gebruikersbericht."
            )

        if not plan.completed:
            raise InvalidResponseInputError(
                "Het ReasoningPlan is nog niet voltooid."
            )

        if not plan.answer_allowed:
            raise InvalidResponseInputError(
                "Het ReasoningPlan staat geen antwoord toe."
            )

    @staticmethod
    def determine_length(
        context: ContextState,
        plan: ReasoningPlan,
    ) -> ResponseLength:
        """Bepaalt de gewenste antwoordlengte."""
        if plan.response_style == "concise":
            return "very_short"

        if plan.should_ask_question:
            return "short"

        if plan.response_style in {
            "step_by_step",
            "comparison",
            "detailed",
        }:
            return "detailed"

        if plan.response_style == "supportive":
            return "normal"

        if context.message_type == "confirmation":
            return "very_short"

        return "normal"

    @staticmethod
    def determine_format(
        plan: ReasoningPlan,
    ) -> ResponseFormat:
        """Bepaalt de gewenste antwoordstructuur."""
        if plan.should_ask_question:
            return "question"

        if plan.include_steps:
            return "steps"

        if plan.include_comparison:
            return "comparison"

        if plan.response_style == "concise":
            return "plain"

        return "paragraphs"

    @staticmethod
    def determine_safety_mode(
        context: ContextState,
        plan: ReasoningPlan,
    ) -> SafetyMode:
        """Bepaalt hoeveel Safety zichtbaar in het antwoord moet zijn."""
        message = context.user_message.lower()

        restricted_phrases = {
            "betaal",
            "betaling uitvoeren",
            "geld overmaken",
            "stuur een mail",
            "verstuur",
            "boek een afspraak",
            "wijzig mijn agenda",
            "verwijder mijn account",
            "öde",
            "para gönder",
            "mail gönder",
            "randevu oluştur",
        }

        if any(
            phrase in message
            for phrase in restricted_phrases
        ):
            return "restricted"

        if plan.safety_attention:
            return "warning"

        return "normal"

    @classmethod
    def safety_message(
        cls,
        language: str,
        safety_mode: SafetyMode,
    ) -> str:
        """Geeft de zichtbare veiligheidsinstructie terug."""
        if language == "tr":
            return cls.TURKISH_SAFETY_MESSAGES[safety_mode]

        return cls.DUTCH_SAFETY_MESSAGES[safety_mode]

    @staticmethod
    def build_body_guidance(
        context: ContextState,
        plan: ReasoningPlan,
        length_guidance: str,
        format_guidance: str,
        safety_guidance: str,
    ) -> list[str]:
        """Bouwt de inhoudelijke schrijfaanwijzingen."""
        guidance = [
            f"Beantwoord het actuele gebruikersbericht: "
            f"{context.user_message}",
            f"Hoofddoel van het antwoord: {plan.objective}.",
            length_guidance,
            format_guidance,
        ]

        if plan.include_explanation:
            guidance.append(
                "Onderbouw de conclusie begrijpelijk, maar toon geen "
                "verborgen interne redeneerstappen."
            )

        if plan.include_steps:
            guidance.append(
                "Maak iedere stap concreet, uitvoerbaar en logisch."
            )

        if plan.include_comparison:
            guidance.append(
                "Gebruik voor alle opties dezelfde relevante criteria."
            )

        if plan.acknowledge_emotion:
            guidance.append(
                "Erken eerst kort en oprecht wat Zeki ervaart voordat "
                "je met oplossingen komt."
            )

        if plan.should_ask_question:
            guidance.append(
                "Geef nog geen uitgebreide oplossing voordat de "
                "verduidelijkende vraag is beantwoord."
            )

            if plan.clarification_question:
                guidance.append(
                    "Gebruik deze verduidelijkende vraag: "
                    + plan.clarification_question
                )

        if plan.use_memory_types:
            guidance.append(
                "Gebruik uitsluitend relevante en betrouwbare informatie "
                "uit deze geheugenbronnen: "
                + ", ".join(plan.use_memory_types)
                + "."
            )
        else:
            guidance.append(
                "Gebruik geen persoonlijke herinneringen wanneer die niet "
                "nodig zijn."
            )

        guidance.append(safety_guidance)
        guidance.append(
            "Maak feiten, aannames en onzekerheden herkenbaar."
        )
        guidance.append(
            "Schrijf natuurlijk en vermijd onnodige herhaling."
        )

        return guidance

    def format(
        self,
        context: ContextState,
        plan: ReasoningPlan,
    ) -> ResponseDraft:
        """Maakt een complete ResponseDraft."""
        self.validate_input(context, plan)

        language = context.language

        if language not in {"nl", "tr"}:
            language = "nl"

        length = self.determine_length(context, plan)
        response_format = self.determine_format(plan)
        safety_mode = self.determine_safety_mode(
            context,
            plan,
        )

        try:
            tone_template = (
                ResponseTemplateLibrary.get_tone_template(
                    language,
                    plan.tone,
                )
            )
            length_guidance = (
                ResponseTemplateLibrary.get_length_guidance(
                    language,
                    length,
                )
            )
            format_guidance = (
                ResponseTemplateLibrary.get_format_guidance(
                    language,
                    response_format,
                )
            )
            safety_guidance = (
                ResponseTemplateLibrary.get_safety_guidance(
                    language,
                    safety_mode,
                )
            )
        except ResponseTemplateError as exc:
            raise ResponseFormatterError(str(exc)) from exc

        instructions = ResponseInstructions(
            language=language,
            tone=plan.tone,
            length=length,
            format=response_format,
            include_explanation=plan.include_explanation,
            include_steps=plan.include_steps,
            include_comparison=plan.include_comparison,
            acknowledge_emotion=plan.acknowledge_emotion,
            ask_clarifying_question=plan.should_ask_question,
            clarification_question=plan.clarification_question,
            safety_mode=safety_mode,
            safety_message=self.safety_message(
                language,
                safety_mode,
            ),
            use_memory_types=list(plan.use_memory_types),
            objective=plan.objective,
            completed=True,
        )

        body_guidance = list(tone_template.body_guidance)
        body_guidance.extend(
            self.build_body_guidance(
                context,
                plan,
                length_guidance,
                format_guidance,
                safety_guidance,
            )
        )

        forbidden_actions = list(
            tone_template.prohibited_patterns
        )
        forbidden_actions.extend(
            self.ALWAYS_FORBIDDEN_ACTIONS
        )

        return ResponseDraft(
            instructions=instructions,
            opening=tone_template.opening_guidance,
            body_guidance=body_guidance,
            closing_guidance=(
                tone_template.closing_guidance
            ),
            forbidden_actions=forbidden_actions,
            completed=True,
        )


def print_draft(
    context: ContextState,
    draft: ResponseDraft,
) -> None:
    """Toont een ResponseDraft overzichtelijk."""
    instructions = draft.instructions

    print()
    print(f"Bericht       : {context.user_message}")
    print(f"Taal          : {instructions.language}")
    print(f"Doel          : {instructions.objective}")
    print(f"Toon          : {instructions.tone}")
    print(f"Lengte        : {instructions.length}")
    print(f"Formaat       : {instructions.format}")
    print(f"Safety        : {instructions.safety_mode}")
    print(
        "Geheugen      : "
        + (
            " -> ".join(instructions.use_memory_types)
            if instructions.use_memory_types
            else "none"
        )
    )
    print(f"Doorvragen    : {instructions.ask_clarifying_question}")
    print(f"Gereed        : {draft.completed}")

    print()
    print("Opening:")
    print(draft.opening)

    print()
    print("Inhoudsrichtlijnen:")
    for item in draft.body_guidance:
        print(f"- {item}")

    print()
    print("Afsluiting:")
    print(draft.closing_guidance)


def self_test() -> int:
    """Test de Response Formatter zonder AI-model."""
    from bilge.memory_manager import MemoryManager
    from bilge.reasoning_engine import ReasoningEngine

    formatter = ResponseFormatter()
    manager = MemoryManager()
    reasoning = ReasoningEngine()

    test_contexts = [
        ContextState(
            completed=True,
            context_completed=True,
            language="nl",
            user_message="Help me een planning maken.",
            intent="request_action",
            message_type="command",
            confidence=1.0,
        ),
        ContextState(
            completed=True,
            context_completed=True,
            language="tr",
            user_message="Bugün kendimi üzgün hissediyorum.",
            intent="share_information",
            message_type="statement",
            confidence=1.0,
        ),
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
    ]

    print("===== Response Formatter-test =====")

    expected = [
        ("steps", "normal"),
        ("paragraphs", "normal"),
        ("paragraphs", "restricted"),
    ]

    for context, expected_values in zip(
        test_contexts,
        expected,
        strict=True,
    ):
        memory_decision = manager.decide(context)
        plan = reasoning.build(
            context,
            memory_decision,
        )
        draft = formatter.format(context, plan)

        print_draft(context, draft)

        expected_format, expected_safety = expected_values

        if draft.instructions.format != expected_format:
            print()
            print(
                f"FOUT: verwacht formaat '{expected_format}', "
                f"maar kreeg '{draft.instructions.format}'."
            )
            return 1

        if draft.instructions.safety_mode != expected_safety:
            print()
            print(
                f"FOUT: verwacht Safety '{expected_safety}', "
                f"maar kreeg '{draft.instructions.safety_mode}'."
            )
            return 1

        if not draft.completed:
            print("FOUT: ResponseDraft is niet voltooid.")
            return 1

    print()
    print("Response Formatter-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
