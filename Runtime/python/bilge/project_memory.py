#!/usr/bin/env python3
"""
Bilge OS - Project Memory

Lokale projectadministratie voor Bilge OS.

Deze module:
- bewaart projecten uitsluitend lokaal op de VPS;
- gebruikt een leesbaar JSON-bestand;
- houdt sprint, status, modules en volgende taak bij;
- berekent projectvoortgang;
- schrijft wijzigingen atomair weg;
- gebruikt geen externe apps, accounts of online diensten;
- weigert herkenbare geheime informatie.

Standaard opslag:
    ~/Bilge/Projects/project_memory.json
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from bilge.config import PROJECTS


class ProjectMemoryError(Exception):
    """Basisfout voor Project Memory."""


class ProjectNotFoundError(ProjectMemoryError):
    """Het gevraagde project bestaat niet."""


class InvalidProjectDataError(ProjectMemoryError):
    """De aangeleverde projectinformatie is ongeldig."""


class SensitiveProjectDataError(ProjectMemoryError):
    """De projectinformatie bevat mogelijk geheime gegevens."""


@dataclass(slots=True)
class ProjectState:
    """Actuele toestand van één project."""

    name: str
    description: str = ""
    status: str = "actief"
    current_sprint: str = ""
    completed_modules: list[str] = field(default_factory=list)
    planned_modules: list[str] = field(default_factory=list)
    last_activity: str = ""
    next_task: str = ""
    notes: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    @property
    def total_modules(self) -> int:
        """Totaal aantal unieke bekende modules."""
        return len(
            set(self.completed_modules)
            | set(self.planned_modules)
        )

    @property
    def progress_percentage(self) -> int:
        """Berekent voortgang op basis van modules."""
        total = self.total_modules

        if total == 0:
            return 0

        completed = len(set(self.completed_modules))
        return round((completed / total) * 100)


class ProjectMemory:
    """Beheert lokale projectinformatie."""

    ALLOWED_STATUSES = {
        "gepland",
        "actief",
        "gepauzeerd",
        "afgerond",
        "geannuleerd",
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
            r"\b(?:seed phrase|herstelzin|recovery phrase)\b"
            r"\s*[:=]\s*.+",
            re.IGNORECASE,
        ),
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
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
            else (PROJECTS / "project_memory.json").resolve()
        )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._projects: dict[str, ProjectState] = {}
        self._load()

    @staticmethod
    def normalize_text(value: str, field_name: str) -> str:
        """Normaliseert tekst en controleert het datatype."""
        if not isinstance(value, str):
            raise InvalidProjectDataError(
                f"{field_name} moet tekst zijn."
            )

        return " ".join(value.strip().split())

    def ensure_safe_text(
        self,
        value: str,
        field_name: str,
    ) -> str:
        """Weigert herkenbare geheime informatie."""
        normalized = self.normalize_text(value, field_name)

        if any(
            pattern.search(normalized)
            for pattern in self.SENSITIVE_PATTERNS
        ):
            raise SensitiveProjectDataError(
                f"{field_name} lijkt geheime informatie te bevatten "
                "en wordt niet opgeslagen."
            )

        return normalized

    @staticmethod
    def project_key(name: str) -> str:
        """Maakt een consistente interne projectsleutel."""
        return " ".join(name.lower().strip().split())

    @staticmethod
    def unique_items(items: list[str]) -> list[str]:
        """Verwijdert dubbele waarden met behoud van volgorde."""
        result: list[str] = []
        seen: set[str] = set()

        for item in items:
            key = item.casefold()

            if key not in seen:
                seen.add(key)
                result.append(item)

        return result

    def _load(self) -> None:
        """Laadt bestaande projectinformatie vanaf schijf."""
        if not self.storage_path.exists():
            self._projects = {}
            return

        try:
            raw_data = json.loads(
                self.storage_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as exc:
            raise ProjectMemoryError(
                f"Project Memory bevat ongeldige JSON: "
                f"{self.storage_path}"
            ) from exc
        except OSError as exc:
            raise ProjectMemoryError(
                f"Project Memory kon niet worden gelezen: "
                f"{self.storage_path}"
            ) from exc

        if not isinstance(raw_data, dict):
            raise ProjectMemoryError(
                "Project Memory moet een JSON-object bevatten."
            )

        projects_data = raw_data.get("projects", {})

        if not isinstance(projects_data, dict):
            raise ProjectMemoryError(
                "Het veld 'projects' is ongeldig."
            )

        loaded: dict[str, ProjectState] = {}

        for key, project_data in projects_data.items():
            if not isinstance(project_data, dict):
                continue

            try:
                loaded[key] = ProjectState(**project_data)
            except TypeError as exc:
                raise ProjectMemoryError(
                    f"Project '{key}' heeft een ongeldige structuur."
                ) from exc

        self._projects = loaded

    def _save(self) -> None:
        """Schrijft alle projecten atomair naar schijf."""
        payload = {
            "version": 1,
            "updated_at": datetime.now(UTC).isoformat(),
            "projects": {
                key: asdict(project)
                for key, project in self._projects.items()
            },
        }

        temporary_path: Path | None = None

        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.storage_path.parent,
                prefix=".project_memory_",
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

            raise ProjectMemoryError(
                f"Project Memory kon niet worden opgeslagen: "
                f"{self.storage_path}"
            ) from exc

    def create_project(
        self,
        name: str,
        *,
        description: str = "",
        current_sprint: str = "",
        planned_modules: list[str] | None = None,
        next_task: str = "",
    ) -> ProjectState:
        """Maakt een nieuw project aan."""
        safe_name = self.ensure_safe_text(name, "Projectnaam")

        if not safe_name:
            raise InvalidProjectDataError(
                "Een projectnaam mag niet leeg zijn."
            )

        key = self.project_key(safe_name)

        if key in self._projects:
            raise InvalidProjectDataError(
                f"Project '{safe_name}' bestaat al."
            )

        safe_description = self.ensure_safe_text(
            description,
            "Beschrijving",
        )
        safe_sprint = self.ensure_safe_text(
            current_sprint,
            "Sprint",
        )
        safe_next_task = self.ensure_safe_text(
            next_task,
            "Volgende taak",
        )

        modules = [
            self.ensure_safe_text(module, "Geplande module")
            for module in (planned_modules or [])
        ]
        modules = [
            module for module in modules if module
        ]

        project = ProjectState(
            name=safe_name,
            description=safe_description,
            current_sprint=safe_sprint,
            planned_modules=self.unique_items(modules),
            next_task=safe_next_task,
        )

        self._projects[key] = project
        self._save()
        return project

    def get_project(self, name: str) -> ProjectState:
        """Geeft één project terug."""
        key = self.project_key(name)

        if key not in self._projects:
            raise ProjectNotFoundError(
                f"Project '{name}' is niet gevonden."
            )

        return self._projects[key]

    def list_projects(self) -> list[ProjectState]:
        """Geeft alle projecten alfabetisch terug."""
        return sorted(
            self._projects.values(),
            key=lambda project: project.name.casefold(),
        )

    def set_active_sprint(
        self,
        project_name: str,
        sprint: str,
    ) -> ProjectState:
        """Past de actieve sprint aan."""
        project = self.get_project(project_name)
        project.current_sprint = self.ensure_safe_text(
            sprint,
            "Sprint",
        )
        project.updated_at = datetime.now(UTC).isoformat()
        self._save()
        return project

    def set_status(
        self,
        project_name: str,
        status: str,
    ) -> ProjectState:
        """Past de projectstatus aan."""
        normalized_status = self.normalize_text(
            status,
            "Status",
        ).lower()

        if normalized_status not in self.ALLOWED_STATUSES:
            raise InvalidProjectDataError(
                "Ongeldige status. Gebruik: "
                + ", ".join(sorted(self.ALLOWED_STATUSES))
                + "."
            )

        project = self.get_project(project_name)
        project.status = normalized_status
        project.updated_at = datetime.now(UTC).isoformat()
        self._save()
        return project

    def plan_module(
        self,
        project_name: str,
        module_name: str,
    ) -> ProjectState:
        """Voegt een module toe aan de planning."""
        project = self.get_project(project_name)
        module = self.ensure_safe_text(
            module_name,
            "Modulenaam",
        )

        if not module:
            raise InvalidProjectDataError(
                "Een modulenaam mag niet leeg zijn."
            )

        if module.casefold() not in {
            item.casefold()
            for item in project.completed_modules
        }:
            project.planned_modules = self.unique_items(
                project.planned_modules + [module]
            )

        project.updated_at = datetime.now(UTC).isoformat()
        self._save()
        return project

    def complete_module(
        self,
        project_name: str,
        module_name: str,
        *,
        activity: str | None = None,
        next_task: str | None = None,
    ) -> ProjectState:
        """Markeert een module als voltooid."""
        project = self.get_project(project_name)
        module = self.ensure_safe_text(
            module_name,
            "Modulenaam",
        )

        project.planned_modules = [
            item
            for item in project.planned_modules
            if item.casefold() != module.casefold()
        ]

        project.completed_modules = self.unique_items(
            project.completed_modules + [module]
        )

        project.last_activity = self.ensure_safe_text(
            activity or f"{module} voltooid.",
            "Laatste activiteit",
        )

        if next_task is not None:
            project.next_task = self.ensure_safe_text(
                next_task,
                "Volgende taak",
            )

        project.updated_at = datetime.now(UTC).isoformat()
        self._save()
        return project

    def set_next_task(
        self,
        project_name: str,
        next_task: str,
    ) -> ProjectState:
        """Past de volgende projecttaak aan."""
        project = self.get_project(project_name)
        project.next_task = self.ensure_safe_text(
            next_task,
            "Volgende taak",
        )
        project.updated_at = datetime.now(UTC).isoformat()
        self._save()
        return project

    def add_note(
        self,
        project_name: str,
        note: str,
    ) -> ProjectState:
        """Voegt een veilige projectnotitie toe."""
        project = self.get_project(project_name)
        safe_note = self.ensure_safe_text(
            note,
            "Projectnotitie",
        )

        if not safe_note:
            raise InvalidProjectDataError(
                "Een projectnotitie mag niet leeg zijn."
            )

        project.notes.append(safe_note)
        project.updated_at = datetime.now(UTC).isoformat()
        self._save()
        return project

    def project_summary(
        self,
        project_name: str,
    ) -> dict[str, Any]:
        """Geeft een compact projectsamenvatting terug."""
        project = self.get_project(project_name)

        return {
            "name": project.name,
            "status": project.status,
            "current_sprint": project.current_sprint,
            "completed_count": len(
                set(project.completed_modules)
            ),
            "planned_count": len(
                set(project.planned_modules)
            ),
            "progress_percentage": (
                project.progress_percentage
            ),
            "last_activity": project.last_activity,
            "next_task": project.next_task,
        }

    def delete_project(self, name: str) -> ProjectState:
        """
        Verwijdert één project uit Project Memory.

        Deze methode bestaat technisch, maar hoort later alleen na
        expliciete bevestiging van Zeki te worden aangeroepen.
        """
        key = self.project_key(name)

        if key not in self._projects:
            raise ProjectNotFoundError(
                f"Project '{name}' is niet gevonden."
            )

        deleted = self._projects.pop(key)
        self._save()
        return deleted


def self_test() -> int:
    """Test Project Memory in een tijdelijke map."""
    from tempfile import TemporaryDirectory

    print("===== Project Memory-test =====")

    with TemporaryDirectory() as temporary_directory:
        test_file = (
            Path(temporary_directory)
            / "project_memory_test.json"
        )

        memory = ProjectMemory(test_file)

        project = memory.create_project(
            "Bilge OS",
            description="Eigen lokale AI-partner voor Zeki.",
            current_sprint="Sprint 4",
            planned_modules=[
                "Short Memory",
                "Project Memory",
                "Long Memory",
                "Prompt Builder",
            ],
            next_task="Project Memory bouwen.",
        )

        if project.name != "Bilge OS":
            print("FOUT: project werd niet aangemaakt.")
            return 1

        memory.complete_module(
            "Bilge OS",
            "Short Memory",
            activity="Short Memory gebouwd en getest.",
            next_task="Project Memory afronden.",
        )

        memory.complete_module(
            "Bilge OS",
            "Project Memory",
            activity="Project Memory gebouwd en getest.",
            next_task="Long Memory bouwen.",
        )

        summary = memory.project_summary("Bilge OS")

        print()
        print(f"Project          : {summary['name']}")
        print(f"Status           : {summary['status']}")
        print(f"Sprint           : {summary['current_sprint']}")
        print(f"Modules klaar    : {summary['completed_count']}")
        print(f"Modules gepland  : {summary['planned_count']}")
        print(f"Voortgang        : {summary['progress_percentage']}%")
        print(f"Laatste activiteit: {summary['last_activity']}")
        print(f"Volgende taak    : {summary['next_task']}")

        reloaded = ProjectMemory(test_file)
        reloaded_summary = reloaded.project_summary(
            "Bilge OS"
        )

        if reloaded_summary != summary:
            print(
                "FOUT: opgeslagen project werd niet correct "
                "teruggelezen."
            )
            return 1

        try:
            memory.add_note(
                "Bilge OS",
                "api_key: supergeheim",
            )
        except SensitiveProjectDataError:
            print()
            print(
                "Geheime projectinformatie correct geweigerd."
            )
        else:
            print()
            print(
                "FOUT: geheime projectinformatie werd opgeslagen."
            )
            return 1

        deleted = memory.delete_project("Bilge OS")

        if deleted.name != "Bilge OS":
            print("FOUT: project werd niet correct verwijderd.")
            return 1

    print("Lokale opslag en herladen correct getest.")
    print("Project Memory-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
