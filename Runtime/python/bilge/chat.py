"""
Interactieve chatmodus voor Bilge.

Starten:
    bilge
    python3 -m bilge.chat

Commando's:
    /debug     Technische logregels aan of uit
    /help      Beschikbare commando's tonen
    exit       Chat afsluiten
"""

from __future__ import annotations

import contextlib
import io
import sys
from typing import Any, Callable, TypeVar

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

T = TypeVar("T")


def run_quietly(
    function: Callable[..., T],
    *args: Any,
    debug_enabled: bool = False,
    **kwargs: Any,
) -> T:
    """
    Voert een functie uit.

    In normale modus worden technische stdout-logregels verborgen.
    In debugmodus blijven alle logregels zichtbaar.
    """
    if debug_enabled:
        return function(*args, **kwargs)

    hidden_output = io.StringIO()

    with contextlib.redirect_stdout(hidden_output):
        return function(*args, **kwargs)


def extract_answer(result: Any) -> str:
    """Haalt het uiteindelijke antwoord veilig uit het resultaat."""
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
    """Toont de rustige startweergave."""
    print()
    print("=" * 48)
    print("                    BILGE")
    print("=" * 48)
    print("Je kunt nu normaal met Bilge praten.")
    print("Typ /help voor commando's.")
    print("=" * 48)
    print()


def print_help() -> None:
    """Toont de beschikbare chatcommando's."""
    print()
    print("Beschikbare commando's:")
    print("  /debug   Technische logregels aan of uit")
    print("  /help    Deze uitleg tonen")
    print("  exit     Chat afsluiten")
    print()


def run_chat() -> int:
    """Start en beheert de interactieve chat."""
    print_header()

    debug_enabled = False

    try:
        engine = run_quietly(
            ConversationEngine,
            debug_enabled=debug_enabled,
        )
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

        normalized_message = user_message.casefold()

        if normalized_message in EXIT_COMMANDS:
            print("Bilge: Tot de volgende keer, Zeki.")
            return 0

        if normalized_message == "/help":
            print_help()
            continue

        if normalized_message == "/debug":
            debug_enabled = not debug_enabled
            status = "aan" if debug_enabled else "uit"
            print()
            print(f"Bilge: Debugmodus staat nu {status}.")
            print()
            continue

        try:
            result = run_quietly(
                engine.process,
                user_message,
                debug_enabled=debug_enabled,
            )

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
            print("Typ /debug en probeer het opnieuw voor meer informatie.")
            print()


def main() -> None:
    """Commando-ingang voor python3 -m bilge.chat."""
    sys.exit(run_chat())


if __name__ == "__main__":
    main()
