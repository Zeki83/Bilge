"""
Bilge Voice Web v1.

Privéwebinterface voor:
- typen vanuit Safari;
- live gestreamde Bilge-antwoorden;
- zin-voor-zin spraak via de stem van het apparaat;
- Nederlands en Turks;
- stoppen van lopende spraak.

De browser spreekt de tekst uit. De VPS genereert geen audio.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    Response,
    StreamingResponse,
)
from pydantic import BaseModel, Field

from bilge.conversation_engine import (
    ConversationEngine,
    ConversationPipelineError,
)


app = FastAPI(
    title="Bilge Voice Web",
    version="1.0.0",
)

engine = ConversationEngine()
engine_lock = asyncio.Lock()


class TTSRequest(BaseModel):
    """Tekst die lokaal door Piper wordt uitgesproken."""

    text: str = Field(
        min_length=1,
        max_length=1_000,
    )


class ChatRequest(BaseModel):
    """Bericht uit de webinterface."""

    message: str = Field(
        min_length=1,
        max_length=4_000,
    )


CJK_PATTERN = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff"
    r"\u3040-\u30ff\uac00-\ud7af]"
)

SENTENCE_BOUNDARY = re.compile(
    r"(?<=[.!?])(?:\s+|$)|\n+"
)


def is_safe_sentence(value: str) -> bool:
    """Blokkeert lege tekst en ongewenste CJK-modelafwijkingen."""
    cleaned = value.strip()

    if not cleaned:
        return False

    return CJK_PATTERN.search(cleaned) is None


def event_line(event: str, data: dict[str, Any]) -> bytes:
    """Maakt één newline-delimited JSON-event."""
    payload = {
        "event": event,
        "data": data,
    }

    return (
        json.dumps(
            payload,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


async def stream_chat(message: str) -> AsyncIterator[bytes]:
    """
    Verwerkt één Bilge-gesprek en streamt veilige complete zinnen.

    ConversationEngine draait in een workerthread, zodat FastAPI zelf
    beschikbaar blijft.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

    raw_buffer = ""
    visible_sentences: list[str] = []

    def enqueue(
        event: str,
        value: Any,
    ) -> None:
        loop.call_soon_threadsafe(
            queue.put_nowait,
            (event, value),
        )

    def on_chunk(chunk: str) -> None:
        nonlocal raw_buffer

        if not isinstance(chunk, str) or not chunk:
            return

        raw_buffer += chunk

        while True:
            match = SENTENCE_BOUNDARY.search(raw_buffer)

            if match is None:
                break

            end = match.end()
            candidate = raw_buffer[:end].strip()
            raw_buffer = raw_buffer[end:]

            if not is_safe_sentence(candidate):
                continue

            normalized = " ".join(candidate.split())

            if normalized in visible_sentences:
                continue

            visible_sentences.append(normalized)

            enqueue(
                "sentence",
                {
                    "text": normalized,
                },
            )

    def run_engine() -> None:
        try:
            result = engine.process(
                message,
                stream_callback=on_chunk,
            )

            if raw_buffer.strip() and is_safe_sentence(raw_buffer):
                normalized_tail = " ".join(
                    raw_buffer.strip().split()
                )

                if (
                    normalized_tail
                    and normalized_tail not in visible_sentences
                ):
                    visible_sentences.append(normalized_tail)

                    enqueue(
                        "sentence",
                        {
                            "text": normalized_tail,
                        },
                    )

            enqueue(
                "complete",
                {
                    "answer": result.answer,
                },
            )

        except ConversationPipelineError as exc:
            enqueue(
                "error",
                {
                    "message": str(exc),
                },
            )

        except Exception as exc:  # Veilige webgrens
            enqueue(
                "error",
                {
                    "message": (
                        "Bilge kon het antwoord niet verwerken: "
                        f"{exc}"
                    ),
                },
            )

        finally:
            enqueue("finished", {})

    yield event_line(
        "status",
        {
            "message": "Bilge verwerkt je bericht...",
        },
    )

    async with engine_lock:
        worker = asyncio.create_task(
            asyncio.to_thread(run_engine)
        )

        while True:
            event, value = await queue.get()

            if event == "finished":
                break

            yield event_line(event, value)

        await worker


@app.get("/audio/bilge-test.wav")
async def bilge_test_audio() -> FileResponse:
    """Geeft de lokale Piper-teststem terug aan de browser."""
    audio_path = (
        Path(__file__).resolve().parent.parent
        / "voices"
        / "bilge_test.wav"
    )

    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Bilge-teststem niet gevonden.",
        )

    return FileResponse(
        path=audio_path,
        media_type="audio/wav",
        filename="bilge_test.wav",
    )


@app.post("/api/tts")
async def text_to_speech(request: TTSRequest) -> Response:
    """Maakt één Bilge-zin lokaal tot WAV-audio."""
    sentence = " ".join(request.text.strip().split())

    if not sentence:
        raise HTTPException(
            status_code=400,
            detail="Geen tekst om uit te spreken.",
        )

    if CJK_PATTERN.search(sentence):
        raise HTTPException(
            status_code=400,
            detail="Onveilige tekst voor spraak geweigerd.",
        )

    model_path = (
        Path(__file__).resolve().parent.parent
        / "voices"
        / "nl_BE-nathalie-medium.onnx"
    )

    if not model_path.exists():
        raise HTTPException(
            status_code=500,
            detail="Bilge-stemmodel niet gevonden.",
        )

    try:
        result = subprocess.run(
            [
                "python3",
                "-m",
                "piper",
                "--model",
                str(model_path),
                "--output_raw",
            ],
            input=sentence.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=30,
        )

    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504,
            detail="Bilge-stem reageerde te langzaam.",
        ) from exc

    except subprocess.CalledProcessError as exc:
        error_text = exc.stderr.decode(
            "utf-8",
            errors="replace",
        )

        raise HTTPException(
            status_code=500,
            detail=f"Piper-fout: {error_text}",
        ) from exc

    raw_audio = result.stdout

    if not raw_audio:
        raise HTTPException(
            status_code=500,
            detail="Piper maakte geen audio.",
        )

    # Piper nl_BE-nathalie-medium gebruikt 22.050 Hz,
    # 16-bit mono PCM. We bouwen daarvan hier een WAV.
    import io
    import wave

    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(raw_audio)

    return Response(
        content=wav_buffer.getvalue(),
        media_type="audio/wav",
        headers={
            "Cache-Control": "no-store",
        },
    )


@app.get("/", response_class=HTMLResponse)
async def homepage() -> str:
    """Toont de mobiele Bilge-webinterface."""
    return HTML_PAGE


@app.get("/health")
async def health() -> dict[str, str]:
    """Eenvoudige gezondheidscontrole."""
    return {
        "status": "ok",
        "service": "bilge-voice-web",
    }


@app.post("/api/chat")
async def chat(request: Request) -> StreamingResponse:
    """Ontvangt een bericht en retourneert een live antwoordstream."""
    try:
        body = await request.json()
        parsed = ChatRequest.model_validate(body)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Ongeldig of leeg bericht.",
        ) from exc

    return StreamingResponse(
        stream_chat(parsed.message.strip()),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


HTML_PAGE = r"""<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width, initial-scale=1, viewport-fit=cover"
  >
  <meta name="theme-color" content="#101522">
  <title>Bilge Voice</title>

  <style>
    :root {
      color-scheme: dark;
      font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: #101522;
      color: #f6f7fb;
    }

    main {
      width: min(760px, 100%);
      min-height: 100vh;
      margin: 0 auto;
      padding:
        max(18px, env(safe-area-inset-top))
        16px
        max(24px, env(safe-area-inset-bottom));
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    header {
      text-align: center;
      padding: 8px 0 4px;
    }

    h1 {
      margin: 0;
      font-size: 1.55rem;
    }

    .subtitle {
      margin: 6px 0 0;
      color: #aeb8cc;
      font-size: 0.92rem;
    }

    #messages {
      flex: 1;
      min-height: 46vh;
      overflow-y: auto;
      padding: 4px 0 18px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .message {
      max-width: 88%;
      padding: 12px 14px;
      border-radius: 18px;
      line-height: 1.45;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .user {
      align-self: flex-end;
      background: #315f55;
    }

    .assistant {
      align-self: flex-start;
      background: #20283a;
    }

    .status {
      align-self: center;
      color: #aeb8cc;
      font-size: 0.88rem;
      padding: 4px;
    }

    .error {
      align-self: center;
      background: #542a32;
    }

    .controls {
      position: sticky;
      bottom: 0;
      background: rgba(16, 21, 34, 0.96);
      padding-top: 8px;
    }

    textarea {
      width: 100%;
      min-height: 76px;
      max-height: 180px;
      resize: vertical;
      border: 1px solid #364159;
      border-radius: 16px;
      background: #171d2b;
      color: inherit;
      font: inherit;
      padding: 13px;
      outline: none;
    }

    textarea:focus {
      border-color: #5b8f83;
    }

    .buttons {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 10px;
    }

    button {
      min-height: 48px;
      border: 0;
      border-radius: 14px;
      font: inherit;
      font-weight: 650;
      cursor: pointer;
    }

    #send {
      background: #4d8579;
      color: white;
    }

    #stop {
      background: #343c50;
      color: white;
    }

    button:disabled {
      opacity: 0.55;
      cursor: default;
    }

    .voice-row {
      display: flex;
      align-items: center;
      gap: 9px;
      margin-top: 10px;
      color: #c2cad9;
      font-size: 0.9rem;
    }

    input[type="checkbox"] {
      width: 20px;
      height: 20px;
    }
  </style>
</head>

<body>
<audio
  id="bilgeAudio"
  preload="auto"
  playsinline
></audio>

<main>
  <header>
    <h1>Bilge Voice</h1>
    <p class="subtitle">
      Live antwoorden met Nederlandse en Turkse spraak
    </p>
  </header>

  <section id="messages" aria-live="polite"></section>

  <section class="controls">
    <textarea
      id="input"
      placeholder="Typ je bericht aan Bilge..."
      autocomplete="off"
    ></textarea>

    <div class="buttons">
      <button id="send" type="button">Versturen</button>
      <button id="stop" type="button">Stop stem</button>
      <button id="testPiper" type="button">Test Bilge-stem</button>
    </div>

    <label class="voice-row">
      <input id="speechEnabled" type="checkbox" checked>
      Bilge’s antwoorden uitspreken
    </label>
  </section>
</main>

<script>
(() => {
  const messages = document.getElementById("messages");
  const input = document.getElementById("input");
  const sendButton = document.getElementById("send");
  const stopButton = document.getElementById("stop");
  const testPiperButton =
    document.getElementById("testPiper");
  const speechEnabled =
    document.getElementById("speechEnabled");

  let activeAssistantBubble = null;
  let voices = [];

  const bilgeAudio =
    document.getElementById("bilgeAudio");

  const piperQueue = [];

  let piperPlaying = false;
  let piperGeneration = 0;
  let currentAudioUrl = null;

  function loadVoices() {
    voices = window.speechSynthesis
      ? window.speechSynthesis.getVoices()
      : [];
  }

  loadVoices();

  if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }

  function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }

  function addMessage(text, className) {
    const element = document.createElement("div");
    element.className = `message ${className}`;
    element.textContent = text;
    messages.appendChild(element);
    scrollToBottom();
    return element;
  }

  function addStatus(text) {
    const element = document.createElement("div");
    element.className = "status";
    element.textContent = text;
    messages.appendChild(element);
    scrollToBottom();
    return element;
  }

  function detectLanguage(text) {
    const value = text.toLocaleLowerCase("tr-TR");

    const turkishSignals = [
      " nasıl",
      " neden",
      " için",
      " teşekkür",
      " merhaba",
      " selam",
      " misin",
      " mısın",
      " mı",
      " mi",
      " ş",
      " ğ",
      " ı",
    ];

    return turkishSignals.some(
      signal => ` ${value}`.includes(signal)
    )
      ? "tr-TR"
      : "nl-NL";
  }

  function chooseVoice(language) {
    const exact = voices.find(
      voice => voice.lang === language
    );

    if (exact) {
      return exact;
    }

    const prefix = language.slice(0, 2).toLowerCase();

    return voices.find(
      voice => voice.lang.toLowerCase().startsWith(prefix)
    ) || null;
  }

  async function createPiperAudio(text, generation) {
    const response = await fetch("/api/tts", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text,
      }),
    });

    if (!response.ok) {
      let detail = "Piper kon geen audio maken.";

      try {
        const payload = await response.json();

        if (payload.detail) {
          detail = payload.detail;
        }
      } catch (_) {
      }

      throw new Error(detail);
    }

    if (generation !== piperGeneration) {
      return null;
    }

    return await response.blob();
  }


  async function playNextPiperSentence() {
    if (
      piperPlaying ||
      piperQueue.length === 0
    ) {
      return;
    }

    piperPlaying = true;

    const item = piperQueue.shift();
    const generation = item.generation;

    try {
      const blob = await createPiperAudio(
        item.text,
        generation
      );

      if (
        !blob ||
        generation !== piperGeneration
      ) {
        piperPlaying = false;
        playNextPiperSentence();
        return;
      }

      if (currentAudioUrl) {
        URL.revokeObjectURL(currentAudioUrl);
      }

      currentAudioUrl = URL.createObjectURL(blob);

      bilgeAudio.src = currentAudioUrl;
      bilgeAudio.volume = 1.0;

      bilgeAudio.onended = () => {
        piperPlaying = false;
        playNextPiperSentence();
      };

      bilgeAudio.onerror = () => {
        piperPlaying = false;
        addStatus("Bilge-audio kon niet worden afgespeeld.");
        playNextPiperSentence();
      };

      await bilgeAudio.play();

    } catch (error) {
      piperPlaying = false;

      addStatus(
        "Bilge-stemfout: " + error.message
      );

      playNextPiperSentence();
    }
  }


  function speakSentence(text) {
    if (
      !speechEnabled.checked ||
      !text.trim()
    ) {
      return;
    }

    piperQueue.push({
      text: text.trim(),
      generation: piperGeneration,
    });

    playNextPiperSentence();
  }

  function stopSpeech() {
    piperGeneration += 1;
    piperQueue.length = 0;
    piperPlaying = false;

    bilgeAudio.pause();
    bilgeAudio.removeAttribute("src");
    bilgeAudio.load();

    if (currentAudioUrl) {
      URL.revokeObjectURL(currentAudioUrl);
      currentAudioUrl = null;
    }

    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }

  async function sendMessage() {
    const message = input.value.trim();

    if (!message || sendButton.disabled) {
      return;
    }

    stopSpeech();

    /*
     * Nieuwe spraakronde.
     * De klik op Versturen geldt op iPhone als
     * gebruikershandeling voor het audiokanaal.
     */
    bilgeAudio.load();

    addMessage(message, "user");
    input.value = "";

    activeAssistantBubble = addMessage("", "assistant");
    const status = addStatus("Bilge denkt...");
    sendButton.disabled = true;

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(
          `Serverfout ${response.status}`
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let completeAnswer = "";

      while (true) {
        const result = await reader.read();

        if (result.done) {
          break;
        }

        buffer += decoder.decode(
          result.value,
          {stream: true}
        );

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) {
            continue;
          }

          const payload = JSON.parse(line);

          if (payload.event === "sentence") {
            const sentence = payload.data.text;

            activeAssistantBubble.textContent +=
              (
                activeAssistantBubble.textContent
                  ? " "
                  : ""
              ) + sentence;

            speakSentence(sentence);
            scrollToBottom();
          }

          if (payload.event === "complete") {
            completeAnswer =
              payload.data.answer || "";
          }

          if (payload.event === "error") {
            throw new Error(
              payload.data.message ||
              "Onbekende Bilge-fout"
            );
          }
        }
      }

      if (
        completeAnswer &&
        !activeAssistantBubble.textContent.trim()
      ) {
        activeAssistantBubble.textContent =
          completeAnswer;
        speakSentence(completeAnswer);
      }

      if (!activeAssistantBubble.textContent.trim()) {
        activeAssistantBubble.textContent =
          "Ik kon nu geen bruikbaar antwoord maken.";
      }

    } catch (error) {
      activeAssistantBubble.remove();

      addMessage(
        `Fout: ${error.message}`,
        "error"
      );

    } finally {
      status.remove();
      sendButton.disabled = false;
      activeAssistantBubble = null;
      input.focus();
      scrollToBottom();
    }
  }

  sendButton.addEventListener("click", sendMessage);
  stopButton.addEventListener("click", stopSpeech);

  testPiperButton.addEventListener("click", async () => {
    const audio = new Audio(
      "/audio/bilge-test.wav?ts=" + Date.now()
    );

    audio.volume = 1.0;

    try {
      await audio.play();
      addStatus("Lokale Bilge-stem wordt afgespeeld.");
    } catch (error) {
      addStatus(
        "Audio kon niet starten: " + error.message
      );
    }
  });

  input.addEventListener("keydown", event => {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      sendMessage();
    }
  });

  addStatus(
    "Klaar. Typ een bericht en tik op Versturen."
  );
})();
</script>
</body>
</html>
"""


def main() -> None:
    """Start de ontwikkelserver."""
    import uvicorn

    uvicorn.run(
        "bilge.voice_web:app",
        host="0.0.0.0",
        port=8010,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
