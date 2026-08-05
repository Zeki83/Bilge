#!/usr/bin/env python3
"""
Bilge OS - Interactieve Chat

Start een lokale chatsessie met Bilge via de volledige pipeline.

Commando's:
- /help   Toon beschikbare commando's
- /status Toon de huidige sessiestatus
- /clear  Wis alleen Short Memory
- /exit   Sluit Bilge af

Deze versie:
- gebruikt uitsluitend lokale Ollama;
- gebruikt Short Memory binnen de actieve sessie;
- schrijft nog niet automatisch naar Long Memory;
- koppelt geen externe apps;
- voert geen betalingen, e-mail- of agenda-acties uit.
"""

from __future__ import annotations

from bilge.conversation_engine import (
    ConversationEngine,
    ConversationEngineError,
)
from bilge.model_client import OllamaModelClient


class BilgeChat:
    """Eenvoudige interactieve terminalchat voor Bilge."""

    def __init__(self) -> None:
        self.engine = ConversationEngine(
            model_client=OllamaModelClient(
                timeout_seconds=300,
                temperature=0.5,
                num_predict=700,
            )
        )

    @staticmethod
    def print_welcome() -> None:
        print()
        print("=" * 64)
        print("BILGE")
        print("=" * 64)
        print()
        print("Bilge wordt lokaal gestart.")
        print("Typ /help voor de beschikbare commando's.")
        print()

    @staticmethod
    def print_help() -> None:
        print()
        print("Beschikbare commando's:")
        print("  /help    Toon deze uitleg")
        print("  /status  Toon de sessiestatus")
        print("  /clear   Wis alleen het tijdelijke gesprekgeheugen")
        print("  /exit    Sluit Bilge af")
        print()

    def print_status(self) -> None:
        status = self.engine.status()

        print()
        print("Sessie-status:")
        print(f"  Gestart              : {status['started']}")
        print(f"  Boot succesvol       : {status['boot_successful']}")
        print(
            "  Short Memory-berichten: "
            f"{status['short_memory_messages']}"
        )
        print(
            "  Laatste beurt voltooid: "
            f"{status['last_result_completed']}"
        )
        print(f"  Model                : {status['model']}")
        print()

    def handle_command(self, command: str) -> bool:
        """
        Verwerkt een chatcommando.

        Geeft True terug wanneer de chat moet doorgaan.
        """
        normalized = command.lower().strip()

        if normalized == "/help":
            self.print_help()
            return True

        if normalized == "/status":
            self.print_status()
            return True

        if normalized == "/clear":
            removed = self.engine.clear_session()

            print()
            print(
                f"Short Memory geleegd. "
                f"{removed} bericht(en) verwijderd."
            )
            print()
            return True

        if normalized in {"/exit", "/quit"}:
            print()
            print("Bilge wordt afgesloten. Tot snel, Zeki.")
            print()
            return False

        print()
        print(
            "Onbekend commando. Typ /help voor de mogelijkheden."
        )
        print()
        return True

    def run(self) -> int:
        """Start de interactieve chatsessie."""
        self.print_welcome()

        try:
            self.engine.start()
        except ConversationEngineError as exc:
            print()
            print(f"Bilge kon niet worden gestart: {exc}")
            return 1

        print()
        print("Bilge is gereed. Je kunt nu met haar praten.")
        print()

        while True:
            try:
                user_message = input("Jij: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                print()
                print("Bilge wordt afgesloten. Tot snel, Zeki.")
                return 0

            if not user_message:
                continue

            if user_message.startswith("/"):
                if not self.handle_command(user_message):
                    return 0

                continue

            print()
            print("Bilge denkt...")

            try:
                result = self.engine.process(user_message)
            except ConversationEngineError as exc:
                print()
                print(f"Bilge-fout: {exc}")
                print()
                continue

            print()
            print(f"Bilge: {result.answer}")
            print()


def self_test() -> int:
    """
    Lichte test zonder interactieve invoer of modelgeneratie.

    Controleert alleen of de chatklasse correct kan worden aangemaakt.
    """
    print("===== Bilge Chat-test =====")

    chat = BilgeChat()

    if chat.engine is None:
        print("FOUT: Conversation Engine ontbreekt.")
        return 1

    status = chat.engine.status()

    if status["started"]:
        print("FOUT: de engine hoort vóór run() nog niet gestart te zijn.")
        return 1

    print("Chatklasse correct aangemaakt.")
    print("Bilge Chat-test geslaagd.")
    return 0


def main() -> int:
    """Applicatie-entrypoint."""
    return BilgeChat().run()


if __name__ == "__main__":
    raise SystemExit(main())
