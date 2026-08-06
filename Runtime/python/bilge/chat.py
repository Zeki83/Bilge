"""
Interactieve chatmodus voor Bilge.

Starten:
    python3 -m bilge.chat

Afsluiten:
    exit
    quit
    stop
    afsluiten
"""

from __future__ import annotations

import sys
from typing import Any

from bilge.conversation_engine import ConversationEngine


EXIT_COMMANDS = {
    "exit",
    "quit",
    "stop",
    "afsluiten",
    "sluiten",
    "çıkış",
    "kapat",
}


def extract_answer(result: Any) -> str:
    """
    Haalt het uiteindelijke antwoord veilig uit ConversationResult.

    De huidige ConversationEngine gebruikt normaal result.answer.
    De extra controles voorkomen een crash als de resultaatstructuur
    later wordt uitgebreid of aangepast.
    """
    if result is None:
        return ""

    answer = getattr(result, "answer", None)

    if isinstance(answer, str):
        return answer.strip()

    final_answer = getattr(result, "final_answer", None)

    if isinstance(final_answer, str):
        return final_answer.strip()

    if isinstance(result, str):
        return result.strip()

    return str(result).strip()


def print_header() -> None:
    """Toont de begroeting wanneer Bilge wordt gestart."""
    print()
    print("=" * 56)
    print("                     BILGE")
    print("=" * 56)
    print("Je kunt nu normaal met Bilge praten.")
    print("Typ 'exit' om de chat af te sluiten.")
    print("=" * 56)
    print()


def run_chat() -> int:
    """Start en beheert de interactieve chat."""
    print_header()

    try:
        engine = ConversationEngine()
    except Exception as exc:
        print(f"[FOUT] Bilge kon niet worden gestart: {exc}")
        return 1

    while True:
        try:
            user_message = input("Jij: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("Bilge: Tot de volgende keer, Zeki.")
            return 0

        if not user_message:
            continue

        if user_message.casefold() in EXIT_COMMANDS:
            print("Bilge: Tot de volgende keer, Zeki.")
            return 0

        try:
            result = engine.process(user_message)
            answer = extract_answer(result)

            if not answer:
                answer = (
                    "Ik kon nu geen bruikbaar antwoord maken. "
                    "Probeer je vraag nog een keer."
                )

            print()
            print(f"Bilge: {answer}")
            print()

        except KeyboardInterrupt:
            print()
            print("Bilge: De huidige verwerking is gestopt.")
            print()

        except Exception as exc:
            print()
            print(f"[FOUT] Er ging iets mis tijdens het antwoorden: {exc}")
            print()


def main() -> None:
    """Commando-ingang voor: python3 -m bilge.chat"""
    exit_code = run_chat()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
