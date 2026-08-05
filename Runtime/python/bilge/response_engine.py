#!/usr/bin/env python3
"""
Bilge OS - Response Engine

Centrale coördinator van de antwoordvoorbereiding.

De Response Engine:
- ontvangt één gebruikersbericht;
- bouwt een ContextState;
- laat de Memory Manager relevante geheugentypen kiezen;
- laat de Reasoning Engine een antwoordstrategie bepalen;
- laat de Response Formatter een ResponseDraft opbouwen;
- verzamelt alle tussenresultaten in één PipelineResult.

Deze versie:
- genereert nog geen definitief AI-antwoord;
- roept Qwen nog niet aan;
- schrijft niets naar Long Memory of Project Memory;
- voert geen externe acties uit;
- doet niets met betalingen, e-mail, agenda of andere apps.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from bilge.context_builder import (
    ContextBuilder,
    ContextBuilderError,
)
from bilge.memory_manager import (
    MemoryDecision,
    MemoryManager,
    MemoryManagerError,
)
from bilge.models import ContextState
from bilge.reasoning_engine import (
    InvalidReasoningInputError,
    ReasoningEngine,
    ReasoningEngineError,
    ReasoningPlan,
)
from bilge.response_formatter import (
    InvalidResponseInputError,
    ResponseFormatter,
    ResponseFormatterError,
)
from bilge.response_types import ResponseDraft


class ResponseEngineError(Exception):
    """Basisfout voor problemen binnen de Response Engine."""


class ResponsePipelineError(ResponseEngineError):
    """Een stap binnen de antwoordpipeline is mislukt."""


@dataclass(slots=True)
class ResponsePipelineResult:
    """
    Volledig resultaat van de antwoordvoorbereiding.

    Dit object bevat nog geen definitief antwoord van een AI-model.
    """

    context: ContextState
    memory_decision: MemoryDecision
    reasoning_plan: ReasoningPlan
    response_draft: ResponseDraft
    started_at: datetime
    completed_at: datetime
    completed: bool = False

    @property
    def language(self) -> str:
        """Geeft de gekozen antwoordtaal terug."""
        return self.response_draft.instructions.language

    @property
    def objective(self) -> str:
        """Geeft het hoofddoel van het antwoord terug."""
        return self.response_draft.instructions.objective

    @property
    def safety_mode(self) -> str:
        """Geeft de gekozen Safety-modus terug."""
        return self.response_draft.instructions.safety_mode

    @property
    def memory_types(self) -> list[str]:
        """Geeft de geselecteerde geheugentypen terug."""
        return list(self.memory_decision.memory_types)


class ResponseEngine:
    """
    Coördineert de volledige voorbereiding van één antwoord.

    Elke onderliggende module behoudt haar eigen verantwoordelijkheid:

    ContextBuilder:
        Begrijpt het gebruikersbericht.

    MemoryManager:
        Bepaalt welke geheugentypen relevant zijn.

    ReasoningEngine:
        Bepaalt de antwoordstrategie.

    ResponseFormatter:
        Zet de strategie om in concrete schrijfinstructies.
    """

    def __init__(
        self,
        *,
        context_builder: ContextBuilder | None = None,
        memory_manager: MemoryManager | None = None,
        reasoning_engine: ReasoningEngine | None = None,
        response_formatter: ResponseFormatter | None = None,
    ) -> None:
        self.context_builder = (
            context_builder or ContextBuilder()
        )
        self.memory_manager = (
            memory_manager or MemoryManager()
        )
        self.reasoning_engine = (
            reasoning_engine or ReasoningEngine()
        )
        self.response_formatter = (
            response_formatter or ResponseFormatter()
        )

        self.last_result: ResponsePipelineResult | None = None

    def build_context(
        self,
        user_message: str,
    ) -> ContextState:
        """Bouwt en valideert de ContextState."""
        try:
            context = self.context_builder.build(user_message)
        except ContextBuilderError as exc:
            raise ResponsePipelineError(
                f"Contextanalyse mislukt: {exc}"
            ) from exc

        if not context.context_completed:
            raise ResponsePipelineError(
                "De Context Builder heeft de analyse niet voltooid."
            )

        if not context.successful:
            raise ResponsePipelineError(
                "De ContextState bevat fouten."
            )

        return context

    def decide_memory(
        self,
        context: ContextState,
    ) -> MemoryDecision:
        """Bepaalt welke geheugentypen relevant zijn."""
        try:
            return self.memory_manager.decide(context)
        except MemoryManagerError as exc:
            raise ResponsePipelineError(
                f"Geheugenkeuze mislukt: {exc}"
            ) from exc

    def build_reasoning_plan(
        self,
        context: ContextState,
        memory_decision: MemoryDecision,
    ) -> ReasoningPlan:
        """Bouwt en valideert het antwoordplan."""
        try:
            plan = self.reasoning_engine.build(
                context,
                memory_decision,
            )
        except (
            InvalidReasoningInputError,
            ReasoningEngineError,
        ) as exc:
            raise ResponsePipelineError(
                f"Antwoordstrategie mislukt: {exc}"
            ) from exc

        if not plan.completed:
            raise ResponsePipelineError(
                "De Reasoning Engine heeft het antwoordplan "
                "niet voltooid."
            )

        if not plan.answer_allowed:
            raise ResponsePipelineError(
                "De Reasoning Engine staat geen antwoord toe."
            )

        return plan

    def build_response_draft(
        self,
        context: ContextState,
        reasoning_plan: ReasoningPlan,
    ) -> ResponseDraft:
        """Bouwt en valideert de ResponseDraft."""
        try:
            draft = self.response_formatter.format(
                context,
                reasoning_plan,
            )
        except (
            InvalidResponseInputError,
            ResponseFormatterError,
        ) as exc:
            raise ResponsePipelineError(
                f"Antwoordopbouw mislukt: {exc}"
            ) from exc

        if not draft.completed:
            raise ResponsePipelineError(
                "De Response Formatter heeft de draft "
                "niet voltooid."
            )

        if not draft.instructions.completed:
            raise ResponsePipelineError(
                "De ResponseInstructions zijn niet voltooid."
            )

        return draft

    def process(
        self,
        user_message: str,
    ) -> ResponsePipelineResult:
        """
        Doorloopt de volledige antwoordvoorbereiding.

        Volgorde:
        1. Context
        2. Memory Decision
        3. Reasoning Plan
        4. Response Draft
        """
        started_at = datetime.now(UTC)

        context = self.build_context(user_message)

        memory_decision = self.decide_memory(context)

        reasoning_plan = self.build_reasoning_plan(
            context,
            memory_decision,
        )

        response_draft = self.build_response_draft(
            context,
            reasoning_plan,
        )

        result = ResponsePipelineResult(
            context=context,
            memory_decision=memory_decision,
            reasoning_plan=reasoning_plan,
            response_draft=response_draft,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            completed=True,
        )

        self.last_result = result
        return result

    def status(self) -> dict[str, object]:
        """Geeft een compact overzicht van het laatste resultaat."""
        if self.last_result is None:
            return {
                "completed": False,
                "message_processed": False,
                "language": "",
                "objective": "",
                "safety_mode": "",
                "memory_types": [],
            }

        return {
            "completed": self.last_result.completed,
            "message_processed": True,
            "language": self.last_result.language,
            "objective": self.last_result.objective,
            "safety_mode": self.last_result.safety_mode,
            "memory_types": self.last_result.memory_types,
        }


def print_result(
    result: ResponsePipelineResult,
) -> None:
    """Toont het pipeline-resultaat overzichtelijk."""
    instructions = result.response_draft.instructions

    print()
    print("===== Response Pipeline-resultaat =====")
    print()
    print(f"Bericht       : {result.context.user_message}")
    print(f"Taal          : {result.context.language}")
    print(f"Berichttype   : {result.context.message_type}")
    print(f"Intentie      : {result.context.intent}")
    print(f"Urgentie      : {result.context.urgency}")
    print(
        "Geheugen      : "
        + (
            " -> ".join(result.memory_types)
            if result.memory_types
            else "none"
        )
    )
    print(f"Doel          : {result.objective}")
    print(f"Stijl         : {result.reasoning_plan.response_style}")
    print(f"Toon          : {instructions.tone}")
    print(f"Lengte        : {instructions.length}")
    print(f"Formaat       : {instructions.format}")
    print(f"Safety        : {result.safety_mode}")
    print(
        f"Doorvragen    : "
        f"{instructions.ask_clarifying_question}"
    )
    print(f"Pipeline klaar: {result.completed}")

    print()
    print("Opening:")
    print(result.response_draft.opening)

    print()
    print("Aantal inhoudsrichtlijnen:")
    print(len(result.response_draft.body_guidance))

    print()
    print("Afsluiting:")
    print(result.response_draft.closing_guidance)


def self_test() -> int:
    """Test de complete Response Pipeline zonder AI-model."""
    engine = ResponseEngine()

    tests = [
        {
            "message": "Help me een planning maken.",
            "language": "nl",
            "objective": "create_plan",
            "format": "steps",
            "safety": "normal",
        },
        {
            "message": "Nasılsın Bilge?",
            "language": "tr",
            "objective": "provide_information",
            "format": "paragraphs",
            "safety": "normal",
        },
        {
            "message": "Ga verder met Bilge Runtime.",
            "language": "nl",
            "objective": "acknowledge_and_respond",
            "format": "paragraphs",
            "safety": "normal",
        },
        {
            "message": (
                "Betaal deze factuur via mijn bankrekening."
            ),
            "language": "nl",
            "objective": "prepare_requested_work",
            "format": "paragraphs",
            "safety": "restricted",
        },
    ]

    print("===== Response Engine-test =====")

    for test in tests:
        try:
            result = engine.process(test["message"])
        except ResponseEngineError as exc:
            print()
            print(f"FOUT: pipeline mislukt: {exc}")
            return 1

        print_result(result)

        instructions = result.response_draft.instructions

        if result.language != test["language"]:
            print()
            print(
                f"FOUT: verwacht taal '{test['language']}', "
                f"maar kreeg '{result.language}'."
            )
            return 1

        if result.objective != test["objective"]:
            print()
            print(
                f"FOUT: verwacht doel '{test['objective']}', "
                f"maar kreeg '{result.objective}'."
            )
            return 1

        if instructions.format != test["format"]:
            print()
            print(
                f"FOUT: verwacht formaat '{test['format']}', "
                f"maar kreeg '{instructions.format}'."
            )
            return 1

        if result.safety_mode != test["safety"]:
            print()
            print(
                f"FOUT: verwacht Safety '{test['safety']}', "
                f"maar kreeg '{result.safety_mode}'."
            )
            return 1

        if not result.completed:
            print()
            print("FOUT: pipeline werd niet voltooid.")
            return 1

    try:
        engine.process("   ")
    except ResponsePipelineError:
        print()
        print("Leeg bericht correct geweigerd.")
    else:
        print()
        print("FOUT: leeg bericht werd toegestaan.")
        return 1

    status = engine.status()

    if not status["completed"]:
        print()
        print("FOUT: Response Engine-status is niet voltooid.")
        return 1

    print()
    print("Response Engine-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
