#!/usr/bin/env python3
"""
Bilge OS - Episode Retriever

Veilige zoeklaag voor Episodic Memory.

Deze module:
- zoekt naar relevante eerdere gesprekservaringen;
- gebruikt uitsluitend lokale Episodic Memory;
- roept geen taalmodel aan;
- maakt geen verbinding met externe diensten;
- geeft compacte contextregels terug voor een toekomstige prompt;
- beperkt het aantal resultaten en de totale tekstlengte;
- negeert triviale of te korte zoekopdrachten;
- verandert of verwijdert geen herinneringen.

Deze versie wordt nog niet automatisch door ConversationEngine gebruikt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bilge.episodic_memory import (
    EpisodeSearchResult,
    EpisodicMemory,
    EpisodicMemoryError,
)


class EpisodeRetrieverError(Exception):
    """Basisfout voor problemen binnen de Episode Retriever."""


class InvalidEpisodeRetrieverInputError(EpisodeRetrieverError):
    """De aangeleverde zoekopdracht is ongeldig."""


@dataclass(slots=True)
class RetrievedEpisode:
    """Compacte representatie van één gevonden episode."""

    episode_id: str
    summary: str
    topic: str
    language: str
    importance: int
    score: float
    matched_terms: list[str] = field(default_factory=list)

    @property
    def context_line(self) -> str:
        """Geeft een compacte promptregel terug."""
        return (
            f"[{self.topic}; belang {self.importance}; "
            f"score {self.score}] {self.summary}"
        )


@dataclass(slots=True)
class EpisodeRetrievalResult:
    """Resultaat van één episodische zoekopdracht."""

    query: str
    episodes: list[RetrievedEpisode] = field(default_factory=list)
    context_items: list[str] = field(default_factory=list)

    searched: bool = False
    found: bool = False
    completed: bool = False
    reason: str = ""

    @property
    def count(self) -> int:
        """Geeft het aantal gevonden episodes terug."""
        return len(self.episodes)


class EpisodeRetriever:
    """Haalt relevante episodische herinneringen op."""

    DEFAULT_LIMIT = 3
    MAX_LIMIT = 5
    DEFAULT_MINIMUM_SCORE = 2.0
    DEFAULT_MINIMUM_IMPORTANCE = 2

    MIN_QUERY_CHARACTERS = 8
    MAX_QUERY_CHARACTERS = 4_000
    MAX_CONTEXT_ITEM_CHARACTERS = 420
    MAX_TOTAL_CONTEXT_CHARACTERS = 1_200

    TRIVIAL_QUERIES = {
        "ok",
        "oke",
        "oké",
        "ja",
        "nee",
        "hoi",
        "hallo",
        "hey",
        "top",
        "prima",
        "bedankt",
        "dank je",
        "dankjewel",
        "thanks",
        "kom maar op",
        "ga verder",
        "doorgaan",
        "lets go",
        "let's go",
        "tamam",
        "evet",
        "hayır",
        "merhaba",
        "selam",
        "devam",
    }

    def __init__(
        self,
        episodic_memory: EpisodicMemory | None = None,
    ) -> None:
        self.episodic_memory = (
            episodic_memory or EpisodicMemory()
        )
        self.last_result: EpisodeRetrievalResult | None = None

    @staticmethod
    def normalize_text(
        value: str,
        field_name: str,
    ) -> str:
        """Normaliseert tekst en controleert het datatype."""
        if not isinstance(value, str):
            raise InvalidEpisodeRetrieverInputError(
                f"{field_name} moet tekst zijn."
            )

        return " ".join(value.strip().split())

    @staticmethod
    def normalize_language(language: str) -> str:
        """Normaliseert een ondersteunde taalcode."""
        if not isinstance(language, str):
            return "unknown"

        normalized = language.strip().casefold()

        if normalized not in {"nl", "tr", "unknown"}:
            return "unknown"

        return normalized

    def is_trivial_query(self, query: str) -> bool:
        """Controleert of zoeken waarschijnlijk geen waarde heeft."""
        normalized = query.strip(" .,!?:;").casefold()

        if normalized in self.TRIVIAL_QUERIES:
            return True

        return (
            len(normalized.split()) <= 2
            and len(normalized) < self.MIN_QUERY_CHARACTERS
        )

    def validate_limit(self, limit: int) -> int:
        """Controleert en begrenst het resultaatlimiet."""
        if not isinstance(limit, int):
            raise InvalidEpisodeRetrieverInputError(
                "limit moet een geheel getal zijn."
            )

        if limit < 1:
            raise InvalidEpisodeRetrieverInputError(
                "limit moet minimaal 1 zijn."
            )

        return min(limit, self.MAX_LIMIT)

    @staticmethod
    def truncate_text(
        value: str,
        maximum: int,
    ) -> str:
        """Kort tekst veilig af."""
        if len(value) <= maximum:
            return value

        return value[: maximum - 3].rstrip() + "..."

    def convert_result(
        self,
        result: EpisodeSearchResult,
    ) -> RetrievedEpisode:
        """Zet een opslagresultaat om naar compacte promptinformatie."""
        episode = result.episode

        return RetrievedEpisode(
            episode_id=episode.id,
            summary=self.truncate_text(
                episode.summary,
                self.MAX_CONTEXT_ITEM_CHARACTERS,
            ),
            topic=episode.topic,
            language=episode.language,
            importance=episode.importance,
            score=result.score,
            matched_terms=list(result.matched_terms),
        )

    def build_context_items(
        self,
        episodes: list[RetrievedEpisode],
    ) -> list[str]:
        """Bouwt context binnen een vaste totale tekenlimiet."""
        items: list[str] = []
        total_characters = 0

        for episode in episodes:
            item = episode.context_line

            remaining = (
                self.MAX_TOTAL_CONTEXT_CHARACTERS
                - total_characters
            )

            if remaining <= 0:
                break

            if len(item) > remaining:
                item = self.truncate_text(
                    item,
                    remaining,
                )

            if not item:
                break

            items.append(item)
            total_characters += len(item)

        return items

    def retrieve(
        self,
        query: str,
        *,
        language: str = "unknown",
        limit: int = DEFAULT_LIMIT,
        minimum_score: float = DEFAULT_MINIMUM_SCORE,
        minimum_importance: int = DEFAULT_MINIMUM_IMPORTANCE,
        register_access: bool = True,
    ) -> EpisodeRetrievalResult:
        """Zoekt relevante episodes voor een nieuw gebruikersbericht."""
        safe_query = self.normalize_text(
            query,
            "Zoekopdracht",
        )
        safe_language = self.normalize_language(
            language
        )
        safe_limit = self.validate_limit(
            limit
        )

        if not safe_query:
            raise InvalidEpisodeRetrieverInputError(
                "De zoekopdracht is leeg."
            )

        if len(safe_query) > self.MAX_QUERY_CHARACTERS:
            raise InvalidEpisodeRetrieverInputError(
                "De zoekopdracht is te lang."
            )

        if self.is_trivial_query(safe_query):
            result = EpisodeRetrievalResult(
                query=safe_query,
                searched=False,
                found=False,
                completed=True,
                reason=(
                    "De zoekopdracht is te kort of te triviaal "
                    "voor episodische herinneringen."
                ),
            )
            self.last_result = result
            return result

        search_language = (
            safe_language
            if safe_language in {"nl", "tr"}
            else None
        )

        try:
            search_results = self.episodic_memory.search(
                safe_query,
                limit=safe_limit,
                minimum_score=minimum_score,
                minimum_importance=minimum_importance,
                language=search_language,
                register_access=register_access,
            )
        except (
            EpisodicMemoryError,
            ValueError,
        ) as exc:
            raise EpisodeRetrieverError(
                f"Episodisch zoeken mislukt: {exc}"
            ) from exc

        retrieved = [
            self.convert_result(search_result)
            for search_result in search_results
        ]

        context_items = self.build_context_items(
            retrieved
        )

        result = EpisodeRetrievalResult(
            query=safe_query,
            episodes=retrieved,
            context_items=context_items,
            searched=True,
            found=bool(retrieved),
            completed=True,
            reason=(
                "Relevante episodische herinneringen gevonden."
                if retrieved
                else
                "Geen voldoende relevante episodische herinneringen gevonden."
            ),
        )

        self.last_result = result
        return result

    def status(self) -> dict[str, object]:
        """Geeft een compact overzicht van de huidige toestand."""
        return {
            "episode_count": (
                self.episodic_memory.episode_count()
            ),
            "last_completed": bool(
                self.last_result
                and self.last_result.completed
            ),
            "last_searched": bool(
                self.last_result
                and self.last_result.searched
            ),
            "last_found": bool(
                self.last_result
                and self.last_result.found
            ),
            "last_count": (
                self.last_result.count
                if self.last_result
                else 0
            ),
        }


def print_result(
    result: EpisodeRetrievalResult,
) -> None:
    """Toont het zoekresultaat overzichtelijk."""
    print()
    print(f"Zoekopdracht : {result.query}")
    print(f"Gezocht      : {result.searched}")
    print(f"Gevonden     : {result.found}")
    print(f"Aantal       : {result.count}")
    print(f"Voltooid     : {result.completed}")
    print(f"Reden        : {result.reason}")

    for number, episode in enumerate(
        result.episodes,
        start=1,
    ):
        print()
        print(f"Resultaat {number}")
        print(f"ID           : {episode.episode_id}")
        print(f"Onderwerp    : {episode.topic}")
        print(f"Taal         : {episode.language}")
        print(f"Belang       : {episode.importance}")
        print(f"Score        : {episode.score}")
        print(
            "Matches      : "
            + (
                ", ".join(episode.matched_terms)
                if episode.matched_terms
                else "geen"
            )
        )
        print(f"Context      : {episode.context_line}")


def self_test() -> int:
    """Test zoeken, rangschikken, limieten en triviale invoer."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    print("===== Episode Retriever-test =====")

    with TemporaryDirectory() as temporary_directory:
        storage_path = (
            Path(temporary_directory)
            / "episodic_memory_test.json"
        )

        memory = EpisodicMemory(
            storage_path
        )

        preferred = memory.add_episode(
            user_message=(
                "Ik wil voortaan complete bestanden ontvangen "
                "in plaats van losse regels."
            ),
            assistant_message=(
                "Ik zal complete bestanden geven en daarna "
                "de teststappen tonen."
            ),
            summary=(
                "Zeki wil tijdens Bilge-ontwikkeling complete "
                "bestanden in plaats van losse regels."
            ),
            topic="bilge development",
            language="nl",
            keywords=[
                "complete bestanden",
                "bilge",
                "werkwijze",
            ],
            importance=5,
        )

        memory.add_episode(
            user_message=(
                "De Episode Pipeline-test is geslaagd."
            ),
            assistant_message=(
                "De selector en opslag werken correct samen."
            ),
            summary=(
                "De Episode Pipeline is succesvol getest."
            ),
            topic="bilge memory",
            language="nl",
            keywords=[
                "episode pipeline",
                "test",
                "memory",
            ],
            importance=4,
        )

        memory.add_episode(
            user_message=(
                "Bilge için sesli konuşma istiyorum."
            ),
            assistant_message=(
                "Ses katmanını daha sonra güvenli biçimde ekleyeceğiz."
            ),
            summary=(
                "Zeki wil uiteindelijk natuurlijke spraak met Bilge."
            ),
            topic="voice",
            language="tr",
            keywords=[
                "ses",
                "bilge",
                "konuşma",
            ],
            importance=5,
        )

        retriever = EpisodeRetriever(
            episodic_memory=memory
        )

        result = retriever.retrieve(
            "Hoe wil ik bestanden ontvangen tijdens Bilge ontwikkeling?",
            language="nl",
        )

        print_result(result)

        if not result.completed:
            print(
                "FOUT: ophalen is niet voltooid."
            )
            return 1

        if not result.found:
            print(
                "FOUT: relevante episode werd niet gevonden."
            )
            return 1

        if result.episodes[0].episode_id != preferred.id:
            print(
                "FOUT: de beste episode staat niet bovenaan."
            )
            return 1

        if not result.context_items:
            print(
                "FOUT: er zijn geen contextregels opgebouwd."
            )
            return 1

        trivial = retriever.retrieve(
            "Ok",
            language="nl",
        )

        print_result(trivial)

        if trivial.searched:
            print(
                "FOUT: triviale zoekopdracht werd toch uitgevoerd."
            )
            return 1

        if trivial.found:
            print(
                "FOUT: triviale zoekopdracht leverde resultaten."
            )
            return 1

        turkish = retriever.retrieve(
            "Bilge ile sesli konuşma hedefim neydi?",
            language="tr",
        )

        print_result(turkish)

        if not turkish.found:
            print(
                "FOUT: Turkse episode werd niet gevonden."
            )
            return 1

        if turkish.episodes[0].language != "tr":
            print(
                "FOUT: taalfilter werkte niet correct."
            )
            return 1

        status = retriever.status()

        if status["episode_count"] != 3:
            print(
                "FOUT: status bevat een verkeerd aantal episodes."
            )
            return 1

        if not status["last_completed"]:
            print(
                "FOUT: laatste zoekactie is niet voltooid."
            )
            return 1

        print()
        print(
            "Zoeken, rangschikken, taalfilter en "
            "contextopbouw correct getest."
        )

    print("Episode Retriever-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
