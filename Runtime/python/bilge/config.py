#!/usr/bin/env python3
"""
Bilge OS - Configuratie

Centrale configuratie voor Bilge OS.

Alle vaste paden en algemene instellingen worden hier beheerd.
"""

from pathlib import Path

# --------------------------------------------------
# Basis
# --------------------------------------------------

BILGE_VERSION = "1.0.0"

DEFAULT_LANGUAGE = "nl"

# --------------------------------------------------
# Hoofdmap
# --------------------------------------------------

BILGE_ROOT = Path("~/Bilge").expanduser().resolve()

# --------------------------------------------------
# Systeem
# --------------------------------------------------

CONSTITUTION = BILGE_ROOT / "00_Constitutie.md"

CORE = BILGE_ROOT / "Core"

ENGINE = BILGE_ROOT / "Engine"

RUNTIME = BILGE_ROOT / "Runtime"

MEMORY = BILGE_ROOT / "Memory"

PROJECTS = BILGE_ROOT / "Projects"

PROMPTS = BILGE_ROOT / "Prompts"

LOGS = BILGE_ROOT / "Logs"

SYSTEM = BILGE_ROOT / "System"

GOALS = BILGE_ROOT / "Goals"

IDEAS = BILGE_ROOT / "Ideas"

BACKUPS = BILGE_ROOT / "Backups"

# --------------------------------------------------
# Kernbestanden
# --------------------------------------------------

CORE_FILES = [
    "01_Missie.md",
    "02_Identiteit.md",
    "03_Persoonlijkheid.md",
    "04_Bilge_Kompas.md",
    "05_Communicatiestijl.md",
    "06_Geheugen.md",
    "07_Proactiviteit.md",
    "08_Kernwaarden.md",
]

# --------------------------------------------------
# Engine
# --------------------------------------------------

BOOT_SEQUENCE = (
    ENGINE
    / "01_Boot"
    / "01_Boot_Sequence.md"
)

ARCHITECTURE = (
    ENGINE
    / "00_Architectuur.md"
)

CONTEXT_ENGINE = (
    ENGINE
    / "02_Context"
    / "01_Context_Engine.md"
)

MEMORY_ENGINE = (
    ENGINE
    / "03_Memory"
    / "01_Memory_Engine.md"
)

REASONING_ENGINE = (
    ENGINE
    / "04_Reasoning"
    / "01_Reasoning_Engine.md"
)

RESPONSE_ENGINE = (
    ENGINE
    / "05_Response"
    / "01_Response_Engine.md"
)

SAFETY_ENGINE = (
    ENGINE
    / "06_Safety"
    / "01_Safety_Engine.md"
)

# --------------------------------------------------
# Test
# --------------------------------------------------

if __name__ == "__main__":

    print("Bilge OS Config")

    print("---------------------")

    print("Versie :", BILGE_VERSION)

    print("Root   :", BILGE_ROOT)

    print("Core   :", CORE)

    print("Engine :", ENGINE)

    print("Runtime:", RUNTIME)
