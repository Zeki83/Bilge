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
import re
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
            streamed_parts: list[str] = []
            visible_parts: list[str] = []
            stream_buffer = ""

            cjk_pattern = re.compile(
                r"[\u3400-\u4dbf\u4e00-\u9fff"
                r"\u3040-\u30ff\uac00-\ud7af]"
            )

            forbidden_english_phrases = (
                "thanks",
                "thank you",
                "you're welcome",
                "how can i help",
                "what can i do for you",
            )

            def normalize_for_comparison(value: str) -> str:
                """
                Normaliseert tekst voor vergelijking.

                Verschillen in markdown, witruimte en regelafbrekingen
                mogen niet leiden tot een dubbel definitief antwoord.
                """
                normalized = value.casefold()
                normalized = re.sub(r"[*_`#>-]+", " ", normalized)
                normalized = re.sub(r"\s+", " ", normalized)
                return normalized.strip()

            def is_safe_stream_text(value: str) -> bool:
                """
                Laat alleen bruikbare Nederlandse/Turkse modeltekst door.

                Chinese, Japanse en Koreaanse tekens worden verborgen.
                Bij een Nederlands antwoord worden ook bekende Engelse
                stopzinnen niet direct getoond.
                """
                stripped = value.strip()

                if not stripped:
                    return False

                if cjk_pattern.search(stripped) is not None:
                    return False

                lowered = stripped.casefold()

                if any(
                    phrase in lowered
                    for phrase in forbidden_english_phrases
                ):
                    return False

                return True

            def emit_safe_text(value: str) -> None:
                """Toont één gecontroleerd tekstdeel."""
                if not is_safe_stream_text(value):
                    return

                normalized = value.strip()

                if not normalized:
                    return

                current_visible = "".join(visible_parts)

                # Voorkom dat Qwen een reeds gegeven stuk opnieuw begint.
                if (
                    normalized in current_visible
                    or current_visible.endswith(normalized)
                ):
                    return

                if not visible_parts:
                    sys.__stdout__.write("\nBilge: ")
                elif (
                    not current_visible.endswith((" ", "\n"))
                    and not normalized.startswith(
                        (".", ",", "!", "?", ":", ";")
                    )
                ):
                    sys.__stdout__.write(" ")

                visible_parts.append(normalized)
                sys.__stdout__.write(normalized)
                sys.__stdout__.flush()

            def show_chunk(chunk: str) -> None:
                """
                Buffert ruwe modeltokens en toont alleen complete,
                gecontroleerde zinnen of regels.
                """
                nonlocal stream_buffer

                if not isinstance(chunk, str) or not chunk:
                    return

                streamed_parts.append(chunk)
                stream_buffer += chunk

                while True:
                    match = re.search(
                        r"(?<=[.!?])(?:\s+|$)|\n+",
                        stream_buffer,
                    )

                    if match is None:
                        break

                    end = match.end()
                    candidate = stream_buffer[:end]
                    stream_buffer = stream_buffer[end:]

                    emit_safe_text(candidate)

            callback = (
                None
                if debug_enabled
                else show_chunk
            )

            result = run_quietly(
                engine.process,
                user_message,
                stream_callback=callback,
                debug_enabled=debug_enabled,
            )

            answer = extract_answer(result)

            if not answer:
                answer = (
                    "Ik kon nu geen bruikbaar antwoord maken. "
                    "Probeer je vraag nog een keer."
                )

            if stream_buffer.strip():
                emit_safe_text(stream_buffer)

            streamed_text = " ".join(
                visible_parts
            ).strip()

            if visible_parts:
                normalized_streamed = normalize_for_comparison(
                    streamed_text
                )
                normalized_answer = normalize_for_comparison(
                    answer
                )

                same_answer = (
                    normalized_streamed == normalized_answer
                    or normalized_answer.startswith(
                        normalized_streamed
                    )
                    or normalized_streamed.startswith(
                        normalized_answer
                    )
                )

                if not same_answer:
                    # Toon een vervanging alleen wanneer het opgeschoonde
                    # antwoord inhoudelijk echt anders is.
                    sys.__stdout__.write(
                        "\n\nBilge (gecorrigeerd): "
                        + answer
                    )

                sys.__stdout__.write("\n\n")
                sys.__stdout__.flush()
            else:
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
