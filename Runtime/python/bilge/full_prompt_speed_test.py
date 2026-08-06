"""
Meet de verwerkingstijd van Bilge's echte prompt rechtstreeks via Ollama.

De bestaande ConversationEngine en PromptBuilder worden niet aangepast.
"""

from __future__ import annotations

import contextlib
import io
import json
import time
import urllib.request
from typing import Any

from bilge.conversation_engine import ConversationEngine


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"


class PromptCaptured(BaseException):
    """Stopt de pipeline zodra het promptpakket is onderschept."""


captured_package: Any = None


def capture_chat(*args: Any, **kwargs: Any) -> Any:
    global captured_package

    if args:
        captured_package = args[0]

    raise PromptCaptured()


def ns_to_seconds(value: Any) -> float:
    try:
        return float(value) / 1_000_000_000
    except (TypeError, ValueError):
        return 0.0


def main() -> None:
    global captured_package

    with contextlib.redirect_stdout(io.StringIO()):
        engine = ConversationEngine()

    engine.model_client.chat = capture_chat

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            engine.process(
                "Zeg uitsluitend in één korte zin dat je klaar bent."
            )
    except PromptCaptured:
        pass

    if captured_package is None:
        raise RuntimeError("Het promptpakket kon niet worden onderschept.")

    system_prompt = captured_package.system_prompt
    user_prompt = captured_package.user_prompt

    combined_prompt = (
        system_prompt
        + "\n\n"
        + user_prompt
    )

    payload = {
        "model": "qwen2.5:7b-instruct",
        "prompt": combined_prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": 0.1,
            "num_predict": 20,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    print()
    print("=" * 58)
    print("       DIRECTE TEST MET BILGE'S ECHTE PROMPT")
    print("=" * 58)
    print(f"System prompt : {len(system_prompt):,} tekens")
    print(f"User prompt   : {len(user_prompt):,} tekens")
    print(f"Totaal        : {len(combined_prompt):,} tekens")
    print()
    print("Bezig met meten...")

    started = time.perf_counter()

    with urllib.request.urlopen(
        request,
        timeout=300,
    ) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    elapsed = time.perf_counter() - started

    print()
    print(f"Totale wachttijd   : {elapsed:.2f} seconden")
    print(
        "Model laden        : "
        f"{ns_to_seconds(result.get('load_duration')):.2f} seconden"
    )
    print(
        "Prompt verwerken   : "
        f"{ns_to_seconds(result.get('prompt_eval_duration')):.2f} seconden"
    )
    print(
        "Antwoord genereren : "
        f"{ns_to_seconds(result.get('eval_duration')):.2f} seconden"
    )
    print(
        "Prompttokens       : "
        f"{result.get('prompt_eval_count', 0)}"
    )
    print(
        "Antwoord           : "
        f"{str(result.get('response', '')).strip()}"
    )
    print()
    print("=" * 58)
    print("Meting voltooid.")
    print("=" * 58)


if __name__ == "__main__":
    main()
