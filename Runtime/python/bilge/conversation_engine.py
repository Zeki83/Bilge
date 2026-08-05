#!/usr/bin/env python3
"""
Bilge OS - Conversation Engine

Centrale end-to-end gespreksketen van Bilge.

Volgorde:
1. Bilge veilig opstarten.
2. Gebruikersbericht analyseren.
3. Geheugenbehoefte bepalen.
4. Veilige Memory Pipeline uitvoeren.
5. Antwoordstrategie en prompt opbouwen.
6. Lokaal Qwen-model aanroepen.
7. Modelantwoord opschonen.
8. Gebruikersbericht en schoon antwoord tijdelijk bewaren.

Deze versie:
- gebruikt uitsluitend de lokale Ollama-server;
- gebruikt Short Memory binnen de actieve sessie;
- verwerkt expliciete geheugenopdrachten;
- slaat gewone gesprekken niet permanent op;
- schoont zichtbare modelmetadata en stijve formuleringen op;
- verwijdert nooit automatisch herinneringen;
- koppelt geen externe apps;
- voert geen betalingen, e-mail- of agenda-acties uit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter

from bilge.answer_cleaner import (
    AnswerCleaner,
    AnswerCleanerError,
    CleanAnswerResult,
)
from bilge.boot_loader import BootLoader
from bilge.memory_manager import MemoryDecision
from bilge.memory_pipeline import (
    MemoryPipeline,
    MemoryPipelineError,
    MemoryPipelineResult,
)
from bilge.model_client import (
    ModelClientError,
    ModelResponse,
    OllamaModelClient,
)
from bilge.models import BootState, ContextState
from bilge.prompt_builder import (
    PromptBuilder,
    PromptBuilderError,
    PromptPackage,
)
from bilge.reasoning_engine import ReasoningPlan
from bilge.response_engine import (
    ResponseEngine,
    ResponseEngineError,
    ResponsePipelineResult,
)
from bilge.response_types import ResponseDraft
from bilge.short_memory import (
    SensitiveInformationError,
    ShortMemory,
    ShortMemoryError,
)


class ConversationEngineError(Exception):
    """Basisfout voor problemen binnen de Conversation Engine."""


class ConversationBootError(ConversationEngineError):
    """Bilge kon niet veilig worden opgestart."""


class ConversationPipelineError(ConversationEngineError):
    """De gespreksketen kon niet volledig worden uitgevoerd."""


@dataclass(slots=True)
class ConversationResult:
    """Volledig resultaat van één gespreksturn."""

    user_message: str
    answer: str

    boot_state: BootState
    context: ContextState
    memory_decision: MemoryDecision
    memory_pipeline_result: MemoryPipelineResult
    reasoning_plan: ReasoningPlan
    response_draft: ResponseDraft
    prompt_package: PromptPackage
    model_response: ModelResponse
    clean_answer_result: CleanAnswerResult

    started_at: datetime
    completed_at: datetime
    duration_seconds: float

    user_message_stored: bool = False
    assistant_message_stored: bool = False
    completed: bool = False

    @property
    def language(self) -> str:
        return self.context.language

    @property
    def model(self) -> str:
        return self.model_response.model

    @property
    def memory_types(self) -> list[str]:
        return list(self.memory_decision.memory_types)

    @property
    def permanent_memory_stored(self) -> bool:
        return self.memory_pipeline_result.stored

    @property
    def memory_action(self) -> str:
        return self.memory_pipeline_result.plan.action

    @property
    def answer_was_cleaned(self) -> bool:
        return self.clean_answer_result.changed


class ConversationEngine:
    """Coördineert één volledige gespreksronde met Bilge."""

    def __init__(
        self,
        *,
        boot_loader: BootLoader | None = None,
        response_engine: ResponseEngine | None = None,
        prompt_builder: PromptBuilder | None = None,
        model_client: OllamaModelClient | None = None,
        short_memory: ShortMemory | None = None,
        memory_pipeline: MemoryPipeline | None = None,
        answer_cleaner: AnswerCleaner | None = None,
    ) -> None:
        self.boot_loader = boot_loader or BootLoader()
        self.response_engine = response_engine or ResponseEngine()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.model_client = model_client or OllamaModelClient()

        self.short_memory = short_memory or ShortMemory(
            max_messages=20
        )

        self.memory_pipeline = (
            memory_pipeline or MemoryPipeline()
        )

        self.answer_cleaner = (
            answer_cleaner or AnswerCleaner()
        )

        self.boot_state: BootState | None = None
        self.last_result: ConversationResult | None = None
        self.started = False

    def start(self) -> BootState:
        """Start Bilge één keer veilig op."""
        if (
            self.started
            and self.boot_state is not None
            and self.boot_state.successful
        ):
            return self.boot_state

        print("\n===== Bilge Conversation Engine =====\n")
        print("[CONVERSATION] Bilge opstarten...")

        boot_state = self.boot_loader.boot()

        if not boot_state.boot_completed:
            raise ConversationBootError(
                "De bootprocedure is niet voltooid."
            )

        if not boot_state.successful:
            raise ConversationBootError(
                "De BootState bevat fouten."
            )

        self.boot_state = boot_state
        self.started = True

        print("[CONVERSATION] Bilge is gereed.")
        return boot_state

    def ensure_started(self) -> BootState:
        """Garandeert dat een geldige BootState beschikbaar is."""
        if (
            not self.started
            or self.boot_state is None
            or not self.boot_state.successful
        ):
            return self.start()

        return self.boot_state

    def selected_memory_items(
        self,
        pipeline: ResponsePipelineResult,
    ) -> list[str]:
        """Selecteert relevante tijdelijke gesprekscontext."""
        if "short" not in pipeline.memory_decision.memory_types:
            return []

        memory_items: list[str] = []

        for message in self.short_memory.get_recent(limit=10):
            role_label = {
                "user": "Zeki",
                "assistant": "Bilge",
                "system": "Systeem",
            }.get(message.role, message.role)

            memory_items.append(
                f"{role_label}: {message.content}"
            )

        return memory_items

    def store_short_memory(
        self,
        role: str,
        content: str,
    ) -> bool:
        """Bewaart een bericht veilig in Short Memory."""
        try:
            self.short_memory.add_message(
                role,  # type: ignore[arg-type]
                content,
            )
        except SensitiveInformationError:
            print(
                "[MEMORY] Mogelijk geheime informatie is "
                "niet tijdelijk opgeslagen."
            )
            return False
        except ShortMemoryError as exc:
            print(
                "[MEMORY] Tijdelijke opslag mislukt: "
                f"{exc}"
            )
            return False

        return True

    def process_permanent_memory(
        self,
        context: ContextState,
    ) -> MemoryPipelineResult:
        """Voert de veilige blijvende geheugencontrole uit."""
        try:
            result = self.memory_pipeline.execute(context)
        except MemoryPipelineError as exc:
            raise ConversationPipelineError(
                f"Geheugenverwerking mislukt: {exc}"
            ) from exc

        if result.stored:
            print("[MEMORY] Herinnering opgeslagen.")
        elif result.plan.action == "forget_request":
            print(
                "[MEMORY] Vergeetverzoek herkend; "
                "er is niets verwijderd."
            )
        elif (
            result.plan.action == "store_long"
            and result.plan.explicit_request
            and not result.plan.allowed
        ):
            print("[MEMORY] Informatie niet opgeslagen.")

        return result

    def clean_model_answer(
        self,
        model_answer: str,
        user_message: str,
    ) -> CleanAnswerResult:
        """Schoont het modelantwoord op."""
        try:
            return self.answer_cleaner.clean(
                model_answer,
                user_message=user_message,
            )
        except AnswerCleanerError as exc:
            raise ConversationPipelineError(
                f"Antwoord opschonen mislukt: {exc}"
            ) from exc

    @staticmethod
    def memory_confirmation(
        language: str,
        result: MemoryPipelineResult,
    ) -> str:
        """Geeft alleen noodzakelijke geheugenfeedback."""
        plan = result.plan

        if result.stored:
            return "Hatırlandı." if language == "tr" else "Onthouden."

        if plan.action == "forget_request":
            if language == "tr":
                return (
                    "Henüz hiçbir şey silinmedi. "
                    "Silme işlemi önce onay gerektiriyor."
                )

            return (
                "Er is nog niets verwijderd. "
                "Verwijderen vereist eerst bevestiging."
            )

        if (
            plan.action == "store_long"
            and plan.explicit_request
            and not plan.allowed
        ):
            if language == "tr":
                return (
                    "Bu bilgi hassas veya eksik göründüğü "
                    "için kaydedilmedi."
                )

            return (
                "Dit is niet opgeslagen, omdat de informatie "
                "gevoelig of onvolledig lijkt."
            )

        return ""

    @classmethod
    def build_final_answer(
        cls,
        cleaned_answer: str,
        language: str,
        memory_result: MemoryPipelineResult,
    ) -> str:
        """Voegt alleen noodzakelijke geheugenfeedback toe."""
        answer = cleaned_answer.strip()
        confirmation = cls.memory_confirmation(
            language,
            memory_result,
        )

        if not confirmation:
            return answer

        normalized_answer = answer.casefold()
        normalized_confirmation = confirmation.casefold()

        if normalized_confirmation in normalized_answer:
            return answer

        return f"{answer}\n\n{confirmation}"

    def process(
        self,
        user_message: str,
    ) -> ConversationResult:
        """Voert één volledige end-to-end gespreksronde uit."""
        started_at = datetime.now(UTC)
        timer_start = perf_counter()

        boot_state = self.ensure_started()

        print("\n[CONVERSATION] Bericht verwerken...")

        try:
            pipeline = self.response_engine.process(
                user_message
            )
        except ResponseEngineError as exc:
            raise ConversationPipelineError(
                f"Antwoordvoorbereiding mislukt: {exc}"
            ) from exc

        memory_result = self.process_permanent_memory(
            pipeline.context
        )

        memory_items = self.selected_memory_items(
            pipeline
        )

        try:
            prompt_package = self.prompt_builder.build(
                boot_state=boot_state,
                context=pipeline.context,
                memory_decision=pipeline.memory_decision,
                reasoning_plan=pipeline.reasoning_plan,
                response_draft=pipeline.response_draft,
                memory_items=memory_items,
            )
        except PromptBuilderError as exc:
            raise ConversationPipelineError(
                f"Promptopbouw mislukt: {exc}"
            ) from exc

        print("[CONVERSATION] Lokaal model aanroepen...")

        try:
            model_response = self.model_client.chat(
                prompt_package
            )
        except ModelClientError as exc:
            raise ConversationPipelineError(
                f"Modelaanroep mislukt: {exc}"
            ) from exc

        clean_result = self.clean_model_answer(
            model_response.content,
            pipeline.context.user_message,
        )

        final_answer = self.build_final_answer(
            clean_result.cleaned,
            pipeline.context.language,
            memory_result,
        )

        user_stored = self.store_short_memory(
            "user",
            pipeline.context.user_message,
        )

        assistant_stored = self.store_short_memory(
            "assistant",
            final_answer,
        )

        completed_at = datetime.now(UTC)
        duration_seconds = perf_counter() - timer_start

        result = ConversationResult(
            user_message=pipeline.context.user_message,
            answer=final_answer,
            boot_state=boot_state,
            context=pipeline.context,
            memory_decision=pipeline.memory_decision,
            memory_pipeline_result=memory_result,
            reasoning_plan=pipeline.reasoning_plan,
            response_draft=pipeline.response_draft,
            prompt_package=prompt_package,
            model_response=model_response,
            clean_answer_result=clean_result,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=round(duration_seconds, 3),
            user_message_stored=user_stored,
            assistant_message_stored=assistant_stored,
            completed=True,
        )

        self.last_result = result

        print("[CONVERSATION] Antwoord ontvangen.")
        return result

    def status(self) -> dict[str, object]:
        """Geeft een compact overzicht van de huidige toestand."""
        return {
            "started": self.started,
            "boot_successful": bool(
                self.boot_state
                and self.boot_state.successful
            ),
            "short_memory_messages": (
                self.short_memory.message_count()
            ),
            "last_result_completed": bool(
                self.last_result
                and self.last_result.completed
            ),
            "last_memory_action": (
                self.last_result.memory_action
                if self.last_result
                else "none"
            ),
            "last_permanent_memory_stored": bool(
                self.last_result
                and self.last_result.permanent_memory_stored
            ),
            "last_answer_cleaned": bool(
                self.last_result
                and self.last_result.answer_was_cleaned
            ),
            "model": (
                self.last_result.model
                if self.last_result
                else self.model_client.model
            ),
        }

    def clear_session(self) -> int:
        """Leegt uitsluitend het tijdelijke gesprekgeheugen."""
        return self.short_memory.clear()


def print_result(result: ConversationResult) -> None:
    """Toont het resultaat overzichtelijk."""
    print()
    print("=" * 64)
    print("BILGE")
    print("=" * 64)
    print()
    print(result.answer)

    print()
    print("-" * 64)
    print(f"Taal              : {result.language}")
    print(f"Model             : {result.model}")
    print(f"Geheugenactie     : {result.memory_action}")
    print(
        f"Blijvend bewaard  : "
        f"{result.permanent_memory_stored}"
    )
    print(
        f"Antwoord opgeschoond: "
        f"{result.answer_was_cleaned}"
    )
    print(
        f"Prompttokens      : "
        f"{result.model_response.prompt_tokens}"
    )
    print(
        f"Antwoordtokens    : "
        f"{result.model_response.response_tokens}"
    )
    print(
        f"Duur              : "
        f"{result.duration_seconds} seconden"
    )
    print(f"Voltooid          : {result.completed}")


def self_test() -> int:
    """Voert één echte end-to-end test uit."""
    print("===== Conversation Engine-test =====")

    engine = ConversationEngine(
        model_client=OllamaModelClient(
            timeout_seconds=300,
            temperature=0.3,
            num_predict=120,
        ),
    )

    try:
        result = engine.process(
            "Zeg in maximaal één korte zin dat de opgeschoonde "
            "Bilge-gespreksketen werkt."
        )
    except ConversationEngineError as exc:
        print()
        print(f"FOUT: {exc}")
        return 1

    print_result(result)

    if not result.completed:
        print("FOUT: gesprek niet voltooid.")
        return 1

    if not result.answer.strip():
        print("FOUT: Bilge gaf geen antwoord.")
        return 1

    if result.answer.lower().startswith(("nl.", "tr.")):
        print("FOUT: zichtbare taalmetadata is niet verwijderd.")
        return 1

    if engine.short_memory.message_count() != 2:
        print("FOUT: Short Memory bevat niet twee berichten.")
        return 1

    print()
    print("Conversation Engine-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
