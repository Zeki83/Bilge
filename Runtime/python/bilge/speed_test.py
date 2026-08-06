"""
Snelheidsmeting voor Bilge.

Meet:
1. Het laden van de ConversationEngine.
2. Een directe koude/warmere Ollama-aanroep.
3. Een volledig antwoord via Bilge.
"""

from __future__ import annotations

import contextlib
import io
import json
import time
import urllib.error
import urllib.request
from typing import Any

from bilge.conversation_engine import ConversationEngine


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5:7b-instruct"


def seconds_from_nanoseconds(value: Any) -> float:
    """Zet een Ollama-duur in nanoseconden om naar seconden."""
    try:
        return float(value) / 1_000_000_000
    except (TypeError, ValueError):
        return 0.0


def direct_ollama_test(label: str) -> None:
    """Meet één korte directe aanvraag aan Ollama."""
    payload = {
        "model": MODEL_NAME,
        "prompt": (
            "Antwoord uitsluitend in één zeer korte Nederlandse zin: "
            "Ik ben klaar."
        ),
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

    started = time.perf_counter()

    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"{label}: FOUT bij Ollama: {exc}")
        return

    elapsed = time.perf_counter() - started

    load_time = seconds_from_nanoseconds(
        result.get("load_duration")
    )
    prompt_time = seconds_from_nanoseconds(
        result.get("prompt_eval_duration")
    )
    generation_time = seconds_from_nanoseconds(
        result.get("eval_duration")
    )
    token_count = result.get("eval_count", 0)
    answer = str(result.get("response", "")).strip()

    print()
    print(label)
    print("-" * 52)
    print(f"Totale wachttijd      : {elapsed:.2f} seconden")
    print(f"Model laden           : {load_time:.2f} seconden")
    print(f"Prompt verwerken      : {prompt_time:.2f} seconden")
    print(f"Antwoord genereren    : {generation_time:.2f} seconden")
    print(f"Gegenereerde tokens   : {token_count}")
    print(f"Antwoord              : {answer}")


def full_bilge_test(engine: ConversationEngine) -> None:
    """Meet één compleet antwoord via de Bilge-pipeline."""
    question = "Zeg uitsluitend in één korte zin dat je klaar bent."

    hidden_logs = io.StringIO()
    started = time.perf_counter()

    with contextlib.redirect_stdout(hidden_logs):
        result = engine.process(question)

    elapsed = time.perf_counter() - started
    answer = str(getattr(result, "answer", "")).strip()

    print()
    print("VOLLEDIGE BILGE-PIPELINE")
    print("-" * 52)
    print(f"Totale wachttijd      : {elapsed:.2f} seconden")
    print(f"Antwoord              : {answer}")


def main() -> None:
    """Voert alle snelheidsmetingen uit."""
    print()
    print("=" * 52)
    print("             BILGE SNELHEIDSMETING")
    print("=" * 52)
    print("Dit kan bij de eerste test even duren.")
    print("Voer tijdens de meting geen andere commando's in.")

    started = time.perf_counter()

    with contextlib.redirect_stdout(io.StringIO()):
        engine = ConversationEngine()

    engine_time = time.perf_counter() - started

    print()
    print("CONVERSATION ENGINE")
    print("-" * 52)
    print(f"Opstarttijd           : {engine_time:.2f} seconden")

    direct_ollama_test("DIRECTE OLLAMA-TEST 1")
    direct_ollama_test("DIRECTE OLLAMA-TEST 2 (MODEL WARM)")
    full_bilge_test(engine)

    print()
    print("=" * 52)
    print("Meting voltooid.")
    print("=" * 52)


if __name__ == "__main__":
    main()
