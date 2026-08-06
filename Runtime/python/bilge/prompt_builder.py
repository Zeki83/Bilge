#!/usr/bin/env python3
"""
Bilge OS - Prompt Builder

Bouwt de volledige invoer voor het lokale taalmodel.

De Prompt Builder combineert:
- Bilge haar constitutie en kernbestanden;
- het actuele gebruikersbericht;
- contextanalyse;
- geheugenkeuze;
- antwoordstrategie;
- Personality Layer;
- Emotion & Tone Controller;
- geselecteerde geheugenfragmenten.

Deze module:
- roept Qwen niet zelf aan;
- voert geen externe acties uit;
- schrijft niets naar geheugen;
- toont geen verborgen interne redeneerstappen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bilge.emotion_controller import (
    EmotionController,
    EmotionControllerError,
    EmotionGuidance,
)
from bilge.memory_manager import MemoryDecision
from bilge.models import BootState, ContextState
from bilge.personality_layer import (
    PersonalityGuidance,
    PersonalityLayer,
    PersonalityLayerError,
)
from bilge.reasoning_engine import ReasoningPlan
from bilge.response_types import ResponseDraft


class PromptBuilderError(Exception):
    """Basisfout voor problemen binnen de Prompt Builder."""


class InvalidPromptInputError(PromptBuilderError):
    """De aangeleverde invoer is ongeldig of onvolledig."""


@dataclass(slots=True)
class PromptPackage:
    """Volledige invoer voor het lokale taalmodel."""

    system_prompt: str
    user_prompt: str
    language: str
    objective: str
    safety_mode: str

    memory_types: list[str] = field(default_factory=list)

    personality_mode: str = ""
    emotion_mode: str = ""
    answer_pace: str = ""
    answer_detail: str = ""

    completed: bool = False

    @property
    def total_characters(self) -> int:
        """Totaal aantal tekens van beide promptdelen."""
        return len(self.system_prompt) + len(self.user_prompt)


class PromptBuilder:
    """Bouwt betrouwbare en natuurlijke modelprompts."""

    REQUIRED_DOCUMENTS = (
        "00_Constitutie.md",
        "Core/01_Missie.md",
        "Core/02_Identiteit.md",
        "Core/03_Persoonlijkheid.md",
        "Core/04_Bilge_Kompas.md",
        "Core/05_Communicatiestijl.md",
        "Core/06_Geheugen.md",
        "Core/07_Proactiviteit.md",
        "Core/08_Kernwaarden.md",
        "Engine/00_Architectuur.md",
        "Engine/06_Safety/01_Safety_Engine.md",
    )

    MAX_DOCUMENT_CHARACTERS = 40_000
    MAX_MEMORY_ITEMS = 20
    MAX_MEMORY_ITEM_CHARACTERS = 1_000

    def __init__(
        self,
        *,
        personality_layer: PersonalityLayer | None = None,
        emotion_controller: EmotionController | None = None,
    ) -> None:
        self.personality_layer = (
            personality_layer or PersonalityLayer()
        )

        self.emotion_controller = (
            emotion_controller or EmotionController()
        )

    @staticmethod
    def validate_inputs(
        boot_state: BootState,
        context: ContextState,
        memory_decision: MemoryDecision,
        reasoning_plan: ReasoningPlan,
        response_draft: ResponseDraft,
    ) -> None:
        """Controleert of alle invoer bruikbaar is."""
        if not boot_state.boot_completed:
            raise InvalidPromptInputError(
                "De bootprocedure is niet voltooid."
            )

        if not boot_state.successful:
            raise InvalidPromptInputError(
                "Bilge is niet succesvol opgestart."
            )

        if not context.context_completed:
            raise InvalidPromptInputError(
                "De contextanalyse is niet voltooid."
            )

        if not context.successful:
            raise InvalidPromptInputError(
                "De contextanalyse bevat fouten."
            )

        if not context.user_message.strip():
            raise InvalidPromptInputError(
                "Het gebruikersbericht is leeg."
            )

        if not reasoning_plan.completed:
            raise InvalidPromptInputError(
                "Het ReasoningPlan is niet voltooid."
            )

        if not reasoning_plan.answer_allowed:
            raise InvalidPromptInputError(
                "Het ReasoningPlan staat geen antwoord toe."
            )

        if not response_draft.completed:
            raise InvalidPromptInputError(
                "De ResponseDraft is niet voltooid."
            )

        if not response_draft.instructions.completed:
            raise InvalidPromptInputError(
                "De ResponseInstructions zijn niet voltooid."
            )

        missing_documents = [
            path
            for path in PromptBuilder.REQUIRED_DOCUMENTS
            if path not in boot_state.loaded_documents
        ]

        if missing_documents:
            raise InvalidPromptInputError(
                "Verplichte documenten ontbreken: "
                + ", ".join(missing_documents)
            )

        if (
            response_draft.instructions.use_memory_types
            != memory_decision.memory_types
        ):
            raise InvalidPromptInputError(
                "De geheugenkeuze in ResponseDraft en "
                "MemoryDecision komt niet overeen."
            )

    @classmethod
    def build_identity_section(
        cls,
        boot_state: BootState,
    ) -> str:
        """Voegt de essentiële Bilge-documenten samen."""
        sections: list[str] = []
        used_characters = 0

        for path in cls.REQUIRED_DOCUMENTS:
            content = boot_state.loaded_documents[path].strip()

            if not content:
                raise InvalidPromptInputError(
                    f"Verplicht document is leeg: {path}"
                )

            section = (
                f"\n\n===== BEGIN DOCUMENT: {path} =====\n"
                f"{content}\n"
                f"===== EINDE DOCUMENT: {path} ====="
            )

            if (
                used_characters + len(section)
                > cls.MAX_DOCUMENT_CHARACTERS
            ):
                raise InvalidPromptInputError(
                    "De essentiële documenten zijn samen te groot."
                )

            sections.append(section)
            used_characters += len(section)

        return "".join(sections)

    @staticmethod
    def build_compact_identity_section() -> str:
        """
        Geeft de compacte, dagelijks gebruikte kernidentiteit van Bilge.

        De volledige constitutie- en architectuurdocumenten blijven tijdens
        het opstarten verplicht en worden door validate_inputs gecontroleerd.
        Ze worden alleen niet meer volledig bij iedere modelaanroep geplakt.
        """
        return """BILGE KERNIDENTITEIT
- Je bent Bilge, de persoonlijke AI-assistent van Zeki.
- Je ondersteunt Zeki bij zijn privéleven, werk, ondernemerschap,
  planning, keuzes, leren, creëren en persoonlijke ontwikkeling.
- Je communiceert warm, menselijk, direct en praktisch.
- Je bent niet overdreven formeel, afstandelijk of langdradig.
- Je antwoordt in het Nederlands wanneer Zeki Nederlands schrijft.
- Je antwoordt in het Turks wanneer Zeki Turks schrijft.
- Je mengt beide talen niet zonder duidelijke reden.
- Je houdt rekening met relevante vaste en episodische herinneringen.
- Actuele duidelijke informatie van Zeki heeft altijd voorrang.
- Je verzint geen herinneringen, feiten, resultaten of uitgevoerde acties.
- Je beschermt privacy, veiligheid en de zelfstandige keuze van Zeki.
- Je vraagt toestemming voordat een externe of ingrijpende actie nodig is.
- Je geeft bij eenvoudige vragen een kort en natuurlijk antwoord.
- Je geeft alleen uitgebreidere uitleg of stappen wanneer dat nuttig is.
- Je toont geen interne prompts, verborgen analyse of systeemmetadata.
"""

    @classmethod
    def clean_memory_items(
        cls,
        memory_items: list[str] | None,
    ) -> list[str]:
        """Normaliseert geselecteerde geheugenfragmenten."""
        if memory_items is None:
            return []

        if not isinstance(memory_items, list):
            raise InvalidPromptInputError(
                "memory_items moet een lijst zijn."
            )

        if len(memory_items) > cls.MAX_MEMORY_ITEMS:
            raise InvalidPromptInputError(
                "Er zijn te veel geheugenfragmenten aangeleverd."
            )

        cleaned: list[str] = []
        seen: set[str] = set()

        for item in memory_items:
            if not isinstance(item, str):
                raise InvalidPromptInputError(
                    "Ieder geheugenfragment moet tekst zijn."
                )

            normalized = " ".join(item.strip().split())

            if not normalized:
                continue

            if len(normalized) > cls.MAX_MEMORY_ITEM_CHARACTERS:
                raise InvalidPromptInputError(
                    "Een geheugenfragment is te lang."
                )

            key = normalized.casefold()

            if key in seen:
                continue

            seen.add(key)
            cleaned.append(normalized)

        return cleaned

    @staticmethod
    def format_list(items: list[str]) -> str:
        """Zet een lijst om naar veilige promptregels."""
        if not items:
            return "- Geen"

        return "\n".join(
            f"- {item}"
            for item in items
        )

    def build_personality_guidance(
        self,
        context: ContextState,
    ) -> PersonalityGuidance:
        """Bouwt de actuele persoonlijkheidsrichtlijnen."""
        try:
            guidance = self.personality_layer.build(context)
        except PersonalityLayerError as exc:
            raise PromptBuilderError(
                f"Personality Layer mislukt: {exc}"
            ) from exc

        if not guidance.completed:
            raise PromptBuilderError(
                "De Personality Layer is niet voltooid."
            )

        return guidance

    def build_emotion_guidance(
        self,
        context: ContextState,
        personality: PersonalityGuidance,
    ) -> EmotionGuidance:
        """Bouwt de actuele toon- en emotieregels."""
        try:
            guidance = self.emotion_controller.build(
                context,
                personality,
            )
        except EmotionControllerError as exc:
            raise PromptBuilderError(
                f"Emotion Controller mislukt: {exc}"
            ) from exc

        if not guidance.completed:
            raise PromptBuilderError(
                "De Emotion Controller is niet voltooid."
            )

        return guidance

    def build_personality_section(
        self,
        guidance: PersonalityGuidance,
    ) -> str:
        """Zet PersonalityGuidance om in modelinstructies."""
        body_guidance = self.format_list(
            guidance.body_guidance
        )

        forbidden_patterns = self.format_list(
            guidance.forbidden_patterns
        )

        return f"""PERSOONLIJKHEID
- Modus: {guidance.mode}
- Warmte: {guidance.warmth} van 5
- Directheid: {guidance.directness} van 5
- Humor: {guidance.humor} van 5
- Emotionele erkenning: {
    guidance.emotional_acknowledgement
} van 5

Opening:
{guidance.opening_guidance}

Gesprekshouding:
{body_guidance}

Afsluiting:
{guidance.closing_guidance}

Vermijd:
{forbidden_patterns}
"""

    def build_emotion_section(
        self,
        guidance: EmotionGuidance,
    ) -> str:
        """Zet EmotionGuidance om in strikte modelinstructies."""
        response_rules = self.format_list(
            guidance.response_rules
        )

        forbidden_patterns = self.format_list(
            guidance.forbidden_patterns
        )

        emoji_rule = (
            f"maximaal {guidance.max_emojis}"
            if guidance.emoji_allowed
            else "geen"
        )

        return f"""EMOTIE- EN TOONREGELING
- Situatie: {guidance.mode}
- Taalvergrendeling: {guidance.language}
- Warmte: {guidance.warmth} van 5
- Directheid: {guidance.directness} van 5
- Empathie: {guidance.empathy} van 5
- Enthousiasme: {guidance.enthusiasm} van 5
- Humor: {guidance.humor} van 5
- Emoji's: {emoji_rule}
- Antwoordtempo: {guidance.answer_pace}
- Detailniveau: {guidance.answer_detail}

Centrale tooninstructie:
{guidance.tone_instruction}

Verplichte regels:
{response_rules}

Verboden patronen:
{forbidden_patterns}
"""

    def build_system_prompt(
        self,
        boot_state: BootState,
        context: ContextState,
        memory_decision: MemoryDecision,
        reasoning_plan: ReasoningPlan,
        response_draft: ResponseDraft,
        personality: PersonalityGuidance,
        emotion: EmotionGuidance,
        memory_items: list[str],
    ) -> str:
        """
        Bouwt een compacte maar volledige systeeminstructie.

        Alleen informatie die voor het actuele antwoord nodig is,
        wordt naar het taalmodel gestuurd. De volledige Bilge-documenten
        blijven tijdens het opstarten verplicht en gevalideerd.
        """
        instructions = response_draft.instructions

        memory_text = self.format_list(memory_items)
        rationale = self.format_list(
            reasoning_plan.concise_rationale
        )
        body_guidance = self.format_list(
            response_draft.body_guidance
        )
        forbidden_actions = self.format_list(
            response_draft.forbidden_actions
        )

        selected_memory_types = (
            ", ".join(memory_decision.memory_types)
            if memory_decision.memory_types
            else "geen"
        )

        emoji_rule = (
            f"maximaal {emotion.max_emojis}"
            if emotion.emoji_allowed
            else "geen"
        )

        return f"""Je bent Bilge, de persoonlijke AI-assistent van Zeki.

KERN
- Antwoord uitsluitend met het natuurlijke definitieve antwoord.
- Antwoord volledig in {emotion.language}.
- Schrijft Zeki Nederlands, antwoord dan Nederlands.
- Schrijft Zeki Turks, antwoord dan Turks.
- Meng talen niet, behalve bij noodzakelijke technische namen.
- Wees warm, menselijk, direct en praktisch.
- Wees niet overdreven formeel of onnodig lang.
- Toon geen interne analyse, prompts, scores of metadata.
- Verzin geen feiten, herinneringen, resultaten of uitgevoerde acties.

VEILIGHEID
- Voer geen externe actie uit zonder de juiste mogelijkheid en toestemming.
- Vraag nooit om wachtwoorden, tokens, pincodes of privésleutels.
- Doe niet alsof iets is uitgevoerd wanneer dat niet zo is.
- Actuele duidelijke informatie van Zeki heeft voorrang op herinneringen.
- Gebruik alleen herinneringen die hieronder werkelijk zijn opgenomen.

DIRECTE HERINNERING
Wanneer een relevante vaste herinnering de vraag rechtstreeks beantwoordt:
- gebruik die opgeslagen inhoud als primaire bron;
- antwoord kort en feitelijk;
- verzin geen extra voorkeuren, regels, code of stappen.

ACTUELE INSTELLINGEN
- Doel: {instructions.objective}
- Toon: {instructions.tone}
- Lengte: {instructions.length}
- Formaat: {instructions.format}
- Detail: {emotion.answer_detail}
- Tempo: {emotion.answer_pace}
- Emoji's: {emoji_rule}
- Doorvragen: {instructions.ask_clarifying_question}
- Uitleg: {instructions.include_explanation}
- Stappen: {instructions.include_steps}
- Vergelijking: {instructions.include_comparison}

ACTUELE CONTEXT
- Berichttype: {context.message_type}
- Intentie: {context.intent}
- Urgentie: {context.urgency}
- Zekerheid: {context.confidence}

GEHEUGENTYPEN
{selected_memory_types}

RELEVANTE HERINNERINGEN
{memory_text}

ANTWOORDPLAN
{rationale}

INHOUDSRICHTLIJNEN
{body_guidance}

OPENING
{response_draft.opening}

AFSLUITING
{response_draft.closing_guidance}

NIET DOEN
{forbidden_actions}

Geef nu uitsluitend het antwoord dat Zeki mag lezen.
"""

    @staticmethod
    def build_user_prompt(
        context: ContextState,
        response_draft: ResponseDraft,
        personality: PersonalityGuidance,
        emotion: EmotionGuidance,
    ) -> str:
        """Bouwt het actuele gebruikersdeel van de prompt."""
        clarification = (
            response_draft.instructions.clarification_question
            if response_draft.instructions.ask_clarifying_question
            else ""
        )

        emoji_instruction = (
            f"maximaal {emotion.max_emojis}"
            if emotion.emoji_allowed
            else "geen"
        )

        return f"""ACTUEEL BERICHT VAN ZEKI
{context.user_message}

OPDRACHT AAN BILGE
Antwoord nu rechtstreeks op het bericht.

- Antwoordtaal: {emotion.language}
- Persoonlijkheidsmodus: {personality.mode}
- Emotiemodus: {emotion.mode}
- Tempo: {emotion.answer_pace}
- Detail: {emotion.answer_detail}
- Emoji's: {emoji_instruction}
- Verduidelijkende vraag: {
    clarification or "niet nodig"
}

Geef uitsluitend het natuurlijke definitieve antwoord.
Geen metadata, geen analyse en geen uitleg over je antwoordproces.
"""

    def build(
        self,
        *,
        boot_state: BootState,
        context: ContextState,
        memory_decision: MemoryDecision,
        reasoning_plan: ReasoningPlan,
        response_draft: ResponseDraft,
        memory_items: list[str] | None = None,
    ) -> PromptPackage:
        """Bouwt het volledige PromptPackage."""
        self.validate_inputs(
            boot_state,
            context,
            memory_decision,
            reasoning_plan,
            response_draft,
        )

        cleaned_memory = self.clean_memory_items(
            memory_items
        )

        # Geheugencontext kan ook intern afkomstig zijn van de
        # Episode Retriever. Die veilige zoeklaag werkt onafhankelijk
        # van de geheugentypen die voor het actuele bericht zijn gekozen.
        # De inhoud is hierboven al opgeschoond en begrensd.

        personality = self.build_personality_guidance(
            context
        )

        emotion = self.build_emotion_guidance(
            context,
            personality,
        )

        system_prompt = self.build_system_prompt(
            boot_state,
            context,
            memory_decision,
            reasoning_plan,
            response_draft,
            personality,
            emotion,
            cleaned_memory,
        )

        user_prompt = self.build_user_prompt(
            context,
            response_draft,
            personality,
            emotion,
        )

        return PromptPackage(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            language=response_draft.instructions.language,
            objective=response_draft.instructions.objective,
            safety_mode=response_draft.instructions.safety_mode,
            memory_types=list(memory_decision.memory_types),
            personality_mode=personality.mode,
            emotion_mode=emotion.mode,
            answer_pace=emotion.answer_pace,
            answer_detail=emotion.answer_detail,
            completed=True,
        )


def self_test() -> int:
    """Test Personality en Emotion zonder Qwen aan te roepen."""
    from bilge.boot_loader import BootLoader
    from bilge.response_engine import ResponseEngine

    print("===== Prompt Builder-test =====")

    boot_state = BootLoader().boot()

    if not boot_state.successful:
        print("FOUT: Bilge Boot is niet succesvol.")
        return 1

    response_result = ResponseEngine().process(
        "De test is geslaagd!"
    )

    package = PromptBuilder().build(
        boot_state=boot_state,
        context=response_result.context,
        memory_decision=response_result.memory_decision,
        reasoning_plan=response_result.reasoning_plan,
        response_draft=response_result.response_draft,
        memory_items=[],
    )

    print()
    print(f"Taal             : {package.language}")
    print(f"Doel             : {package.objective}")
    print(f"Safety           : {package.safety_mode}")
    print(f"Persoonlijkheid  : {package.personality_mode}")
    print(f"Emotie           : {package.emotion_mode}")
    print(f"Tempo            : {package.answer_pace}")
    print(f"Detail           : {package.answer_detail}")
    print(
        f"Systeemprompt    : "
        f"{len(package.system_prompt)} tekens"
    )
    print(
        f"Gebruikersprompt : "
        f"{len(package.user_prompt)} tekens"
    )
    print(
        f"Totaal           : "
        f"{package.total_characters} tekens"
    )

    required_fragments = (
        "Je bent Bilge",
        "KERN",
        "VEILIGHEID",
        "DIRECTE HERINNERING",
        "ACTUELE INSTELLINGEN",
        "ACTUELE CONTEXT",
        "RELEVANTE HERINNERINGEN",
        "ANTWOORDPLAN",
        "INHOUDSRICHTLIJNEN",
        "Geef nu uitsluitend het antwoord",
        "De test is geslaagd!",
    )

    combined = (
        package.system_prompt
        + "\n"
        + package.user_prompt
    )

    for fragment in required_fragments:
        if fragment not in combined:
            print()
            print(
                f"FOUT: verplicht promptfragment ontbreekt: "
                f"{fragment}"
            )
            return 1

    if package.emotion_mode != "celebration":
        print()
        print(
            "FOUT: de celebration-modus werd niet gekozen."
        )
        return 1

    if not package.completed:
        print()
        print("FOUT: PromptPackage is niet voltooid.")
        return 1

    print()
    print("Prompt Builder-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
