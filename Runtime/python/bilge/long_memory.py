#!/usr/bin/env python3
"""
Bilge OS - Long Memory

Blijvend lokaal geheugen voor informatie die op langere termijn nuttig is.

Deze module:
- bewaart gegevens uitsluitend lokaal op de VPS;
- gebruikt een leesbaar JSON-bestand;
- ondersteunt voorkeuren, feiten, doelen en werkwijzen;
- voorkomt dubbele herinneringen;
- kan zoeken, bijwerken en verwijderen;
- schrijft wijzigingen atomair weg;
- weigert herkenbare geheime gegevens;
- maakt geen verbinding met externe apps of diensten.

Standaard opslag:
    ~/Bilge/Memory/long_memory.json
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from bilge.config import MEMORY


MemoryCategory = Literal[
    "preference",
    "fact",
    "goal",
    "workflow",
    "decision",
    "other",
]


class LongMemoryError(Exception):
    """Basisfout voor problemen binnen Long Memory."""


class MemoryNotFoundError(LongMemoryError):
    """De gevraagde herinnering bestaat niet."""


class InvalidMemoryError(LongMemoryError):
    """De aangeleverde herinnering is ongeldig."""


class SensitiveMemoryError(LongMemoryError):
    """De informatie bevat mogelijk geheime gegevens."""


@dataclass(slots=True)
class MemoryRecord:
    """Eén blijvende herinnering."""

    id: str
    category: MemoryCategory
    content: str
    context: str = ""
    source: str = "user"
    active: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class LongMemory:
    """Beheert blijvende herinneringen in een lokaal JSON-bestand."""

    ALLOWED_CATEGORIES = {
        "preference",
        "fact",
        "goal",
        "workflow",
        "decision",
        "other",
    }

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
            r"\b(?:seed phrase|recovery phrase|herstelzin)\b"
            r"\s*[:=]\s*.+",
            re.IGNORECASE,
        ),
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:cvv|cvc)\b\s*[:=]?\s*\d{3,4}\b",
            re.IGNORECASE,
        ),
    )

    def __init__(
        self,
        storage_path: str | Path | None = None,
    ) -> None:
        self.storage_path = (
            Path(storage_path).expanduser().resolve()
            if storage_path is not None
            else (MEMORY / "long_memory.json").resolve()
        )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._records: dict[str, MemoryRecord] = {}
        self._load()

    @staticmethod
    def normalize_text(value: str, field_name: str) -> str:
        """Normaliseert tekst en controleert het datatype."""
        if not isinstance(value, str):
            raise InvalidMemoryError(
                f"{field_name} moet tekst zijn."
            )

        return " ".join(value.strip().split())

    def ensure_safe_text(
        self,
        value: str,
        field_name: str,
    ) -> str:
        """Weigert herkenbare geheime gegevens."""
        normalized = self.normalize_text(value, field_name)

        if any(
            pattern.search(normalized)
            for pattern in self.SENSITIVE_PATTERNS
        ):
            raise SensitiveMemoryError(
                f"{field_name} lijkt geheime informatie te bevatten "
                "en wordt daarom niet opgeslagen."
            )

        return normalized

    def validate_category(
        self,
        category: str,
    ) -> MemoryCategory:
        """Controleert en normaliseert de geheugencategorie."""
        normalized = self.normalize_text(
            category,
            "Categorie",
        ).lower()

        if normalized not in self.ALLOWED_CATEGORIES:
            raise InvalidMemoryError(
                "Ongeldige categorie. Gebruik: "
                + ", ".join(sorted(self.ALLOWED_CATEGORIES))
                + "."
            )

        return normalized  # type: ignore[return-value]

    @staticmethod
    def content_key(
        category: str,
        content: str,
    ) -> tuple[str, str]:
        """Maakt een sleutel voor dubbele herinneringen."""
        return category.casefold(), content.casefold()

    def _load(self) -> None:
        """Laadt bestaande herinneringen vanaf schijf."""
        if not self.storage_path.exists():
            self._records = {}
            return

        try:
            raw_data = json.loads(
                self.storage_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise LongMemoryError(
                f"Long Memory bevat ongeldige JSON: "
                f"{self.storage_path}"
            ) from exc
        except OSError as exc:
            raise LongMemoryError(
                f"Long Memory kon niet worden gelezen: "
                f"{self.storage_path}"
            ) from exc

        if not isinstance(raw_data, dict):
            raise LongMemoryError(
                "Long Memory moet een JSON-object bevatten."
            )

        records_data = raw_data.get("records", {})

        if not isinstance(records_data, dict):
            raise LongMemoryError(
                "Het veld 'records' is ongeldig."
            )

        loaded: dict[str, MemoryRecord] = {}

        for record_id, record_data in records_data.items():
            if not isinstance(record_data, dict):
                continue

            try:
                loaded[record_id] = MemoryRecord(**record_data)
            except TypeError as exc:
                raise LongMemoryError(
                    f"Herinnering '{record_id}' heeft een "
                    "ongeldige structuur."
                ) from exc

        self._records = loaded

    def _save(self) -> None:
        """Schrijft herinneringen atomair naar schijf."""
        payload = {
            "version": 1,
            "updated_at": datetime.now(UTC).isoformat(),
            "records": {
                record_id: asdict(record)
                for record_id, record in self._records.items()
            },
        }

        temporary_path: Path | None = None

        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.storage_path.parent,
                prefix=".long_memory_",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                json.dump(
                    payload,
                    temporary_file,
                    ensure_ascii=False,
                    indent=2,
                )
                temporary_file.write("\n")
                temporary_path = Path(temporary_file.name)

            temporary_path.replace(self.storage_path)

        except OSError as exc:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink(missing_ok=True)

            raise LongMemoryError(
                f"Long Memory kon niet worden opgeslagen: "
                f"{self.storage_path}"
            ) from exc

    def find_duplicate(
        self,
        category: MemoryCategory,
        content: str,
    ) -> MemoryRecord | None:
        """Zoekt een actieve herinnering met dezelfde inhoud."""
        wanted_key = self.content_key(category, content)

        for record in self._records.values():
            if (
                record.active
                and self.content_key(
                    record.category,
                    record.content,
                ) == wanted_key
            ):
                return record

        return None

    def add_memory(
        self,
        category: str,
        content: str,
        *,
        context: str = "",
        source: str = "user",
    ) -> MemoryRecord:
        """Slaat één nieuwe blijvende herinnering op."""
        safe_category = self.validate_category(category)
        safe_content = self.ensure_safe_text(
            content,
            "Herinnering",
        )
        safe_context = self.ensure_safe_text(
            context,
            "Context",
        )
        safe_source = self.ensure_safe_text(
            source,
            "Bron",
        )

        if not safe_content:
            raise InvalidMemoryError(
                "Een herinnering mag niet leeg zijn."
            )

        duplicate = self.find_duplicate(
            safe_category,
            safe_content,
        )

        if duplicate is not None:
            return duplicate

        record = MemoryRecord(
            id=str(uuid.uuid4()),
            category=safe_category,
            content=safe_content,
            context=safe_context,
            source=safe_source or "user",
        )

        self._records[record.id] = record
        self._save()
        return record

    def get_memory(
        self,
        memory_id: str,
    ) -> MemoryRecord:
        """Geeft één herinnering terug op basis van ID."""
        normalized_id = self.normalize_text(
            memory_id,
            "Memory ID",
        )

        if normalized_id not in self._records:
            raise MemoryNotFoundError(
                f"Herinnering '{normalized_id}' is niet gevonden."
            )

        return self._records[normalized_id]

    def list_memories(
        self,
        *,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[MemoryRecord]:
        """Geeft herinneringen gesorteerd op wijzigingsdatum terug."""
        normalized_category: MemoryCategory | None = None

        if category is not None:
            normalized_category = self.validate_category(
                category
            )

        records = list(self._records.values())

        if active_only:
            records = [
                record
                for record in records
                if record.active
            ]

        if normalized_category is not None:
            records = [
                record
                for record in records
                if record.category == normalized_category
            ]

        return sorted(
            records,
            key=lambda record: record.updated_at,
            reverse=True,
        )

    def search(
        self,
        query: str,
        *,
        category: str | None = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Zoekt eenvoudig in inhoud en context."""
        normalized_query = self.normalize_text(
            query,
            "Zoekopdracht",
        ).casefold()

        if not normalized_query:
            return []

        if not isinstance(limit, int) or limit < 1:
            raise ValueError(
                "limit moet een positief geheel getal zijn."
            )

        candidates = self.list_memories(
            category=category,
            active_only=True,
        )

        results = [
            record
            for record in candidates
            if (
                normalized_query in record.content.casefold()
                or normalized_query in record.context.casefold()
            )
        ]

        return results[:limit]

    def update_memory(
        self,
        memory_id: str,
        *,
        category: str | None = None,
        content: str | None = None,
        context: str | None = None,
    ) -> MemoryRecord:
        """Past een bestaande herinnering aan."""
        record = self.get_memory(memory_id)

        if category is not None:
            record.category = self.validate_category(category)

        if content is not None:
            safe_content = self.ensure_safe_text(
                content,
                "Herinnering",
            )

            if not safe_content:
                raise InvalidMemoryError(
                    "Een herinnering mag niet leeg zijn."
                )

            record.content = safe_content

        if context is not None:
            record.context = self.ensure_safe_text(
                context,
                "Context",
            )

        record.updated_at = datetime.now(UTC).isoformat()
        self._save()
        return record

    def deactivate_memory(
        self,
        memory_id: str,
    ) -> MemoryRecord:
        """
        Deactiveert een herinnering zonder haar direct te verwijderen.

        Dit is de veiligste standaard voor gewone wijzigingen.
        """
        record = self.get_memory(memory_id)
        record.active = False
        record.updated_at = datetime.now(UTC).isoformat()
        self._save()
        return record

    def reactivate_memory(
        self,
        memory_id: str,
    ) -> MemoryRecord:
        """Activeert een eerder gedeactiveerde herinnering opnieuw."""
        record = self.get_memory(memory_id)
        record.active = True
        record.updated_at = datetime.now(UTC).isoformat()
        self._save()
        return record

    def delete_memory(
        self,
        memory_id: str,
    ) -> MemoryRecord:
        """
        Verwijdert een herinnering permanent.

        Deze methode hoort later alleen na een expliciete opdracht van
        Zeki te worden aangeroepen.
        """
        normalized_id = self.normalize_text(
            memory_id,
            "Memory ID",
        )

        if normalized_id not in self._records:
            raise MemoryNotFoundError(
                f"Herinnering '{normalized_id}' is niet gevonden."
            )

        deleted = self._records.pop(normalized_id)
        self._save()
        return deleted

    def memory_count(
        self,
        *,
        active_only: bool = True,
    ) -> int:
        """Geeft het aantal herinneringen terug."""
        return len(
            self.list_memories(active_only=active_only)
        )


def self_test() -> int:
    """Test Long Memory in een tijdelijke map."""
    from tempfile import TemporaryDirectory

    print("===== Long Memory-test =====")

    with TemporaryDirectory() as temporary_directory:
        test_file = (
            Path(temporary_directory)
            / "long_memory_test.json"
        )

        memory = LongMemory(test_file)

        preference = memory.add_memory(
            "preference",
            "Zeki wil complete bestanden in plaats van losse regels.",
            context="Werkwijze tijdens het bouwen van Bilge OS.",
        )

        goal = memory.add_memory(
            "goal",
            "Bilge ontwikkelen met stem, avatar en een eigen app.",
            context="Langetermijndoel van het Bilge OS-project.",
        )

        duplicate = memory.add_memory(
            "preference",
            "Zeki wil complete bestanden in plaats van losse regels.",
            context="Dubbele invoer.",
        )

        if duplicate.id != preference.id:
            print(
                "FOUT: dubbele herinnering werd niet herkend."
            )
            return 1

        results = memory.search("complete bestanden")

        if len(results) != 1:
            print("FOUT: zoeken werkt niet correct.")
            return 1

        memory.update_memory(
            preference.id,
            context=(
                "Vaste ontwikkelwerkwijze: complete bestanden, "
                "daarna testen."
            ),
        )

        memory.deactivate_memory(goal.id)

        if memory.memory_count() != 1:
            print(
                "FOUT: gedeactiveerde herinnering bleef actief."
            )
            return 1

        memory.reactivate_memory(goal.id)

        reloaded = LongMemory(test_file)

        if reloaded.memory_count() != 2:
            print(
                "FOUT: herinneringen werden niet correct herladen."
            )
            return 1

        try:
            memory.add_memory(
                "fact",
                "wachtwoord: SuperGeheim123",
            )
        except SensitiveMemoryError:
            print(
                "Geheime informatie correct geweigerd."
            )
        else:
            print(
                "FOUT: geheime informatie werd opgeslagen."
            )
            return 1

        deleted = memory.delete_memory(goal.id)

        if deleted.id != goal.id:
            print(
                "FOUT: herinnering werd niet correct verwijderd."
            )
            return 1

        print(f"Actieve herinneringen: {memory.memory_count()}")
        print("Opslaan, zoeken en herladen correct getest.")

    print("Long Memory-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
