#!/usr/bin/env python3
"""
Bilge OS - Long Memory Retriever

Veilige zoeklaag voor blijvende herinneringen.

Deze module:
- zoekt uitsluitend in lokale Long Memory;
- gebruikt alleen actieve herinneringen;
- rangschikt voorkeuren, doelen, werkwijzen en feiten;
- geeft compacte contextregels terug voor PromptBuilder;
- beperkt het aantal resultaten en de totale tekstlengte;
- zoekt niet bij triviale of zeer korte berichten;
- wijzigt of verwijdert geen herinneringen;
- maakt geen verbinding met externe diensten.

Deze versie wordt nog niet automatisch door ConversationEngine gebruikt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bilge.long_memory import (
    LongMemory,
    LongMemoryError,
    MemoryRecord,
)


class LongMemoryRetrieverError(Exception):
    """Basisfout voor problemen binnen Long Memory Retriever."""


class InvalidLongMemoryRetrieverInputError(
    LongMemoryRetrieverError
):
    """De aangeleverde zoekopdracht is ongeldig."""


@dataclass(slots=True)
class RetrievedLongMemory:
    """Compacte representatie van één relevante herinnering."""

    memory_id: str
    category: str
    content: str
    context: str
    score: float
    matched_terms: list[str] = field(default_factory=list)

    @property
    def context_line(self) -> str:
        """Geeft één compacte promptregel terug."""
        label = {
            "preference": "Voorkeur",
            "goal": "Doel",
            "workflow": "Werkwijze",
            "decision": "Besluit",
            "fact": "Feit",
            "other": "Herinnering",
        }.get(
            self.category,
            "Herinnering",
        )

        if self.context:
            return (
                f"[{label}; score {self.score}] "
                f"{self.content} "
                f"(Context: {self.context})"
            )

        return (
            f"[{label}; score {self.score}] "
            f"{self.content}"
        )


@dataclass(slots=True)
class LongMemoryRetrievalResult:
    """Resultaat van één zoekactie in Long Memory."""

    query: str
    memories: list[RetrievedLongMemory] = field(
        default_factory=list
    )
    context_items: list[str] = field(
        default_factory=list
    )

    searched: bool = False
    found: bool = False
    completed: bool = False
    reason: str = ""

    @property
    def count(self) -> int:
        """Geeft het aantal gevonden herinneringen terug."""
        return len(self.memories)


class LongMemoryRetriever:
    """Haalt relevante blijvende herinneringen op."""

    DEFAULT_LIMIT = 4
    MAX_LIMIT = 6
    DEFAULT_MINIMUM_SCORE = 2.0

    MIN_QUERY_CHARACTERS = 8
    MAX_QUERY_CHARACTERS = 4_000

    MAX_CONTEXT_ITEM_CHARACTERS = 420
    MAX_TOTAL_CONTEXT_CHARACTERS = 1_400

    CATEGORY_WEIGHTS = {
        "preference": 2.0,
        "workflow": 1.8,
        "goal": 1.6,
        "decision": 1.5,
        "fact": 1.2,
        "other": 1.0,
    }

    STOP_WORDS = {
        "de",
        "het",
        "een",
        "en",
        "of",
        "ik",
        "je",
        "jij",
        "mijn",
        "jouw",
        "dat",
        "dit",
        "die",
        "wat",
        "hoe",
        "wil",
        "moet",
        "met",
        "voor",
        "van",
        "naar",
        "in",
        "op",
        "om",
        "te",
        "is",
        "zijn",
        "was",
        "waren",
        "ben",
        "heb",
        "heeft",
        "als",
        "bij",
        "dan",
        "nog",
        "nu",
        "the",
        "a",
        "an",
        "and",
        "or",
        "my",
        "your",
        "what",
        "how",
        "with",
        "for",
        "to",
        "is",
        "are",
        "benim",
        "senin",
        "nasıl",
        "ne",
        "ve",
        "veya",
        "bir",
        "bu",
        "şu",
        "ile",
        "için",
        "mi",
        "mı",
        "mu",
        "mü",
    }

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
        "ga verder",
        "doorgaan",
        "kom maar op",
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
        long_memory: LongMemory | None = None,
    ) -> None:
        self.long_memory = long_memory or LongMemory()
        self.last_result: LongMemoryRetrievalResult | None = None

    @staticmethod
    def normalize_text(
        value: str,
        field_name: str,
    ) -> str:
        """Normaliseert tekst en controleert het datatype."""
        if not isinstance(value, str):
            raise InvalidLongMemoryRetrieverInputError(
                f"{field_name} moet tekst zijn."
            )

        return " ".join(value.strip().split())

    def validate_limit(
        self,
        limit: int,
    ) -> int:
        """Controleert en begrenst het resultaatlimiet."""
        if not isinstance(limit, int):
            raise InvalidLongMemoryRetrieverInputError(
                "limit moet een geheel getal zijn."
            )

        if limit < 1:
            raise InvalidLongMemoryRetrieverInputError(
                "limit moet minimaal 1 zijn."
            )

        return min(
            limit,
            self.MAX_LIMIT,
        )

    def is_trivial_query(
        self,
        query: str,
    ) -> bool:
        """Controleert of zoeken waarschijnlijk geen waarde heeft."""
        normalized = query.strip(
            " .,!?:;"
        ).casefold()

        if normalized in self.TRIVIAL_QUERIES:
            return True

        return (
            len(normalized.split()) <= 2
            and len(normalized) < self.MIN_QUERY_CHARACTERS
        )

    @staticmethod
    def truncate_text(
        value: str,
        maximum: int,
    ) -> str:
        """Kort tekst veilig af."""
        if len(value) <= maximum:
            return value

        return value[: maximum - 3].rstrip() + "..."

    def tokenize(
        self,
        value: str,
    ) -> list[str]:
        """Maakt bruikbare zoektermen van tekst."""
        words = re.findall(
            r"[0-9A-Za-zÀ-ÖØ-öø-ÿĞğİıŞşÇç]+",
            value.casefold(),
        )

        return [
            word
            for word in words
            if (
                len(word) >= 3
                and word not in self.STOP_WORDS
            )
        ]

    @staticmethod
    def contains_phrase(
        phrase: str,
        content: str,
    ) -> bool:
        """Controleert op een volledige genormaliseerde woordgroep."""
        normalized_phrase = " ".join(
            phrase.casefold().split()
        )
        normalized_content = " ".join(
            content.casefold().split()
        )

        return (
            bool(normalized_phrase)
            and normalized_phrase in normalized_content
        )

    def score_record(
        self,
        query: str,
        query_terms: list[str],
        record: MemoryRecord,
    ) -> tuple[float, list[str]]:
        """Berekent een eenvoudige uitlegbare relevantiescore."""
        searchable_content = (
            f"{record.content} {record.context}"
        ).casefold()

        matched_terms = sorted(
            {
                term
                for term in query_terms
                if term in searchable_content
            }
        )

        score = 0.0

        score += len(matched_terms) * 2.0

        if self.contains_phrase(
            query,
            record.content,
        ):
            score += 5.0

        if self.contains_phrase(
            record.content,
            query,
        ):
            score += 3.0

        score += self.CATEGORY_WEIGHTS.get(
            record.category,
            1.0,
        )

        content_terms = set(
            self.tokenize(record.content)
        )

        if query_terms:
            overlap_ratio = (
                len(set(query_terms).intersection(content_terms))
                / len(set(query_terms))
            )
            score += overlap_ratio * 3.0

        return round(score, 2), matched_terms

    def retrieve_candidates(
        self,
        query: str,
    ) -> list[tuple[MemoryRecord, float, list[str]]]:
        """Rangschikt alle actieve herinneringen."""
        query_terms = self.tokenize(query)

        candidates: list[
            tuple[MemoryRecord, float, list[str]]
        ] = []

        try:
            records = self.long_memory.list_memories(
                active_only=True
            )
        except LongMemoryError as exc:
            raise LongMemoryRetrieverError(
                f"Long Memory kon niet worden gelezen: {exc}"
            ) from exc

        for record in records:
            score, matched_terms = self.score_record(
                query,
                query_terms,
                record,
            )

            candidates.append(
                (
                    record,
                    score,
                    matched_terms,
                )
            )

        return sorted(
            candidates,
            key=lambda item: (
                item[1],
                item[0].updated_at,
            ),
            reverse=True,
        )

    def convert_record(
        self,
        record: MemoryRecord,
        score: float,
        matched_terms: list[str],
    ) -> RetrievedLongMemory:
        """Zet één geheugenrecord om naar compacte context."""
        return RetrievedLongMemory(
            memory_id=record.id,
            category=record.category,
            content=self.truncate_text(
                record.content,
                self.MAX_CONTEXT_ITEM_CHARACTERS,
            ),
            context=self.truncate_text(
                record.context,
                self.MAX_CONTEXT_ITEM_CHARACTERS,
            ),
            score=score,
            matched_terms=matched_terms,
        )

    def build_context_items(
        self,
        memories: list[RetrievedLongMemory],
    ) -> list[str]:
        """Bouwt context binnen een vaste totale tekenlimiet."""
        items: list[str] = []
        total_characters = 0

        for memory in memories:
            item = memory.context_line

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
        limit: int = DEFAULT_LIMIT,
        minimum_score: float = DEFAULT_MINIMUM_SCORE,
    ) -> LongMemoryRetrievalResult:
        """Zoekt relevante actieve blijvende herinneringen."""
        safe_query = self.normalize_text(
            query,
            "Zoekopdracht",
        )
        safe_limit = self.validate_limit(
            limit
        )

        if not safe_query:
            raise InvalidLongMemoryRetrieverInputError(
                "De zoekopdracht is leeg."
            )

        if len(safe_query) > self.MAX_QUERY_CHARACTERS:
            raise InvalidLongMemoryRetrieverInputError(
                "De zoekopdracht is te lang."
            )

        if not isinstance(
            minimum_score,
            (int, float),
        ):
            raise InvalidLongMemoryRetrieverInputError(
                "minimum_score moet een getal zijn."
            )

        if minimum_score < 0:
            raise InvalidLongMemoryRetrieverInputError(
                "minimum_score mag niet negatief zijn."
            )

        if self.is_trivial_query(safe_query):
            result = LongMemoryRetrievalResult(
                query=safe_query,
                searched=False,
                found=False,
                completed=True,
                reason=(
                    "De zoekopdracht is te kort of te triviaal "
                    "voor Long Memory."
                ),
            )
            self.last_result = result
            return result

        candidates = self.retrieve_candidates(
            safe_query
        )

        selected = [
            self.convert_record(
                record,
                score,
                matched_terms,
            )
            for record, score, matched_terms in candidates
            if score >= minimum_score
        ][:safe_limit]

        context_items = self.build_context_items(
            selected
        )

        result = LongMemoryRetrievalResult(
            query=safe_query,
            memories=selected,
            context_items=context_items,
            searched=True,
            found=bool(selected),
            completed=True,
            reason=(
                "Relevante blijvende herinneringen gevonden."
                if selected
                else
                "Geen voldoende relevante blijvende "
                "herinneringen gevonden."
            ),
        )

        self.last_result = result
        return result

    def status(self) -> dict[str, object]:
        """Geeft een compact overzicht van de huidige toestand."""
        return {
            "active_memory_count": (
                self.long_memory.memory_count(
                    active_only=True
                )
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
    result: LongMemoryRetrievalResult,
) -> None:
    """Toont het zoekresultaat overzichtelijk."""
    print()
    print(f"Zoekopdracht : {result.query}")
    print(f"Gezocht      : {result.searched}")
    print(f"Gevonden     : {result.found}")
    print(f"Aantal       : {result.count}")
    print(f"Voltooid     : {result.completed}")
    print(f"Reden        : {result.reason}")

    for number, memory in enumerate(
        result.memories,
        start=1,
    ):
        print()
        print(f"Resultaat {number}")
        print(f"ID           : {memory.memory_id}")
        print(f"Categorie    : {memory.category}")
        print(f"Score        : {memory.score}")
        print(
            "Matches      : "
            + (
                ", ".join(memory.matched_terms)
                if memory.matched_terms
                else "geen"
            )
        )
        print(f"Inhoud       : {memory.content}")
        print(f"Context      : {memory.context}")
        print(f"Promptregel  : {memory.context_line}")


def self_test() -> int:
    """Test zoeken, rangschikken, context en triviale invoer."""
    from pathlib import Path
    from tempfile import TemporaryDirectory

    print("===== Long Memory Retriever-test =====")

    with TemporaryDirectory() as temporary_directory:
        storage_path = (
            Path(temporary_directory)
            / "long_memory_test.json"
        )

        memory = LongMemory(
            storage_path
        )

        preferred = memory.add_memory(
            "preference",
            (
                "Zeki wil complete bestanden ontvangen "
                "in plaats van losse regels."
            ),
            context=(
                "Vaste werkwijze tijdens het bouwen "
                "van Bilge OS."
            ),
        )

        memory.add_memory(
            "workflow",
            (
                "Na iedere geslaagde module wordt eerst "
                "getest en daarna een GitHub-snapshot gemaakt."
            ),
            context="Ontwikkelproces van Bilge OS.",
        )

        memory.add_memory(
            "goal",
            (
                "Bilge moet uiteindelijk natuurlijke spraak, "
                "een avatar en een eigen app krijgen."
            ),
            context="Langetermijndoel.",
        )

        inactive = memory.add_memory(
            "fact",
            "Zeki gebruikt uitsluitend losse coderegels.",
            context="Verouderde testinformatie.",
        )

        memory.deactivate_memory(
            inactive.id
        )

        retriever = LongMemoryRetriever(
            long_memory=memory
        )

        result = retriever.retrieve(
            (
                "Hoe wil Zeki dat code en bestanden "
                "worden aangeleverd?"
            )
        )

        print_result(result)

        if not result.completed:
            print(
                "FOUT: ophalen is niet voltooid."
            )
            return 1

        if not result.found:
            print(
                "FOUT: relevante voorkeur werd niet gevonden."
            )
            return 1

        if result.memories[0].memory_id != preferred.id:
            print(
                "FOUT: de beste herinnering staat niet bovenaan."
            )
            return 1

        if not result.context_items:
            print(
                "FOUT: er zijn geen contextregels opgebouwd."
            )
            return 1

        if any(
            item.memory_id == inactive.id
            for item in result.memories
        ):
            print(
                "FOUT: gedeactiveerde herinnering werd opgehaald."
            )
            return 1

        workflow_result = retriever.retrieve(
            (
                "Wat doen we nadat een Bilge-module "
                "succesvol is getest?"
            )
        )

        print_result(workflow_result)

        if not workflow_result.found:
            print(
                "FOUT: relevante werkwijze werd niet gevonden."
            )
            return 1

        if workflow_result.memories[0].category != "workflow":
            print(
                "FOUT: werkwijze staat niet bovenaan."
            )
            return 1

        trivial = retriever.retrieve(
            "Ok"
        )

        print_result(trivial)

        if trivial.searched:
            print(
                "FOUT: triviale zoekopdracht werd uitgevoerd."
            )
            return 1

        if trivial.found:
            print(
                "FOUT: triviale zoekopdracht leverde resultaten."
            )
            return 1

        status = retriever.status()

        if status["active_memory_count"] != 3:
            print(
                "FOUT: status bevat een verkeerd "
                "aantal actieve herinneringen."
            )
            return 1

        if not status["last_completed"]:
            print(
                "FOUT: laatste zoekactie is niet voltooid."
            )
            return 1

        print()
        print(
            "Zoeken, rangschikken, actieve filtering en "
            "contextopbouw correct getest."
        )

    print("Long Memory Retriever-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
