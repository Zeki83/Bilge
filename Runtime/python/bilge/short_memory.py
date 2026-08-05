#!/usr/bin/env python3
"""
Bilge OS - Short Memory

Tijdelijk werkgeheugen voor de actieve gesprekssessie.

Deze versie:
- bewaart recente berichten uitsluitend in het werkgeheugen;
- schrijft niets naar bestanden of databases;
- heeft een instelbare maximale capaciteit;
- verwijdert automatisch de oudste berichten;
- kan berichten ophalen en het geheugen leegmaken;
- weigert bekende soorten geheime informatie.

Na het stoppen of herstarten van het Python-proces is dit geheugen leeg.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


MessageRole = Literal["user", "assistant", "system"]


class ShortMemoryError(Exception):
    """Basisfout voor problemen binnen Short Memory."""


class InvalidMessageError(ShortMemoryError):
    """Het bericht of de rol is ongeldig."""


class SensitiveInformationError(ShortMemoryError):
    """Het bericht bevat mogelijk geheime informatie."""


@dataclass(frozen=True, slots=True)
class ShortMemoryMessage:
    """Eén tijdelijk bericht binnen het gesprekgeheugen."""

    role: MessageRole
    content: str
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        repr=False,
    )


class ShortMemory:
    """Bewaart een beperkt aantal recente berichten in het RAM-geheugen."""

    ALLOWED_ROLES = {"user", "assistant", "system"}

    SENSITIVE_PATTERNS = (
        re.compile(
            r"\b(?:password|wachtwoord|passwd|pin(?:code)?)\b"
            r"\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:api[_ -]?key|access[_ -]?token|secret[_ -]?key)\b"
            r"\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:2fa|otp|verification code|verificatiecode)\b"
            r"\s*[:=]?\s*\d{4,8}\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:seed phrase|herstelzin|recovery phrase)\b"
            r"\s*[:=]\s*.+",
            re.IGNORECASE,
        ),
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            re.IGNORECASE,
        ),
    )

    def __init__(self, max_messages: int = 20) -> None:
        if not isinstance(max_messages, int) or max_messages < 1:
            raise ValueError(
                "max_messages moet een positief geheel getal zijn."
            )

        self.max_messages = max_messages
        self._messages: deque[ShortMemoryMessage] = deque(
            maxlen=max_messages
        )

    @staticmethod
    def normalize_content(content: str) -> str:
        """Verwijdert overbodige witruimte uit een bericht."""
        if not isinstance(content, str):
            raise InvalidMessageError(
                "De inhoud van een bericht moet tekst zijn."
            )

        return " ".join(content.strip().split())

    def contains_sensitive_information(self, content: str) -> bool:
        """Controleert op herkenbare soorten geheime informatie."""
        return any(
            pattern.search(content)
            for pattern in self.SENSITIVE_PATTERNS
        )

    def add_message(
        self,
        role: MessageRole,
        content: str,
    ) -> ShortMemoryMessage:
        """
        Voegt één bericht toe aan het tijdelijke geheugen.

        Wanneer de capaciteit is bereikt, wordt automatisch het oudste
        bericht verwijderd.
        """
        if role not in self.ALLOWED_ROLES:
            raise InvalidMessageError(
                "Ongeldige rol. Gebruik user, assistant of system."
            )

        normalized_content = self.normalize_content(content)

        if not normalized_content:
            raise InvalidMessageError(
                "Een leeg bericht kan niet worden opgeslagen."
            )

        if self.contains_sensitive_information(normalized_content):
            raise SensitiveInformationError(
                "Het bericht lijkt geheime informatie te bevatten en "
                "wordt daarom niet in Short Memory opgeslagen."
            )

        message = ShortMemoryMessage(
            role=role,
            content=normalized_content,
        )

        self._messages.append(message)
        return message

    def get_recent(
        self,
        limit: int | None = None,
    ) -> list[ShortMemoryMessage]:
        """Geeft de meest recente berichten in chronologische volgorde."""
        messages = list(self._messages)

        if limit is None:
            return messages

        if not isinstance(limit, int) or limit < 0:
            raise ValueError(
                "limit moet een geheel getal van nul of hoger zijn."
            )

        if limit == 0:
            return []

        return messages[-limit:]

    def message_count(self) -> int:
        """Geeft het huidige aantal opgeslagen berichten terug."""
        return len(self._messages)

    def clear(self) -> int:
        """
        Maakt het tijdelijke geheugen leeg.

        Geeft terug hoeveel berichten zijn verwijderd.
        """
        removed_count = len(self._messages)
        self._messages.clear()
        return removed_count

    def is_empty(self) -> bool:
        """Controleert of Short Memory leeg is."""
        return not self._messages


def self_test() -> int:
    """Voert lokale tests uit zonder bestanden of externe verbindingen."""
    memory = ShortMemory(max_messages=3)

    print("===== Short Memory-test =====")

    memory.add_message(
        "user",
        "Laten we verdergaan met Bilge.",
    )
    memory.add_message(
        "assistant",
        "Goed, we bouwen nu het tijdelijke geheugen.",
    )
    memory.add_message(
        "user",
        "Wat was de laatste stap?",
    )

    print()
    print(f"Berichten opgeslagen: {memory.message_count()}")

    for message in memory.get_recent():
        print(f"- {message.role}: {message.content}")

    memory.add_message(
        "assistant",
        "De oudste regel wordt nu automatisch verwijderd.",
    )

    if memory.message_count() != 3:
        print("FOUT: de maximale capaciteit werkt niet.")
        return 1

    recent_messages = memory.get_recent()

    if recent_messages[0].content == "Laten we verdergaan met Bilge.":
        print("FOUT: het oudste bericht werd niet verwijderd.")
        return 1

    if len(memory.get_recent(limit=2)) != 2:
        print("FOUT: get_recent(limit=2) werkt niet.")
        return 1

    try:
        memory.add_message(
            "user",
            "wachtwoord: SuperGeheim123",
        )
    except SensitiveInformationError:
        print()
        print("Geheime informatie correct geweigerd.")
    else:
        print()
        print("FOUT: geheime informatie werd opgeslagen.")
        return 1

    removed = memory.clear()

    if removed != 3 or not memory.is_empty():
        print("FOUT: het geheugen werd niet correct geleegd.")
        return 1

    print(f"Berichten verwijderd: {removed}")
    print("Short Memory-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
