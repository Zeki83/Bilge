#!/usr/bin/env python3
"""
Bilge OS - Episodic Memory

Lokaal geheugen voor betekenisvolle gesprekservaringen.

Een episode kan bevatten:
- wat Zeki zei;
- wat Bilge antwoordde;
- een korte samenvatting;
- onderwerp en taal;
- trefwoorden;
- belangscore;
- tijdstippen en gebruiksgegevens.

Deze eerste versie:
- bewaart uitsluitend lokaal op de VPS;
- gebruikt een leesbaar JSON-bestand;
- schrijft wijzigingen atomair weg;
- voorkomt exacte dubbele episodes;
- weigert herkenbare geheime informatie;
- ondersteunt zoeken, ophalen en verwijderen;
- roept geen taalmodel aan;
- voert geen externe acties uit;
- wordt nog niet automatisch door de chat aangeroepen.

Standaard opslag:
    ~/Bilge/Memory/episodic_memory.json
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


EpisodeLanguage = Literal["nl", "tr", "unknown"]


class EpisodicMemoryError(Exception):
    """Basisfout voor problemen binnen Episodic Memory."""


class EpisodeNotFoundError(EpisodicMemoryError):
    """De gevraagde episode bestaat niet."""


class InvalidEpisodeError(EpisodicMemoryError):
    """De aangeleverde episode is ongeldig."""


class SensitiveEpisodeError(EpisodicMemoryError):
    """De episode bevat mogelijk geheime informatie."""


@dataclass(slots=True)
class EpisodeRecord:
    """Eén blijvende gesprekservaring."""

    id: str
    user_message: str
    assistant_message: str
    summary: str

    topic: str = "general"
    language: EpisodeLanguage = "unknown"
    keywords: list[str] = field(default_factory=list)

    importance: int = 3
    source: str = "conversation"
    active: bool = True

    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    last_accessed_at: str = ""
    access_count: int = 0


@dataclass(slots=True)
class EpisodeSearchResult:
    """Eén zoekresultaat met eenvoudige relevantiescore."""

    episode: EpisodeRecord
    score: float
    matched_terms: list[str] = field(default_factory=list)


class EpisodicMemory:
    """Beheert betekenisvolle gesprekservaringen."""

    ALLOWED_LANGUAGES = {
        "nl",
        "tr",
        "unknown",
    }

    MAX_USER_MESSAGE_LENGTH = 8_000
    MAX_ASSISTANT_MESSAGE_LENGTH = 12_000
    MAX_SUMMARY_LENGTH = 1_000
    MAX_TOPIC_LENGTH = 100
    MAX_KEYWORDS = 20
    MAX_KEYWORD_LENGTH = 60

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
            r"\b(?:personal access token|github token)\b"
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
        re.compile(
            r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b",
            re.IGNORECASE,
        ),
    )

    WORD_PATTERN = re.compile(
        r"[A-Za-zÀ-ÖØ-öø-ÿĞğİıŞşÇç0-9_-]+"
    )

    def __init__(
        self,
        storage_path: str | Path | None = None,
    ) -> None:
        self.storage_path = (
            Path(storage_path).expanduser().resolve()
            if storage_path is not None
            else (MEMORY / "episodic_memory.json").resolve()
        )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._episodes: dict[str, EpisodeRecord] = {}
        self._load()

    @staticmethod
    def normalize_text(
        value: str,
        field_name: str,
    ) -> str:
        """Normaliseert tekst en controleert het datatype."""
        if not isinstance(value, str):
            raise InvalidEpisodeError(
                f"{field_name} moet tekst zijn."
            )

        return " ".join(value.strip().split())

    @staticmethod
    def validate_length(
        value: str,
        maximum: int,
        field_name: str,
    ) -> None:
        """Controleert de maximale tekstlengte."""
        if len(value) > maximum:
            raise InvalidEpisodeError(
                f"{field_name} is te lang. "
                f"Maximum: {maximum} tekens."
            )

    def ensure_safe_text(
        self,
        value: str,
        field_name: str,
        *,
        maximum: int,
    ) -> str:
        """Normaliseert tekst en weigert herkenbare geheimen."""
        normalized = self.normalize_text(
            value,
            field_name,
        )

        self.validate_length(
            normalized,
            maximum,
            field_name,
        )

        if any(
            pattern.search(normalized)
            for pattern in self.SENSITIVE_PATTERNS
        ):
            raise SensitiveEpisodeError(
                f"{field_name} lijkt geheime informatie te bevatten "
                "en wordt daarom niet opgeslagen."
            )

        return normalized

    def validate_language(
        self,
        language: str,
    ) -> EpisodeLanguage:
        """Controleert de taalcode."""
        normalized = self.normalize_text(
            language,
            "Taal",
        ).casefold()

        if normalized not in self.ALLOWED_LANGUAGES:
            raise InvalidEpisodeError(
                "Ongeldige taal. Gebruik: nl, tr of unknown."
            )

        return normalized  # type: ignore[return-value]

    @staticmethod
    def validate_importance(
        importance: int,
    ) -> int:
        """Beperkt belang tot een waarde van 1 tot en met 5."""
        if not isinstance(importance, int):
            raise InvalidEpisodeError(
                "importance moet een geheel getal zijn."
            )

        if importance < 1 or importance > 5:
            raise InvalidEpisodeError(
                "importance moet tussen 1 en 5 liggen."
            )

        return importance

    def clean_keywords(
        self,
        keywords: list[str] | None,
    ) -> list[str]:
        """Normaliseert en dedupliceert trefwoorden."""
        if keywords is None:
            return []

        if not isinstance(keywords, list):
            raise InvalidEpisodeError(
                "keywords moet een lijst zijn."
            )

        if len(keywords) > self.MAX_KEYWORDS:
            raise InvalidEpisodeError(
                f"Er mogen maximaal {self.MAX_KEYWORDS} "
                "trefwoorden worden opgeslagen."
            )

        cleaned: list[str] = []
        seen: set[str] = set()

        for keyword in keywords:
            safe_keyword = self.ensure_safe_text(
                keyword,
                "Trefwoord",
                maximum=self.MAX_KEYWORD_LENGTH,
            ).casefold()

            if not safe_keyword:
                continue

            if safe_keyword in seen:
                continue

            seen.add(safe_keyword)
            cleaned.append(safe_keyword)

        return cleaned

    @staticmethod
    def duplicate_key(
        user_message: str,
        assistant_message: str,
    ) -> tuple[str, str]:
        """Maakt een sleutel voor exacte dubbele episodes."""
        return (
            user_message.casefold(),
            assistant_message.casefold(),
        )

    def _load(self) -> None:
        """Laadt bestaande episodes vanaf schijf."""
        if not self.storage_path.exists():
            self._episodes = {}
            return

        try:
            raw_data = json.loads(
                self.storage_path.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as exc:
            raise EpisodicMemoryError(
                "Episodic Memory bevat ongeldige JSON: "
                f"{self.storage_path}"
            ) from exc
        except OSError as exc:
            raise EpisodicMemoryError(
                "Episodic Memory kon niet worden gelezen: "
                f"{self.storage_path}"
            ) from exc

        if not isinstance(raw_data, dict):
            raise EpisodicMemoryError(
                "Episodic Memory moet een JSON-object bevatten."
            )

        episodes_data = raw_data.get("episodes", {})

        if not isinstance(episodes_data, dict):
            raise EpisodicMemoryError(
                "Het veld 'episodes' is ongeldig."
            )

        loaded: dict[str, EpisodeRecord] = {}

        for episode_id, episode_data in episodes_data.items():
            if not isinstance(episode_data, dict):
                continue

            try:
                loaded[episode_id] = EpisodeRecord(
                    **episode_data
                )
            except TypeError as exc:
                raise EpisodicMemoryError(
                    f"Episode '{episode_id}' heeft een "
                    "ongeldige structuur."
                ) from exc

        self._episodes = loaded

    def _save(self) -> None:
        """Schrijft episodes atomair naar schijf."""
        payload = {
            "version": 1,
            "updated_at": datetime.now(UTC).isoformat(),
            "episodes": {
                episode_id: asdict(episode)
                for episode_id, episode
                in self._episodes.items()
            },
        }

        temporary_path: Path | None = None

        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.storage_path.parent,
                prefix=".episodic_memory_",
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
                temporary_path = Path(
                    temporary_file.name
                )

            temporary_path.replace(
                self.storage_path
            )

        except OSError as exc:
            if temporary_path and temporary_path.exists():
                temporary_path.unlink(
                    missing_ok=True
                )

            raise EpisodicMemoryError(
                "Episodic Memory kon niet worden opgeslagen: "
                f"{self.storage_path}"
            ) from exc

    def find_duplicate(
        self,
        user_message: str,
        assistant_message: str,
    ) -> EpisodeRecord | None:
        """Zoekt een actieve exacte dubbele episode."""
        wanted_key = self.duplicate_key(
            user_message,
            assistant_message,
        )

        for episode in self._episodes.values():
            if (
                episode.active
                and self.duplicate_key(
                    episode.user_message,
                    episode.assistant_message,
                ) == wanted_key
            ):
                return episode

        return None

    def add_episode(
        self,
        user_message: str,
        assistant_message: str,
        summary: str,
        *,
        topic: str = "general",
        language: str = "unknown",
        keywords: list[str] | None = None,
        importance: int = 3,
        source: str = "conversation",
    ) -> EpisodeRecord:
        """Slaat één betekenisvolle gesprekservaring op."""
        safe_user_message = self.ensure_safe_text(
            user_message,
            "Gebruikersbericht",
            maximum=self.MAX_USER_MESSAGE_LENGTH,
        )
        safe_assistant_message = self.ensure_safe_text(
            assistant_message,
            "Assistentantwoord",
            maximum=self.MAX_ASSISTANT_MESSAGE_LENGTH,
        )
        safe_summary = self.ensure_safe_text(
            summary,
            "Samenvatting",
            maximum=self.MAX_SUMMARY_LENGTH,
        )
        safe_topic = self.ensure_safe_text(
            topic,
            "Onderwerp",
            maximum=self.MAX_TOPIC_LENGTH,
        ).casefold()
        safe_source = self.ensure_safe_text(
            source,
            "Bron",
            maximum=100,
        )
        safe_language = self.validate_language(
            language
        )
        safe_importance = self.validate_importance(
            importance
        )
        safe_keywords = self.clean_keywords(
            keywords
        )

        if not safe_user_message:
            raise InvalidEpisodeError(
                "Het gebruikersbericht mag niet leeg zijn."
            )

        if not safe_assistant_message:
            raise InvalidEpisodeError(
                "Het assistentantwoord mag niet leeg zijn."
            )

        if not safe_summary:
            raise InvalidEpisodeError(
                "De samenvatting mag niet leeg zijn."
            )

        duplicate = self.find_duplicate(
            safe_user_message,
            safe_assistant_message,
        )

        if duplicate is not None:
            return duplicate

        episode = EpisodeRecord(
            id=str(uuid.uuid4()),
            user_message=safe_user_message,
            assistant_message=safe_assistant_message,
            summary=safe_summary,
            topic=safe_topic or "general",
            language=safe_language,
            keywords=safe_keywords,
            importance=safe_importance,
            source=safe_source or "conversation",
        )

        self._episodes[episode.id] = episode
        self._save()
        return episode

    def get_episode(
        self,
        episode_id: str,
        *,
        register_access: bool = False,
    ) -> EpisodeRecord:
        """Geeft één episode terug op basis van ID."""
        normalized_id = self.normalize_text(
            episode_id,
            "Episode ID",
        )

        if normalized_id not in self._episodes:
            raise EpisodeNotFoundError(
                f"Episode '{normalized_id}' is niet gevonden."
            )

        episode = self._episodes[normalized_id]

        if register_access:
            episode.access_count += 1
            episode.last_accessed_at = (
                datetime.now(UTC).isoformat()
            )
            episode.updated_at = (
                datetime.now(UTC).isoformat()
            )
            self._save()

        return episode

    def list_episodes(
        self,
        *,
        topic: str | None = None,
        language: str | None = None,
        active_only: bool = True,
        minimum_importance: int = 1,
    ) -> list[EpisodeRecord]:
        """Geeft gefilterde episodes terug."""
        safe_minimum = self.validate_importance(
            minimum_importance
        )

        safe_topic: str | None = None
        safe_language: EpisodeLanguage | None = None

        if topic is not None:
            safe_topic = self.normalize_text(
                topic,
                "Onderwerp",
            ).casefold()

        if language is not None:
            safe_language = self.validate_language(
                language
            )

        episodes = list(
            self._episodes.values()
        )

        if active_only:
            episodes = [
                episode
                for episode in episodes
                if episode.active
            ]

        if safe_topic is not None:
            episodes = [
                episode
                for episode in episodes
                if episode.topic == safe_topic
            ]

        if safe_language is not None:
            episodes = [
                episode
                for episode in episodes
                if episode.language == safe_language
            ]

        episodes = [
            episode
            for episode in episodes
            if episode.importance >= safe_minimum
        ]

        return sorted(
            episodes,
            key=lambda episode: (
                episode.importance,
                episode.updated_at,
            ),
            reverse=True,
        )

    @classmethod
    def tokenize(
        cls,
        value: str,
    ) -> set[str]:
        """Zet tekst om in eenvoudige zoektermen."""
        return {
            match.group(0).casefold()
            for match in cls.WORD_PATTERN.finditer(value)
            if len(match.group(0)) >= 2
        }

    def score_episode(
        self,
        episode: EpisodeRecord,
        query_terms: set[str],
    ) -> EpisodeSearchResult:
        """Berekent eenvoudige lexicale relevantie."""
        summary_terms = self.tokenize(
            episode.summary
        )
        topic_terms = self.tokenize(
            episode.topic
        )
        keyword_terms = {
            keyword.casefold()
            for keyword in episode.keywords
        }
        user_terms = self.tokenize(
            episode.user_message
        )
        assistant_terms = self.tokenize(
            episode.assistant_message
        )

        matched_terms: set[str] = set()
        score = 0.0

        for term in query_terms:
            matched = False

            if term in keyword_terms:
                score += 5.0
                matched = True

            if term in topic_terms:
                score += 4.0
                matched = True

            if term in summary_terms:
                score += 3.0
                matched = True

            if term in user_terms:
                score += 2.0
                matched = True

            if term in assistant_terms:
                score += 1.0
                matched = True

            if matched:
                matched_terms.add(term)

        if matched_terms:
            score += episode.importance * 0.5
            score += min(
                episode.access_count,
                10,
            ) * 0.1

        return EpisodeSearchResult(
            episode=episode,
            score=round(score, 3),
            matched_terms=sorted(
                matched_terms
            ),
        )

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        minimum_score: float = 1.0,
        minimum_importance: int = 1,
        topic: str | None = None,
        language: str | None = None,
        register_access: bool = False,
    ) -> list[EpisodeSearchResult]:
        """Zoekt relevante episodes."""
        normalized_query = self.normalize_text(
            query,
            "Zoekopdracht",
        )

        if not normalized_query:
            return []

        if not isinstance(limit, int) or limit < 1:
            raise ValueError(
                "limit moet een positief geheel getal zijn."
            )

        if not isinstance(
            minimum_score,
            (int, float),
        ):
            raise ValueError(
                "minimum_score moet numeriek zijn."
            )

        query_terms = self.tokenize(
            normalized_query
        )

        if not query_terms:
            return []

        candidates = self.list_episodes(
            topic=topic,
            language=language,
            active_only=True,
            minimum_importance=minimum_importance,
        )

        scored = [
            self.score_episode(
                episode,
                query_terms,
            )
            for episode in candidates
        ]

        results = [
            result
            for result in scored
            if result.score >= float(
                minimum_score
            )
        ]

        results.sort(
            key=lambda result: (
                result.score,
                result.episode.importance,
                result.episode.updated_at,
            ),
            reverse=True,
        )

        selected = results[:limit]

        if register_access and selected:
            now = datetime.now(UTC).isoformat()

            for result in selected:
                result.episode.access_count += 1
                result.episode.last_accessed_at = now
                result.episode.updated_at = now

            self._save()

        return selected

    def update_episode(
        self,
        episode_id: str,
        *,
        summary: str | None = None,
        topic: str | None = None,
        keywords: list[str] | None = None,
        importance: int | None = None,
    ) -> EpisodeRecord:
        """Past metadata van een bestaande episode aan."""
        episode = self.get_episode(
            episode_id
        )

        if summary is not None:
            safe_summary = self.ensure_safe_text(
                summary,
                "Samenvatting",
                maximum=self.MAX_SUMMARY_LENGTH,
            )

            if not safe_summary:
                raise InvalidEpisodeError(
                    "De samenvatting mag niet leeg zijn."
                )

            episode.summary = safe_summary

        if topic is not None:
            episode.topic = (
                self.ensure_safe_text(
                    topic,
                    "Onderwerp",
                    maximum=self.MAX_TOPIC_LENGTH,
                ).casefold()
                or "general"
            )

        if keywords is not None:
            episode.keywords = self.clean_keywords(
                keywords
            )

        if importance is not None:
            episode.importance = (
                self.validate_importance(
                    importance
                )
            )

        episode.updated_at = (
            datetime.now(UTC).isoformat()
        )
        self._save()
        return episode

    def deactivate_episode(
        self,
        episode_id: str,
    ) -> EpisodeRecord:
        """Deactiveert een episode zonder definitieve verwijdering."""
        episode = self.get_episode(
            episode_id
        )
        episode.active = False
        episode.updated_at = (
            datetime.now(UTC).isoformat()
        )
        self._save()
        return episode

    def reactivate_episode(
        self,
        episode_id: str,
    ) -> EpisodeRecord:
        """Activeert een gedeactiveerde episode opnieuw."""
        episode = self.get_episode(
            episode_id
        )
        episode.active = True
        episode.updated_at = (
            datetime.now(UTC).isoformat()
        )
        self._save()
        return episode

    def delete_episode(
        self,
        episode_id: str,
    ) -> EpisodeRecord:
        """Verwijdert een episode permanent."""
        normalized_id = self.normalize_text(
            episode_id,
            "Episode ID",
        )

        if normalized_id not in self._episodes:
            raise EpisodeNotFoundError(
                f"Episode '{normalized_id}' is niet gevonden."
            )

        deleted = self._episodes.pop(
            normalized_id
        )
        self._save()
        return deleted

    def episode_count(
        self,
        *,
        active_only: bool = True,
    ) -> int:
        """Geeft het aantal episodes terug."""
        return len(
            self.list_episodes(
                active_only=active_only
            )
        )


def self_test() -> int:
    """Test Episodic Memory in een tijdelijke map."""
    from tempfile import TemporaryDirectory

    print("===== Episodic Memory-test =====")

    with TemporaryDirectory() as temporary_directory:
        test_file = (
            Path(temporary_directory)
            / "episodic_memory_test.json"
        )

        memory = EpisodicMemory(
            test_file
        )

        first = memory.add_episode(
            user_message=(
                "Ik wil voortaan complete bestanden ontvangen."
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
                "werkwijze",
                "bilge",
            ],
            importance=5,
        )

        second = memory.add_episode(
            user_message=(
                "De Emotion Controller-test is geslaagd."
            ),
            assistant_message=(
                "Mooi, de test is geslaagd. We kunnen verder."
            ),
            summary=(
                "De Emotion Controller is succesvol getest."
            ),
            topic="bilge development",
            language="nl",
            keywords=[
                "emotion controller",
                "test",
            ],
            importance=4,
        )

        duplicate = memory.add_episode(
            user_message=(
                "Ik wil voortaan complete bestanden ontvangen."
            ),
            assistant_message=(
                "Ik zal complete bestanden geven en daarna "
                "de teststappen tonen."
            ),
            summary="Dubbele episode.",
            topic="duplicate",
            language="nl",
            importance=1,
        )

        if duplicate.id != first.id:
            print(
                "FOUT: dubbele episode werd niet herkend."
            )
            return 1

        results = memory.search(
            "complete bestanden Bilge",
            register_access=True,
        )

        if not results:
            print(
                "FOUT: zoeken leverde geen resultaat op."
            )
            return 1

        if results[0].episode.id != first.id:
            print(
                "FOUT: de meest relevante episode staat niet bovenaan."
            )
            return 1

        accessed = memory.get_episode(
            first.id
        )

        if accessed.access_count != 1:
            print(
                "FOUT: gebruiksteller werd niet bijgewerkt."
            )
            return 1

        memory.update_episode(
            second.id,
            importance=5,
            keywords=[
                "emotion controller",
                "geslaagde test",
            ],
        )

        memory.deactivate_episode(
            second.id
        )

        if memory.episode_count() != 1:
            print(
                "FOUT: gedeactiveerde episode bleef actief."
            )
            return 1

        memory.reactivate_episode(
            second.id
        )

        reloaded = EpisodicMemory(
            test_file
        )

        if reloaded.episode_count() != 2:
            print(
                "FOUT: episodes werden niet correct herladen."
            )
            return 1

        try:
            memory.add_episode(
                user_message=(
                    "Onthoud mijn GitHub-token: "
                    "ghp_abcdefghijklmnopqrstuvwxyz123456"
                ),
                assistant_message=(
                    "Ik onthoud de token."
                ),
                summary=(
                    "GitHub-token onthouden."
                ),
            )
        except SensitiveEpisodeError:
            print(
                "Geheime informatie correct geweigerd."
            )
        else:
            print(
                "FOUT: geheime informatie werd opgeslagen."
            )
            return 1

        deleted = memory.delete_episode(
            second.id
        )

        if deleted.id != second.id:
            print(
                "FOUT: episode werd niet correct verwijderd."
            )
            return 1

        print(
            f"Actieve episodes: {memory.episode_count()}"
        )
        print(
            "Opslaan, zoeken, scoren en herladen correct getest."
        )

    print("Episodic Memory-test geslaagd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test())
