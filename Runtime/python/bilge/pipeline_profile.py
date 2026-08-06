"""
Meet welke onderdelen van Bilge tijd kosten.

Dit bestand verandert niets aan de bestaande Bilge-code.
"""

from __future__ import annotations

import contextlib
import io
import time
from typing import Any, Callable

from bilge.conversation_engine import ConversationEngine


def wrap_method(
    owner: Any,
    method_name: str,
    measurements: list[tuple[str, float]],
) -> None:
    """Meet een methode als deze op het object aanwezig is."""
    original = getattr(owner, method_name, None)

    if original is None or not callable(original):
        return

    def measured(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()

        try:
            return original(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - started
            measurements.append((method_name, elapsed))

    setattr(owner, method_name, measured)


def package_character_count(args: tuple[Any, ...]) -> int:
    """Schat de omvang van het pakket dat naar het model gaat."""
    if not args:
        return 0

    try:
        return len(repr(args[0]))
    except Exception:
        return 0


def main() -> None:
    measurements: list[tuple[str, float]] = []
    model_calls: list[tuple[float, int]] = []

    print()
    print("=" * 58)
    print("              BILGE PIPELINE-PROFIEL")
    print("=" * 58)

    with contextlib.redirect_stdout(io.StringIO()):
        engine = ConversationEngine()

    # Bekende onderdelen van ConversationEngine meten.
    for method_name in (
        "retrieve_long_memories",
        "retrieve_episodes",
        "selected_memory_items",
        "build_memory_context",
        "direct_long_memory_answer",
        "build_final_answer",
    ):
        wrap_method(
            engine,
            method_name,
            measurements,
        )

    # PromptBuilder meten.
    prompt_builder = getattr(engine, "prompt_builder", None)

    if prompt_builder is not None:
        wrap_method(
            prompt_builder,
            "build",
            measurements,
        )

    # Modelaanroep apart meten.
    model_client = getattr(engine, "model_client", None)

    if model_client is None:
        raise RuntimeError(
            "ConversationEngine heeft geen model_client."
        )

    original_chat: Callable[..., Any] = model_client.chat

    def measured_chat(*args: Any, **kwargs: Any) -> Any:
        characters = package_character_count(args)
        started = time.perf_counter()

        result = original_chat(*args, **kwargs)

        elapsed = time.perf_counter() - started
        model_calls.append((elapsed, characters))

        return result

    model_client.chat = measured_chat

    question = "Zeg uitsluitend in één korte zin dat je klaar bent."

    started = time.perf_counter()

    with contextlib.redirect_stdout(io.StringIO()):
        result = engine.process(question)

    total_time = time.perf_counter() - started
    answer = str(getattr(result, "answer", "")).strip()

    print()
    print("TOTAAL")
    print("-" * 58)
    print(f"Volledige verwerking : {total_time:.2f} seconden")
    print(f"Antwoord             : {answer}")

    print()
    print("GEMETEN ONDERDELEN")
    print("-" * 58)

    if measurements:
        for name, duration in measurements:
            print(f"{name:<28}: {duration:>8.2f} seconden")
    else:
        print("Geen losse onderdelen gemeten.")

    print()
    print("MODELAANROEPEN")
    print("-" * 58)
    print(f"Aantal modelaanroepen: {len(model_calls)}")

    for index, (duration, characters) in enumerate(
        model_calls,
        start=1,
    ):
        print(
            f"Aanroep {index:<3}          : "
            f"{duration:>8.2f} seconden"
        )
        print(
            f"Pakketgrootte {index:<2}     : "
            f"{characters} tekens"
        )

    measured_total = sum(
        duration
        for _, duration in measurements
    )
    model_total = sum(
        duration
        for duration, _ in model_calls
    )

    print()
    print("SAMENVATTING")
    print("-" * 58)
    print(f"Gemeten methodetijd  : {measured_total:.2f} seconden")
    print(f"Totale modeltijd     : {model_total:.2f} seconden")
    print(
        f"Overige verwerking   : "
        f"{max(0.0, total_time - model_total):.2f} seconden"
    )

    print()
    print("=" * 58)
    print("Profielmeting voltooid.")
    print("=" * 58)


if __name__ == "__main__":
    main()
