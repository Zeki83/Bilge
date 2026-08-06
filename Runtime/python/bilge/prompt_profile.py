"""
Onderzoekt de omvang van het promptpakket van Bilge.

De modelaanroep wordt onderschept:
- Qwen wordt niet aangeroepen;
- er wordt geen antwoord gegenereerd;
- persoonlijke tekst wordt niet afgedrukt;
- alleen veldnamen, typen en lengtes worden getoond.
"""

from __future__ import annotations

import contextlib
import io
from dataclasses import fields, is_dataclass
from typing import Any

from bilge.conversation_engine import ConversationEngine


class PromptCaptured(BaseException):
    """Stopt de pipeline zodra het promptpakket is onderschept."""


captured_package: Any = None


def capture_chat(*args: Any, **kwargs: Any) -> Any:
    """Onderschept het pakket vlak vóór de modelaanroep."""
    global captured_package

    if args:
        captured_package = args[0]
    elif kwargs:
        captured_package = kwargs

    raise PromptCaptured()


def safe_length(value: Any) -> int:
    """Geeft een veilige geschatte tekstlengte."""
    if isinstance(value, str):
        return len(value)

    try:
        return len(repr(value))
    except Exception:
        return 0


def describe(
    name: str,
    value: Any,
    indent: int = 0,
    depth: int = 0,
) -> None:
    """Toont structuur en lengtes zonder inhoud af te drukken."""
    prefix = " " * indent
    type_name = type(value).__name__

    if isinstance(value, str):
        print(
            f"{prefix}{name}: str — "
            f"{len(value):,} tekens"
        )
        return

    if value is None:
        print(f"{prefix}{name}: None")
        return

    if isinstance(value, (bool, int, float)):
        print(f"{prefix}{name}: {type_name}")
        return

    if depth >= 4:
        print(
            f"{prefix}{name}: {type_name} — "
            f"repr {safe_length(value):,} tekens"
        )
        return

    if is_dataclass(value):
        print(
            f"{prefix}{name}: {type_name} — dataclass, "
            f"repr {safe_length(value):,} tekens"
        )

        for field in fields(value):
            describe(
                field.name,
                getattr(value, field.name),
                indent + 2,
                depth + 1,
            )
        return

    if isinstance(value, dict):
        print(
            f"{prefix}{name}: dict — {len(value)} onderdelen, "
            f"repr {safe_length(value):,} tekens"
        )

        for key, item in value.items():
            describe(
                str(key),
                item,
                indent + 2,
                depth + 1,
            )
        return

    if isinstance(value, (list, tuple)):
        print(
            f"{prefix}{name}: {type_name} — {len(value)} onderdelen, "
            f"repr {safe_length(value):,} tekens"
        )

        for index, item in enumerate(value):
            describe(
                f"[{index}]",
                item,
                indent + 2,
                depth + 1,
            )
        return

    attributes = getattr(value, "__dict__", None)

    if isinstance(attributes, dict):
        print(
            f"{prefix}{name}: {type_name} — object, "
            f"repr {safe_length(value):,} tekens"
        )

        for key, item in attributes.items():
            describe(
                str(key),
                item,
                indent + 2,
                depth + 1,
            )
        return

    print(
        f"{prefix}{name}: {type_name} — "
        f"repr {safe_length(value):,} tekens"
    )


def main() -> None:
    global captured_package

    print()
    print("=" * 62)
    print("                 BILGE PROMPT-PROFIEL")
    print("=" * 62)

    with contextlib.redirect_stdout(io.StringIO()):
        engine = ConversationEngine()

    engine.model_client.chat = capture_chat

    question = "Zeg uitsluitend in één korte zin dat je klaar bent."

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            engine.process(question)
    except PromptCaptured:
        pass

    if captured_package is None:
        raise RuntimeError(
            "Het promptpakket kon niet worden onderschept."
        )

    print()
    print("TOTALE OMVANG")
    print("-" * 62)
    print(
        f"Type pakket          : "
        f"{type(captured_package).__name__}"
    )
    print(
        f"Geschatte repr-lengte: "
        f"{safe_length(captured_package):,} tekens"
    )

    print()
    print("ONDERDELEN")
    print("-" * 62)

    describe(
        "prompt_package",
        captured_package,
    )

    print()
    print("=" * 62)
    print("Prompt-profiel voltooid.")
    print("=" * 62)


if __name__ == "__main__":
    main()
