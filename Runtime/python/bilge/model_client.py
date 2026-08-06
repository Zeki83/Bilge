#!/usr/bin/env python3
"""
Bilge OS - Model Client

Lokale verbinding tussen Bilge OS en Ollama.

Deze module:
- stuurt een PromptPackage naar de lokale Ollama API;
- gebruikt standaard qwen2.5:7b-instruct;
- gebruikt geen externe AI-dienst;
- schakelt streaming voorlopig uit;
- controleert vooraf of Ollama en het gekozen model beschikbaar zijn;
- voert geen externe apps, betalingen of accountacties uit.
"""

from __future__ import annotations

from collections.abc import Callable

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from bilge.prompt_builder import PromptPackage


class ModelClientError(Exception):
    """Basisfout voor problemen binnen de Model Client."""


class OllamaConnectionError(ModelClientError):
    """De lokale Ollama-server is niet bereikbaar."""


class OllamaResponseError(ModelClientError):
    """Ollama gaf een ongeldig of mislukt antwoord terug."""


class ModelNotAvailableError(ModelClientError):
    """Het ingestelde model is niet lokaal beschikbaar."""


class InvalidPromptPackageError(ModelClientError):
    """Het PromptPackage is ongeldig of onvolledig."""


@dataclass(slots=True)
class ModelResponse:
    """Gecontroleerd antwoord van het lokale taalmodel."""

    content: str
    model: str
    done: bool
    done_reason: str = ""
    prompt_tokens: int = 0
    response_tokens: int = 0
    total_duration_ns: int = 0
    completed: bool = False

    @property
    def total_tokens(self) -> int:
        """Totaal aantal verwerkte tokens indien bekend."""
        return self.prompt_tokens + self.response_tokens


class OllamaModelClient:
    """Stuurt prompts naar de lokale Ollama Chat API."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: int = 300,
        temperature: float = 0.5,
        num_predict: int = 700,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv(
                "BILGE_OLLAMA_URL",
                "http://127.0.0.1:11434",
            )
        ).rstrip("/")

        self.model = (
            model
            or os.getenv(
                "BILGE_MODEL",
                "qwen2.5:7b-instruct",
            )
        ).strip()

        if not self.model:
            raise ValueError("De modelnaam mag niet leeg zijn.")

        if (
            not isinstance(timeout_seconds, int)
            or timeout_seconds < 1
        ):
            raise ValueError(
                "timeout_seconds moet een positief geheel getal zijn."
            )

        if not isinstance(temperature, (int, float)):
            raise ValueError(
                "temperature moet een getal zijn."
            )

        if not 0.0 <= float(temperature) <= 2.0:
            raise ValueError(
                "temperature moet tussen 0.0 en 2.0 liggen."
            )

        if not isinstance(num_predict, int) or num_predict < 1:
            raise ValueError(
                "num_predict moet een positief geheel getal zijn."
            )

        self.timeout_seconds = timeout_seconds
        self.temperature = float(temperature)
        self.num_predict = num_predict

    @staticmethod
    def validate_prompt_package(
        package: PromptPackage,
    ) -> None:
        """Controleert of het PromptPackage verzendbaar is."""
        if not isinstance(package, PromptPackage):
            raise InvalidPromptPackageError(
                "De invoer moet een PromptPackage zijn."
            )

        if not package.completed:
            raise InvalidPromptPackageError(
                "Het PromptPackage is niet voltooid."
            )

        if not package.system_prompt.strip():
            raise InvalidPromptPackageError(
                "De systeemprompt is leeg."
            )

        if not package.user_prompt.strip():
            raise InvalidPromptPackageError(
                "De gebruikersprompt is leeg."
            )

    def _request_json(
        self,
        endpoint: str,
        *,
        payload: dict[str, Any] | None = None,
        method: str = "GET",
    ) -> dict[str, Any]:
        """Voert één JSON-request uit naar de lokale Ollama API."""
        url = f"{self.base_url}{endpoint}"

        request_data: bytes | None = None
        headers = {
            "Accept": "application/json",
        }

        if payload is not None:
            request_data = json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8")

            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            url=url,
            data=request_data,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                response_body = response.read().decode("utf-8")

        except urllib.error.HTTPError as exc:
            try:
                error_body = exc.read().decode("utf-8")
                error_data = json.loads(error_body)
                error_message = error_data.get(
                    "error",
                    error_body,
                )
            except (UnicodeDecodeError, json.JSONDecodeError):
                error_message = str(exc)

            raise OllamaResponseError(
                f"Ollama HTTP-fout {exc.code}: {error_message}"
            ) from exc

        except (
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            ConnectionError,
        ) as exc:
            raise OllamaConnectionError(
                f"Ollama is niet bereikbaar via {self.base_url}: "
                f"{exc}"
            ) from exc

        try:
            result = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise OllamaResponseError(
                "Ollama gaf geen geldige JSON terug."
            ) from exc

        if not isinstance(result, dict):
            raise OllamaResponseError(
                "Ollama gaf een onverwachte JSON-structuur terug."
            )

        if result.get("error"):
            raise OllamaResponseError(str(result["error"]))

        return result

    def list_models(self) -> list[str]:
        """Geeft de lokaal beschikbare Ollama-modellen terug."""
        data = self._request_json("/api/tags")

        models_data = data.get("models", [])

        if not isinstance(models_data, list):
            raise OllamaResponseError(
                "Het modellenoverzicht van Ollama is ongeldig."
            )

        names: list[str] = []

        for model_data in models_data:
            if not isinstance(model_data, dict):
                continue

            name = model_data.get("name") or model_data.get("model")

            if isinstance(name, str) and name.strip():
                names.append(name.strip())

        return names

    def ensure_model_available(self) -> None:
        """Controleert of het ingestelde model lokaal beschikbaar is."""
        available_models = self.list_models()

        if self.model in available_models:
            return

        raise ModelNotAvailableError(
            f"Model '{self.model}' is niet lokaal beschikbaar. "
            "Beschikbare modellen: "
            + (
                ", ".join(available_models)
                if available_models
                else "geen"
            )
        )

    def build_payload(
        self,
        package: PromptPackage,
    ) -> dict[str, Any]:
        """Bouwt de requestbody voor de Ollama Chat API."""
        self.validate_prompt_package(package)

        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": package.system_prompt,
                },
                {
                    "role": "user",
                    "content": package.user_prompt,
                },
            ],
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
        }

    def chat_stream(
        self,
        package: PromptPackage,
        *,
        on_chunk: Callable[[str], None] | None = None,
        verify_model: bool = True,
    ) -> ModelResponse:
        """
        Stuurt een PromptPackage streamend naar Ollama.

        Ieder ontvangen tekstfragment wordt direct doorgegeven aan
        on_chunk. Aan het einde wordt daarnaast een volledig
        ModelResponse teruggegeven, zodat de bestaande gesprekspipeline
        normaal kan doorgaan.
        """
        self.validate_prompt_package(package)

        if verify_model:
            self.ensure_model_available()

        payload = self.build_payload(package)
        payload["stream"] = True

        url = f"{self.base_url}/api/chat"

        request_data = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        request = urllib.request.Request(
            url=url,
            data=request_data,
            headers={
                "Accept": "application/x-ndjson",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        content_parts: list[str] = []
        final_data: dict[str, Any] = {}
        completed = False

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                for raw_line in response:
                    if not raw_line:
                        continue

                    try:
                        line = raw_line.decode("utf-8").strip()
                    except UnicodeDecodeError as exc:
                        raise OllamaResponseError(
                            "Ollama stuurde een ongeldig "
                            "UTF-8-streamfragment."
                        ) from exc

                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise OllamaResponseError(
                            "Ollama stuurde een ongeldig "
                            "JSON-streamfragment."
                        ) from exc

                    if not isinstance(data, dict):
                        raise OllamaResponseError(
                            "Ollama stuurde een onverwachte "
                            "streamstructuur."
                        )

                    if data.get("error"):
                        raise OllamaResponseError(
                            str(data["error"])
                        )

                    message = data.get("message")

                    if isinstance(message, dict):
                        chunk = message.get("content", "")

                        if isinstance(chunk, str) and chunk:
                            content_parts.append(chunk)

                            if on_chunk is not None:
                                on_chunk(chunk)

                    final_data = data

                    if bool(data.get("done", False)):
                        completed = True
                        break

        except urllib.error.HTTPError as exc:
            try:
                error_body = exc.read().decode("utf-8")
                error_data = json.loads(error_body)
                error_message = error_data.get(
                    "error",
                    error_body,
                )
            except (
                UnicodeDecodeError,
                json.JSONDecodeError,
            ):
                error_message = str(exc)

            raise OllamaResponseError(
                f"Ollama HTTP-fout {exc.code}: "
                f"{error_message}"
            ) from exc

        except (
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            ConnectionError,
        ) as exc:
            raise OllamaConnectionError(
                f"Ollama is niet bereikbaar via "
                f"{self.base_url}: {exc}"
            ) from exc

        content = "".join(content_parts).strip()

        if not content:
            raise OllamaResponseError(
                "Ollama gaf geen bruikbare "
                "streamende antwoordtekst terug."
            )

        if not completed:
            raise OllamaResponseError(
                "Ollama heeft het streamende antwoord "
                "niet voltooid."
            )

        return ModelResponse(
            content=content,
            model=str(
                final_data.get(
                    "model",
                    self.model,
                )
            ),
            done=True,
            done_reason=str(
                final_data.get(
                    "done_reason",
                    "",
                )
            ),
            prompt_tokens=int(
                final_data.get(
                    "prompt_eval_count",
                    0,
                )
                or 0
            ),
            response_tokens=int(
                final_data.get(
                    "eval_count",
                    0,
                )
                or 0
            ),
            total_duration_ns=int(
                final_data.get(
                    "total_duration",
                    0,
                )
                or 0
            ),
            completed=True,
        )

    def chat(
        self,
        package: PromptPackage,
        *,
        verify_model: bool = True,
    ) -> ModelResponse:
        """Stuurt het PromptPackage naar het lokale model."""
        self.validate_prompt_package(package)

        if verify_model:
            self.ensure_model_available()

        payload = self.build_payload(package)

        data = self._request_json(
            "/api/chat",
            payload=payload,
            method="POST",
        )

        message = data.get("message")

        if not isinstance(message, dict):
            raise OllamaResponseError(
                "Ollama-antwoord bevat geen geldig message-object."
            )

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise OllamaResponseError(
                "Ollama gaf geen bruikbare antwoordtekst terug."
            )

        done = bool(data.get("done", False))

        if not done:
            raise OllamaResponseError(
                "Ollama heeft het antwoord niet voltooid."
            )

        return ModelResponse(
            content=content.strip(),
            model=str(data.get("model", self.model)),
            done=done,
            done_reason=str(data.get("done_reason", "")),
            prompt_tokens=int(data.get("prompt_eval_count", 0) or 0),
            response_tokens=int(data.get("eval_count", 0) or 0),
            total_duration_ns=int(
                data.get("total_duration", 0) or 0
            ),
            completed=True,
        )


def self_test() -> int:
    """
    Voert eerst een lichte verbindingstest uit en daarna één korte
    echte modelgeneratie.

    De test gebruikt bewust een klein PromptPackage, zodat we alleen
    de Model Client testen en niet opnieuw de volledige Bilge-prompt.
    """
    print("===== Model Client-test =====")

    client = OllamaModelClient(
        timeout_seconds=300,
        temperature=0.2,
        num_predict=80,
    )

    try:
        models = client.list_models()
    except ModelClientError as exc:
        print(f"FOUT: {exc}")
        return 1

    print()
    print(f"Ollama URL       : {client.base_url}")
    print(f"Ingesteld model  : {client.model}")
    print(
        "Lokale modellen : "
        + (", ".join(models) if models else "geen")
    )

    try:
        client.ensure_model_available()
    except ModelClientError as exc:
        print(f"FOUT: {exc}")
        return 1

    package = PromptPackage(
        system_prompt=(
            "Je bent Bilge. Antwoord uitsluitend in het Nederlands. "
            "Houd het antwoord bij één korte zin. "
            "Voer geen externe acties uit."
        ),
        user_prompt=(
            "Zeg dat de lokale modelverbinding werkt."
        ),
        language="nl",
        objective="connection_test",
        safety_mode="normal",
        memory_types=[],
        completed=True,
    )

    print()
    print("Korte generatie starten...")

    try:
        response = client.chat(
            package,
            verify_model=False,
        )
    except ModelClientError as exc:
        print(f"FOUT: {exc}")
        return 1

    print()
    print(f"Model            : {response.model}")
    print(f"Voltooid         : {response.completed}")
    print(f"Stopreden        : {response.done_reason}")
    print(f"Prompttokens     : {response.prompt_tokens}")
    print(f"Antwoordtokens   : {response.response_tokens}")
    print(f"Antwoord         : {response.content}")

    if not response.completed:
        print("FOUT: modelantwoord is niet voltooid.")
        return 1

    print()
    print("Model Client-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
