#!/usr/bin/env python3
"""
Bilge OS - Boot Loader

Laadt alle essentiële onderdelen van Bilge OS en geeft een BootState terug.
"""

from __future__ import annotations

from bilge.config import CORE_FILES
from bilge.file_loader import BilgeFileError, BilgeFileLoader
from bilge.models import BootState


class BootLoader:
    """Laadt alle essentiële onderdelen van Bilge OS."""

    def __init__(self) -> None:
        self.loader = BilgeFileLoader()
        self.state = BootState()

    def load_constitution(self) -> None:
        print("[BOOT] Constitutie laden...")

        relative_path = "00_Constitutie.md"
        text = self.loader.read_text(relative_path)

        self.state.loaded_documents[relative_path] = text or ""
        self.state.constitution_loaded = True

        print("[OK] Constitutie geladen")

    def load_core(self) -> None:
        print("[BOOT] Core laden...")

        for filename in CORE_FILES:
            relative_path = f"Core/{filename}"
            text = self.loader.read_text(relative_path)

            self.state.loaded_documents[relative_path] = text or ""
            print(f"[OK] {filename}")

        self.state.core_loaded = True

    def load_architecture(self) -> None:
        print("[BOOT] Architectuur laden...")

        relative_path = "Engine/00_Architectuur.md"
        text = self.loader.read_text(relative_path)

        self.state.loaded_documents[relative_path] = text or ""
        self.state.architecture_loaded = True

        print("[OK] Architectuur geladen")

    def load_safety(self) -> None:
        print("[BOOT] Safety laden...")

        relative_path = "Engine/06_Safety/01_Safety_Engine.md"
        text = self.loader.read_text(relative_path)

        self.state.loaded_documents[relative_path] = text or ""
        self.state.safety_loaded = True

        print("[OK] Safety geladen")

    def essential_components_loaded(self) -> bool:
        """Controleert of alle verplichte onderdelen geladen zijn."""
        return all(
            (
                self.state.constitution_loaded,
                self.state.core_loaded,
                self.state.architecture_loaded,
                self.state.safety_loaded,
            )
        )

    def boot(self) -> BootState:
        """Voert de volledige veilige bootprocedure uit."""
        print("\n===== Bilge OS Boot =====\n")

        try:
            self.load_constitution()
            print()

            self.load_core()
            print()

            self.load_architecture()
            print()

            self.load_safety()

            success = self.essential_components_loaded()

            self.state.boot_completed = success
            self.state.completed = success

        except BilgeFileError as exc:
            self.state.boot_completed = False
            self.state.completed = False
            self.state.errors.append(str(exc))

            print("\n[BOOT-FOUT]")
            print(exc)

        print("\n=========================")

        if self.state.boot_completed:
            print("Bilge succesvol opgestart.")
        else:
            print("Bilge kon niet volledig worden opgestart.")

        print()
        print(f"Documenten geladen   : {len(self.state.loaded_documents)}")
        print(f"Constitutie geladen  : {self.state.constitution_loaded}")
        print(f"Core geladen         : {self.state.core_loaded}")
        print(f"Architectuur geladen : {self.state.architecture_loaded}")
        print(f"Safety geladen       : {self.state.safety_loaded}")
        print(f"Boot voltooid        : {self.state.boot_completed}")
        print(f"State voltooid       : {self.state.completed}")

        return self.state


if __name__ == "__main__":
    state = BootLoader().boot()

    print("\nBootState:")
    print(state)

    raise SystemExit(0 if state.successful else 1)
