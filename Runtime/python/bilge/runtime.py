#!/usr/bin/env python3
"""
Bilge OS - Runtime

De Runtime coördineert de onderdelen van Bilge OS.

Deze versie:
- start Bilge via de Boot Loader;
- controleert of de essentiële onderdelen geladen zijn;
- verwerkt een gebruikersbericht via de Context Builder;
- bewaart BootState, ContextState en RuntimeState;
- gebruikt nog geen geheugen, AI-model of externe apps.
"""

from __future__ import annotations

from bilge.boot_loader import BootLoader
from bilge.context_builder import (
    ContextBuilder,
    ContextBuilderError,
)
from bilge.models import BootState, ContextState, RuntimeState


class BilgeRuntimeError(Exception):
    """Basisfout voor problemen binnen de Bilge Runtime."""


class BilgeBootError(BilgeRuntimeError):
    """Bilge kon niet veilig en volledig worden opgestart."""


class BilgeContextError(BilgeRuntimeError):
    """Het gebruikersbericht kon niet betrouwbaar worden verwerkt."""


class BilgeRuntime:
    """Centrale coördinator van Bilge OS."""

    def __init__(self) -> None:
        self.boot_loader = BootLoader()
        self.context_builder = ContextBuilder()
        self.state = RuntimeState()

    def start(self) -> BootState:
        """Start Bilge OS en bewaart de BootState."""
        print("\n===== Bilge Runtime =====\n")

        boot_state = self.boot_loader.boot()

        if not boot_state.boot_completed:
            self.state.completed = False
            self.state.errors.append(
                "Bilge kon niet volledig worden opgestart."
            )
            raise BilgeBootError(
                "De Runtime is gestopt omdat een essentieel "
                "onderdeel ontbreekt of niet betrouwbaar is geladen."
            )

        self.state.boot = boot_state

        print("\n[RUNTIME] Alle essentiële onderdelen zijn beschikbaar.")
        return boot_state

    def process_message(self, user_message: str) -> ContextState:
        """
        Verwerkt één gebruikersbericht via de Context Builder.

        De Runtime geeft nog geen AI-antwoord.
        """
        if self.state.boot is None or not self.state.boot.boot_completed:
            raise BilgeBootError(
                "Bilge moet eerst volledig worden opgestart."
            )

        print("\n[RUNTIME] Gebruikersbericht analyseren...")

        try:
            context_state = self.context_builder.build(user_message)
        except ContextBuilderError as exc:
            self.state.completed = False
            self.state.errors.append(str(exc))
            raise BilgeContextError(str(exc)) from exc

        self.state.context = context_state
        self.state.completed = (
            self.state.boot.successful
            and context_state.successful
        )

        print("[RUNTIME] Contextanalyse voltooid.")
        return context_state

    def status(self) -> dict[str, bool | int | str]:
        """Geeft een compact overzicht van de Runtime-status."""
        loaded_documents = 0
        language = ""
        intent = ""

        if self.state.boot is not None:
            loaded_documents = len(
                self.state.boot.loaded_documents
            )

        if self.state.context is not None:
            language = self.state.context.language
            intent = self.state.context.intent

        return {
            "runtime_completed": self.state.completed,
            "boot_completed": bool(
                self.state.boot
                and self.state.boot.boot_completed
            ),
            "context_completed": bool(
                self.state.context
                and self.state.context.context_completed
            ),
            "loaded_documents": loaded_documents,
            "language": language,
            "intent": intent,
        }


def self_test() -> int:
    """Voert een lokale Runtime-test uit."""
    runtime = BilgeRuntime()

    try:
        runtime.start()
        context = runtime.process_message(
            "Laten we verder gaan met Bilge."
        )
    except BilgeRuntimeError as exc:
        print(f"\n[RUNTIME-FOUT] {exc}")
        return 1

    status = runtime.status()

    print("\nContext-resultaat:")
    print(f"Bericht    : {context.user_message}")
    print(f"Taal       : {context.language}")
    print(f"Type       : {context.message_type}")
    print(f"Intentie   : {context.intent}")
    print(f"Urgentie   : {context.urgency}")
    print(f"Vervolg    : {context.probable_follow_up}")
    print(f"Zekerheid  : {context.confidence}")

    print("\nRuntime-status:")
    print(f"Runtime gereed    : {status['runtime_completed']}")
    print(f"Boot voltooid     : {status['boot_completed']}")
    print(f"Context voltooid  : {status['context_completed']}")
    print(f"Documenten geladen: {status['loaded_documents']}")
    print(f"Taal              : {status['language']}")
    print(f"Intentie          : {status['intent']}")

    if not status["runtime_completed"]:
        print("\nFOUT: Runtime werd niet succesvol afgerond.")
        return 1

    print("\nRuntime-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
