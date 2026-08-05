#!/usr/bin/env python3
"""
Bilge OS - File Loader

Verantwoordelijkheid:
- Bestanden binnen de Bilge-map veilig controleren.
- UTF-8-tekstbestanden inlezen.
- Duidelijke foutmeldingen geven.
- Nooit bestanden wijzigen of verwijderen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


class BilgeFileError(Exception):
    """Basisfout voor problemen bij het inlezen van Bilge-bestanden."""


class FileOutsideBilgeError(BilgeFileError):
    """Het gevraagde bestand bevindt zich buiten de Bilge-map."""


class BilgeFileNotFoundError(BilgeFileError):
    """Het gevraagde Bilge-bestand bestaat niet."""


class BilgeFileLoader:
    """Leest tekstbestanden veilig vanuit één vaste Bilge-hoofdmap."""

    def __init__(self, bilge_root: str | Path = "~/Bilge") -> None:
        self.bilge_root = Path(bilge_root).expanduser().resolve()

        if not self.bilge_root.exists():
            raise BilgeFileNotFoundError(
                f"De Bilge-map bestaat niet: {self.bilge_root}"
            )

        if not self.bilge_root.is_dir():
            raise BilgeFileError(
                f"Het Bilge-pad is geen map: {self.bilge_root}"
            )

    def resolve_path(self, relative_path: str | Path) -> Path:
        """
        Zet een relatief Bilge-pad om naar een veilig absoluut pad.

        Voorbeeld:
            Core/01_Missie.md
        """
        requested_path = (self.bilge_root / relative_path).resolve()

        try:
            requested_path.relative_to(self.bilge_root)
        except ValueError as exc:
            raise FileOutsideBilgeError(
                f"Toegang buiten de Bilge-map is niet toegestaan: "
                f"{requested_path}"
            ) from exc

        return requested_path

    def exists(self, relative_path: str | Path) -> bool:
        """Controleert of een bestand binnen de Bilge-map bestaat."""
        return self.resolve_path(relative_path).is_file()

    def read_text(
        self,
        relative_path: str | Path,
        *,
        required: bool = True,
    ) -> str | None:
        """
        Leest een UTF-8-tekstbestand.

        required=True:
            Geeft een fout als het bestand ontbreekt.

        required=False:
            Geeft None als het bestand ontbreekt.
        """
        file_path = self.resolve_path(relative_path)

        if not file_path.exists():
            if required:
                raise BilgeFileNotFoundError(
                    f"Verplicht bestand ontbreekt: {file_path}"
                )
            return None

        if not file_path.is_file():
            raise BilgeFileError(
                f"Het opgegeven pad is geen bestand: {file_path}"
            )

        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise BilgeFileError(
                f"Het bestand is geen geldig UTF-8-tekstbestand: {file_path}"
            ) from exc
        except OSError as exc:
            raise BilgeFileError(
                f"Het bestand kon niet worden gelezen: {file_path}"
            ) from exc

    def read_many(
        self,
        relative_paths: Iterable[str | Path],
        *,
        required: bool = True,
    ) -> dict[str, str]:
        """Leest meerdere bestanden en geeft hun inhoud per pad terug."""
        loaded_files: dict[str, str] = {}

        for relative_path in relative_paths:
            content = self.read_text(relative_path, required=required)

            if content is not None:
                loaded_files[str(relative_path)] = content

        return loaded_files

    def check_required(
        self,
        relative_paths: Iterable[str | Path],
    ) -> list[str]:
        """Geeft een lijst terug van verplichte bestanden die ontbreken."""
        missing_files: list[str] = []

        for relative_path in relative_paths:
            if not self.exists(relative_path):
                missing_files.append(str(relative_path))

        return missing_files


def self_test() -> int:
    """Voert een eenvoudige, alleen-lezen test uit."""
    required_files = [
        "00_Constitutie.md",
        "Core/01_Missie.md",
        "Core/02_Identiteit.md",
        "Core/08_Kernwaarden.md",
        "Engine/00_Architectuur.md",
        "Engine/01_Boot/01_Boot_Sequence.md",
        "Engine/06_Safety/01_Safety_Engine.md",
    ]

    try:
        loader = BilgeFileLoader()
        missing_files = loader.check_required(required_files)

        print(f"Bilge-hoofdmap: {loader.bilge_root}")

        if missing_files:
            print("\nOntbrekende verplichte bestanden:")
            for missing_file in missing_files:
                print(f"- {missing_file}")
            return 1

        constitution = loader.read_text("00_Constitutie.md")

        print(f"Verplichte bestanden gevonden: {len(required_files)}")
        print(f"Constitutie ingelezen: {len(constitution or '')} tekens")
        print("File Loader-test geslaagd.")
        return 0

    except BilgeFileError as exc:
        print(f"File Loader-fout: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(self_test())
