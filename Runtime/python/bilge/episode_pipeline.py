#!/usr/bin/env python3
"""
Bilge OS - Episode Pipeline

Veilige koppeling tussen:
- EpisodeSelector;
- EpisodicMemory.

Deze module:
1. ontvangt één afgeronde gespreksronde;
2. laat de Episode Selector bepalen of opslag nuttig is;
3. bewaart alleen goedgekeurde episodes;
4. weigert gevoelige informatie;
5. voorkomt dubbele opslag via EpisodicMemory;
6. gebruikt uitsluitend lokale opslag;
7. voert geen externe acties uit.

Deze versie is nog niet automatisch gekoppeld aan ConversationEngine.
"""

from __future__ import annotations

from dataclasses import dataclass

from bilge.episode_selector import (
    EpisodeSelectionPlan,
    EpisodeSelector,
    EpisodeSelectorError,
)
from bilge.episodic_memory import (
    EpisodeRecord,
    EpisodicMemory,
    EpisodicMemoryError,
    InvalidEpisodeError,
    SensitiveEpisodeError,
)


class EpisodePipelineError(Exception):
    """Basisfout voor problemen binnen de Episode Pipeline."""


@dataclass(slots=True)
class EpisodePipelineResult:
    """Resultaat van één volledige episodeverwerking."""

    selection_plan: EpisodeSelectionPlan
    episode: EpisodeRecord | None = None
    stored: bool = False
    duplicate: bool = False
    completed: bool = False

    @property
    def decision(self) -> str:
        """Geeft de selectie-uitkomst terug."""
        return self.selection_plan.decision

    @property
    def should_store(self) -> bool:
        """Geeft terug of opslag was toegestaan."""
        return self.selection_plan.should_store


class EpisodePipeline:
    """
    Coördineert selectie en opslag van betekenisvolle gesprekken.

    De selector beslist.
    EpisodicMemory bewaart.
    De pipeline houdt de onderdelen bewust los van elkaar.
    """

    def __init__(
        self,
        *,
        selector: EpisodeSelector | None = None,
        episodic_memory: EpisodicMemory | None = None,
    ) -> None:
        self.selector = selector or EpisodeSelector()
        self.episodic_memory = episodic_memory or EpisodicMemory()

        self.last_result: EpisodePipelineResult | None = None

    def process(
        self,
        user_message: str,
        assistant_message: str,
        *,
        language: str = "unknown",
        source: str = "conversation",
    ) -> EpisodePipelineResult:
        """
        Verwerkt één afgeronde gespreksronde.

        Alleen wanneer de selector `should_store=True` teruggeeft,
        wordt de episode daadwerkelijk lokaal opgeslagen.
        """
        try:
            selection_plan = self.selector.select(
                user_message=user_message,
                assistant_message=assistant_message,
                language=language,
            )
        except EpisodeSelectorError as exc:
            raise EpisodePipelineError(
                f"Episode-selectie mislukt: {exc}"
            ) from exc

        if not selection_plan.completed:
            raise EpisodePipelineError(
                "De Episode Selector leverde geen voltooid plan."
            )

        if not selection_plan.should_store:
            result = EpisodePipelineResult(
                selection_plan=selection_plan,
                episode=None,
                stored=False,
                duplicate=False,
                completed=True,
            )

            self.last_result = result
            return result

        existing = self.episodic_memory.find_duplicate(
            user_message,
            assistant_message,
        )

        try:
            episode = self.episodic_memory.add_episode(
                user_message=user_message,
                assistant_message=assistant_message,
                summary=selection_plan.summary,
                topic=selection_plan.topic,
                language=selection_plan.language,
                keywords=selection_plan.keywords,
                importance=selection_plan.importance,
                source=source,
            )
        except (
            SensitiveEpisodeError,
            InvalidEpisodeError,
            EpisodicMemoryError,
        ) as exc:
            raise EpisodePipelineError(
                f"Episode-opslag mislukt: {exc}"
            ) from exc

        duplicate = (
            existing is not None
            and existing.id == episode.id
        )

        result = EpisodePipelineResult(
            selection_plan=selection_plan,
            episode=episode,
            stored=True,
            duplicate=duplicate,
            completed=True,
        )

        self.last_result = result
        return result

    def status(self) -> dict[str, object]:
        """Geeft een compact overzicht van de huidige toestand."""
        return {
            "episode_count": (
                self.episodic_memory.episode_count()
            ),
            "last_result_completed": bool(
                self.last_result
                and self.last_result.completed
            ),
            "last_decision": (
                self.last_result.decision
                if self.last_result
                else "none"
            ),
            "last_stored": bool(
                self.last_result
                and self.last_result.stored
            ),
            "last_duplicate": bool(
                self.last_result
                and self.last_result.duplicate
            ),
        }


def print_result(
    user_message: str,
    result: EpisodePipelineResult,
) -> None:
    """Toont het resultaat overzichtelijk."""
    print()
    print(f"Bericht      : {user_message}")
    print(f"Beslissing  : {result.decision}")
    print(f"Opslaan      : {result.should_store}")
    print(f"Opgeslagen   : {result.stored}")
    print(f"Dubbel       : {result.duplicate}")
    print(f"Voltooid     : {result.completed}")
    print(
        f"Onderwerp    : "
        f"{result.selection_plan.topic}"
    )
    print(
        f"Belang       : "
        f"{result.selection_plan.importance}"
    )

    if result.episode is not None:
        print(f"Episode ID   : {result.episode.id}")
        print(f"Samenvatting : {result.episode.summary}")

    for reason in result.selection_plan.reasons:
        print(f"Reden        : {reason}")


def self_test() -> int:
    """Test selectie, opslag, overslaan en duplicaten."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    print("===== Episode Pipeline-test =====")

    with TemporaryDirectory() as temporary_directory:
        storage_path = (
            Path(temporary_directory)
            / "episodic_memory_test.json"
        )

        pipeline = EpisodePipeline(
            selector=EpisodeSelector(),
            episodic_memory=EpisodicMemory(
                storage_path
            ),
        )

        meaningful_user = (
            "Ik wil voortaan complete bestanden ontvangen "
            "in plaats van losse regels."
        )
        meaningful_assistant = (
            "Ik zal tijdens de verdere ontwikkeling van Bilge "
            "steeds complete bestanden geven."
        )

        stored_result = pipeline.process(
            meaningful_user,
            meaningful_assistant,
            language="nl",
        )

        print_result(
            meaningful_user,
            stored_result,
        )

        if not stored_result.completed:
            print(
                "FOUT: betekenisvolle verwerking is niet voltooid."
            )
            return 1

        if not stored_result.stored:
            print(
                "FOUT: betekenisvolle episode werd niet opgeslagen."
            )
            return 1

        if stored_result.episode is None:
            print(
                "FOUT: opgeslagen episode ontbreekt."
            )
            return 1

        if pipeline.episodic_memory.episode_count() != 1:
            print(
                "FOUT: er hoort precies één episode te bestaan."
            )
            return 1

        duplicate_result = pipeline.process(
            meaningful_user,
            meaningful_assistant,
            language="nl",
        )

        print_result(
            meaningful_user,
            duplicate_result,
        )

        if not duplicate_result.stored:
            print(
                "FOUT: dubbele episode leverde geen geldig resultaat."
            )
            return 1

        if not duplicate_result.duplicate:
            print(
                "FOUT: dubbele episode werd niet herkend."
            )
            return 1

        if pipeline.episodic_memory.episode_count() != 1:
            print(
                "FOUT: dubbele episode werd opnieuw opgeslagen."
            )
            return 1

        trivial_result = pipeline.process(
            "Ok",
            "Prima, dan gaan we verder.",
            language="nl",
        )

        print_result(
            "Ok",
            trivial_result,
        )

        if trivial_result.stored:
            print(
                "FOUT: triviaal gesprek werd opgeslagen."
            )
            return 1

        if trivial_result.decision != "skip":
            print(
                "FOUT: triviaal gesprek werd niet overgeslagen."
            )
            return 1

        sensitive_result = pipeline.process(
            (
                "Onthoud mijn GitHub-token: "
                "ghp_abcdefghijklmnopqrstuvwxyz123456"
            ),
            "Ik zal deze token onthouden.",
            language="nl",
        )

        print_result(
            "Gevoelige testinhoud",
            sensitive_result,
        )

        if sensitive_result.stored:
            print(
                "FOUT: gevoelige episode werd opgeslagen."
            )
            return 1

        if sensitive_result.decision != "reject_sensitive":
            print(
                "FOUT: gevoelige episode werd niet geweigerd."
            )
            return 1

        turkish_result = pipeline.process(
            "Bugün kahve içtim.",
            "Afiyet olsun.",
            language="tr",
        )

        print_result(
            "Bugün kahve içtim.",
            turkish_result,
        )

        if turkish_result.stored:
            print(
                "FOUT: triviaal Turks gesprek werd opgeslagen."
            )
            return 1

        status = pipeline.status()

        if status["episode_count"] != 1:
            print(
                "FOUT: pipeline-status bevat een verkeerd aantal."
            )
            return 1

        print()
        print(f"Actieve episodes: {status['episode_count']}")
        print(
            "Selectie, opslag, duplicaten en veiligheid "
            "correct getest."
        )

    print("Episode Pipeline-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
