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
9. Betekenisvolle gespreksrondes selecteren voor Episodic Memory.

Deze versie:
- gebruikt uitsluitend de lokale Ollama-server;
- gebruikt Short Memory binnen de actieve sessie;
- verwerkt expliciete geheugenopdrachten;
- bewaart betekenisvolle gesprekken in Episodic Memory;
- slaat triviale gesprekken niet permanent op;
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
from bilge.episode_pipeline import (
    EpisodePipeline,
    EpisodePipelineError,
    EpisodePipelineResult,
)
from bilge.episode_retriever import (
    EpisodeRetrievalResult,
    EpisodeRetriever,
    EpisodeRetrieverError,
)
from bilge.long_memory_retriever import (
    LongMemoryRetrievalResult,
    LongMemoryRetriever,
    LongMemoryRetrieverError,
)
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
    long_memory_retrieval_result: LongMemoryRetrievalResult | None
    episode_retrieval_result: EpisodeRetrievalResult | None
    episode_pipeline_result: EpisodePipelineResult | None
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
        """Geeft de gebruikte antwoordtaal terug."""
        return self.context.language

    @property
    def model(self) -> str:
        """Geeft het gebruikte model terug."""
        return self.model_response.model

    @property
    def memory_types(self) -> list[str]:
        """Geeft de gekozen geheugentypen terug."""
        return list(self.memory_decision.memory_types)

    @property
    def permanent_memory_stored(self) -> bool:
        """Geeft terug of expliciete Long Memory is opgeslagen."""
        return self.memory_pipeline_result.stored

    @property
    def memory_action(self) -> str:
        """Geeft de expliciete geheugenactie terug."""
        return self.memory_pipeline_result.plan.action

    @property
    def answer_was_cleaned(self) -> bool:
        """Geeft terug of het modelantwoord is aangepast."""
        return self.clean_answer_result.changed

    @property
    def retrieved_long_memory_count(self) -> int:
        """Geeft het aantal opgehaalde vaste herinneringen terug."""
        if self.long_memory_retrieval_result is None:
            return 0

        return self.long_memory_retrieval_result.count

    @property
    def long_memory_context_found(self) -> bool:
        """Geeft terug of relevante vaste herinneringen zijn gevonden."""
        return bool(
            self.long_memory_retrieval_result
            and self.long_memory_retrieval_result.found
        )

    @property
    def retrieved_episode_count(self) -> int:
        """Geeft het aantal opgehaalde eerdere episodes terug."""
        if self.episode_retrieval_result is None:
            return 0

        return self.episode_retrieval_result.count

    @property
    def episodic_context_found(self) -> bool:
        """Geeft terug of relevante eerdere episodes zijn gevonden."""
        return bool(
            self.episode_retrieval_result
            and self.episode_retrieval_result.found
        )

    @property
    def episode_stored(self) -> bool:
        """Geeft terug of deze gespreksronde episodisch is opgeslagen."""
        return bool(
            self.episode_pipeline_result
            and self.episode_pipeline_result.stored
        )

    @property
    def episode_decision(self) -> str:
        """Geeft de episodische selectiebeslissing terug."""
        if self.episode_pipeline_result is None:
            return "unavailable"

        return self.episode_pipeline_result.decision

    @property
    def episode_duplicate(self) -> bool:
        """Geeft terug of de episode al bestond."""
        return bool(
            self.episode_pipeline_result
            and self.episode_pipeline_result.duplicate
        )


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
        long_memory_retriever: LongMemoryRetriever | None = None,
        episode_pipeline: EpisodePipeline | None = None,
        episode_retriever: EpisodeRetriever | None = None,
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

        self.long_memory_retriever = (
            long_memory_retriever
            or LongMemoryRetriever(
                long_memory=self.memory_pipeline.long_memory
            )
        )

        self.episode_pipeline = (
            episode_pipeline or EpisodePipeline()
        )

        self.episode_retriever = (
            episode_retriever
            or EpisodeRetriever(
                episodic_memory=(
                    self.episode_pipeline.episodic_memory
                )
            )
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

    def retrieve_long_memories(
        self,
        user_message: str,
    ) -> LongMemoryRetrievalResult | None:
        """
        Haalt relevante vaste voorkeuren, doelen en werkwijzen op.

        Een zoekfout mag het gewone gesprek nooit blokkeren.
        """
        try:
            result = self.long_memory_retriever.retrieve(
                user_message,
                limit=4,
            )
        except LongMemoryRetrieverError as exc:
            print(
                "[LONG MEMORY] Vaste herinneringen konden niet "
                f"worden opgehaald: {exc}"
            )
            return None

        if not result.searched:
            print(
                "[LONG MEMORY] Geen zoekactie nodig voor "
                "dit korte of triviale bericht."
            )
        elif result.found:
            print(
                "[LONG MEMORY] Relevante vaste herinneringen "
                f"gevonden: {result.count}."
            )
        else:
            print(
                "[LONG MEMORY] Geen relevante vaste "
                "herinneringen gevonden."
            )

        return result

    def retrieve_episodes(
        self,
        user_message: str,
        language: str,
    ) -> EpisodeRetrievalResult | None:
        """
        Haalt relevante eerdere episodes op.

        Een zoekfout mag het gewone gesprek nooit blokkeren.
        """
        try:
            result = self.episode_retriever.retrieve(
                user_message,
                language=language,
                limit=3,
                register_access=True,
            )
        except EpisodeRetrieverError as exc:
            print(
                "[EPISODE] Eerdere episodes konden niet "
                f"worden opgehaald: {exc}"
            )
            return None

        if not result.searched:
            print(
                "[EPISODE] Geen zoekactie nodig voor "
                "dit korte of triviale bericht."
            )
        elif result.found:
            print(
                "[EPISODE] Relevante eerdere episodes "
                f"gevonden: {result.count}."
            )
        else:
            print(
                "[EPISODE] Geen relevante eerdere "
                "episodes gevonden."
            )

        return result

    @staticmethod
    def build_memory_context(
        recent_items: list[str],
        long_memory_result: LongMemoryRetrievalResult | None,
        episode_result: EpisodeRetrievalResult | None,
    ) -> list[str]:
        """
        Bouwt drie duidelijk gescheiden geheugensecties.

        Volgorde:
        1. recente gesprekscontext;
        2. vaste voorkeuren, doelen en werkwijzen;
        3. eerdere relevante ervaringen.
        """
        combined: list[str] = []

        if recent_items:
            combined.append(
                "RECENTE GESPREKSCONTEXT"
            )
            combined.extend(recent_items)

        if (
            long_memory_result is not None
            and long_memory_result.found
            and long_memory_result.context_items
        ):
            combined.append(
                "VASTE VOORKEUREN, DOELEN EN WERKWIJZEN"
            )
            combined.extend(
                long_memory_result.context_items
            )

        if (
            episode_result is not None
            and episode_result.found
            and episode_result.context_items
        ):
            combined.append(
                "EERDERE RELEVANTE ERVARINGEN"
            )
            combined.extend(
                episode_result.context_items
            )

        return combined

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

    def process_episode(
        self,
        user_message: str,
        assistant_message: str,
        language: str,
    ) -> EpisodePipelineResult | None:
        """
        Selecteert en bewaart een betekenisvolle gespreksronde.

        Een fout binnen Episodic Memory blokkeert het gewone gesprek niet.
        Bilge kan dus blijven antwoorden wanneer episodische opslag faalt.
        """
        try:
            result = self.episode_pipeline.process(
                user_message=user_message,
                assistant_message=assistant_message,
                language=language,
                source="conversation_engine",
            )
        except EpisodePipelineError as exc:
            print(
                "[EPISODE] Episodische verwerking overgeslagen: "
                f"{exc}"
            )
            return None

        if result.stored and result.duplicate:
            print(
                "[EPISODE] Bestaande episode herkend; "
                "niet dubbel opgeslagen."
            )
        elif result.stored:
            print("[EPISODE] Betekenisvolle episode opgeslagen.")
        elif result.decision == "reject_sensitive":
            print(
                "[EPISODE] Gevoelige gespreksinhoud "
                "niet opgeslagen."
            )
        else:
            print("[EPISODE] Gespreksronde niet blijvend bewaard.")

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

    @staticmethod
    def direct_long_memory_answer(
        user_message: str,
        language: str,
        retrieval_result: LongMemoryRetrievalResult | None,
    ) -> str:
        """
        Beantwoordt alleen directe vragen over een opgeslagen voorkeur.

        Andere vragen blijven volledig via het taalmodel lopen.
        """
        if (
            retrieval_result is None
            or not retrieval_result.found
            or not retrieval_result.memories
        ):
            return ""

        message = " ".join(
            user_message.casefold().strip().split()
        )

        direct_preference_question = any(
            signal in message
            for signal in (
                "hoe wil ik dat je",
                "hoe wil ik ",
                "wat is mijn voorkeur",
                "wat wil ik dat je",
                "nasıl istiyorum",
                "tercihim nedir",
            )
        )

        if not direct_preference_question:
            return ""

        preference = next(
            (
                item
                for item in retrieval_result.memories
                if item.category == "preference"
            ),
            None,
        )

        if preference is None:
            return ""

        content = preference.content.strip()

        if language == "tr":
            if content.casefold().startswith("zeki wil "):
                content = content[9:]

            return f"Sen {content}"

        if content.casefold().startswith("zeki wil "):
            content = content[9:]

        if not content:
            return ""

        return f"Je wilt {content}"

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

        long_memory_retrieval_result = (
            self.retrieve_long_memories(
                user_message=pipeline.context.user_message,
            )
        )

        if (
            long_memory_retrieval_result is not None
            and long_memory_retrieval_result.found
            and long_memory_retrieval_result.context_items
        ):
            episode_retrieval_result = None
            print(
                "[MEMORY PRIORITY] Relevante vaste herinnering "
                "heeft voorrang; episodische context overgeslagen."
            )
        else:
            episode_retrieval_result = self.retrieve_episodes(
                user_message=pipeline.context.user_message,
                language=pipeline.context.language,
            )

        memory_items = self.selected_memory_items(
            pipeline
        )

        memory_items = self.build_memory_context(
            recent_items=memory_items,
            long_memory_result=long_memory_retrieval_result,
            episode_result=episode_retrieval_result,
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

        direct_memory_answer = self.direct_long_memory_answer(
            user_message=pipeline.context.user_message,
            language=pipeline.context.language,
            retrieval_result=long_memory_retrieval_result,
        )

        answer_source = (
            direct_memory_answer
            if direct_memory_answer
            else clean_result.cleaned
        )

        if direct_memory_answer:
            print(
                "[MEMORY ANSWER] Direct antwoord uit een "
                "vaste voorkeur gebruikt."
            )

        final_answer = self.build_final_answer(
            answer_source,
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

        episode_result = self.process_episode(
            user_message=pipeline.context.user_message,
            assistant_message=final_answer,
            language=pipeline.context.language,
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
            long_memory_retrieval_result=(
                long_memory_retrieval_result
            ),
            episode_retrieval_result=episode_retrieval_result,
            episode_pipeline_result=episode_result,
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
            "episodic_memory_episodes": (
                self.episode_pipeline
                .episodic_memory
                .episode_count()
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
            "last_long_memory_retrieval_completed": bool(
                self.last_result
                and self.last_result.long_memory_retrieval_result
                and self.last_result
                .long_memory_retrieval_result
                .completed
            ),
            "last_long_memory_context_found": bool(
                self.last_result
                and self.last_result.long_memory_context_found
            ),
            "last_retrieved_long_memory_count": (
                self.last_result.retrieved_long_memory_count
                if self.last_result
                else 0
            ),
            "last_episode_retrieval_completed": bool(
                self.last_result
                and self.last_result.episode_retrieval_result
                and self.last_result
                .episode_retrieval_result
                .completed
            ),
            "last_episodic_context_found": bool(
                self.last_result
                and self.last_result.episodic_context_found
            ),
            "last_retrieved_episode_count": (
                self.last_result.retrieved_episode_count
                if self.last_result
                else 0
            ),
            "last_episode_decision": (
                self.last_result.episode_decision
                if self.last_result
                else "none"
            ),
            "last_episode_stored": bool(
                self.last_result
                and self.last_result.episode_stored
            ),
            "last_episode_duplicate": bool(
                self.last_result
                and self.last_result.episode_duplicate
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
    print(f"Taal                 : {result.language}")
    print(f"Model                : {result.model}")
    print(f"Geheugenactie        : {result.memory_action}")
    print(
        f"Long Memory bewaard  : "
        f"{result.permanent_memory_stored}"
    )
    print(
        f"Vaste herinneringen  : "
        f"{result.retrieved_long_memory_count}"
    )
    print(
        f"Long Memory-context  : "
        f"{result.long_memory_context_found}"
    )
    print(
        f"Episodes opgehaald   : "
        f"{result.retrieved_episode_count}"
    )
    print(
        f"Episodische context  : "
        f"{result.episodic_context_found}"
    )
    print(
        f"Episodebeslissing    : "
        f"{result.episode_decision}"
    )
    print(
        f"Episode bewaard      : "
        f"{result.episode_stored}"
    )
    print(
        f"Episode dubbel       : "
        f"{result.episode_duplicate}"
    )
    print(
        f"Antwoord opgeschoond : "
        f"{result.answer_was_cleaned}"
    )
    print(
        f"Prompttokens         : "
        f"{result.model_response.prompt_tokens}"
    )
    print(
        f"Antwoordtokens       : "
        f"{result.model_response.response_tokens}"
    )
    print(
        f"Duur                 : "
        f"{result.duration_seconds} seconden"
    )
    print(f"Voltooid             : {result.completed}")


def self_test() -> int:
    """Voert één echte end-to-end test uit."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from bilge.episode_selector import EpisodeSelector
    from bilge.episodic_memory import EpisodicMemory
    from bilge.long_memory import LongMemory

    print("===== Conversation Engine-test =====")

    with TemporaryDirectory() as temporary_directory:
        episode_storage = (
            Path(temporary_directory)
            / "episodic_memory_test.json"
        )

        long_memory_storage = (
            Path(temporary_directory)
            / "long_memory_test.json"
        )

        test_long_memory = LongMemory(
            long_memory_storage
        )

        test_long_memory.add_memory(
            "workflow",
            (
                "De Bilge-gespreksketen gebruikt relevante "
                "vaste herinneringen bij het antwoorden."
            ),
            context="Test van Long Memory Retrieval.",
        )

        test_memory_pipeline = MemoryPipeline(
            long_memory=test_long_memory
        )

        test_long_memory_retriever = LongMemoryRetriever(
            long_memory=test_long_memory
        )

        test_episodic_memory = EpisodicMemory(
            episode_storage
        )

        test_episodic_memory.add_episode(
            user_message=(
                "De Bilge-gespreksketen gebruikt "
                "episodische herinneringen."
            ),
            assistant_message=(
                "Eerdere relevante gesprekken kunnen vóór "
                "een nieuw antwoord worden opgehaald."
            ),
            summary=(
                "De Bilge-gespreksketen kan relevante "
                "episodische herinneringen ophalen."
            ),
            topic="bilge development",
            language="nl",
            keywords=[
                "bilge",
                "gespreksketen",
                "episodische herinneringen",
            ],
            importance=5,
        )

        test_episode_pipeline = EpisodePipeline(
            selector=EpisodeSelector(),
            episodic_memory=test_episodic_memory,
        )

        test_episode_retriever = EpisodeRetriever(
            episodic_memory=test_episodic_memory,
        )

        engine = ConversationEngine(
            model_client=OllamaModelClient(
                timeout_seconds=300,
                temperature=0.3,
                num_predict=120,
            ),
            memory_pipeline=test_memory_pipeline,
            long_memory_retriever=(
                test_long_memory_retriever
            ),
            episode_pipeline=test_episode_pipeline,
            episode_retriever=test_episode_retriever,
        )

        try:
            result = engine.process(
                "Zeg in maximaal één korte zin dat de Bilge-"
                "gespreksketen relevante vaste en episodische "
                "herinneringen gebruikt."
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
            print(
                "FOUT: zichtbare taalmetadata is niet verwijderd."
            )
            return 1

        if engine.short_memory.message_count() != 2:
            print(
                "FOUT: Short Memory bevat niet twee berichten."
            )
            return 1

        if result.long_memory_retrieval_result is None:
            print(
                "FOUT: Long Memory Retriever leverde "
                "geen resultaat."
            )
            return 1

        if not result.long_memory_retrieval_result.completed:
            print(
                "FOUT: Long Memory ophalen is niet voltooid."
            )
            return 1

        if not result.long_memory_retrieval_result.found:
            print(
                "FOUT: voorbereide vaste herinnering "
                "werd niet gevonden."
            )
            return 1

        if result.retrieved_long_memory_count < 1:
            print(
                "FOUT: geen vaste geheugencontext beschikbaar."
            )
            return 1

        if result.episode_retrieval_result is None:
            print(
                "FOUT: Episode Retriever leverde geen resultaat."
            )
            return 1

        if not result.episode_retrieval_result.completed:
            print(
                "FOUT: episodisch ophalen is niet voltooid."
            )
            return 1

        if not result.episode_retrieval_result.found:
            print(
                "FOUT: voorbereide testepisode werd niet gevonden."
            )
            return 1

        if result.retrieved_episode_count < 1:
            print(
                "FOUT: geen episodische context beschikbaar."
            )
            return 1

        if result.episode_pipeline_result is None:
            print(
                "FOUT: Episode Pipeline leverde geen resultaat."
            )
            return 1

        if not result.episode_pipeline_result.completed:
            print(
                "FOUT: episodische verwerking is niet voltooid."
            )
            return 1

        status = engine.status()

        if not status[
            "last_long_memory_retrieval_completed"
        ]:
            print(
                "FOUT: Long Memory Retrieval ontbreekt "
                "in status."
            )
            return 1

        if status["last_retrieved_long_memory_count"] < 1:
            print(
                "FOUT: status bevat geen opgehaalde "
                "vaste herinnering."
            )
            return 1

        if status["last_episode_decision"] == "none":
            print(
                "FOUT: episodebeslissing ontbreekt in status."
            )
            return 1

    print()
    print("Conversation Engine-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
