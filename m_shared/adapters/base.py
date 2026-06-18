"""Abstract base class for platform survey adapters."""

from abc import ABC, abstractmethod
from typing import NamedTuple

from m_shared.models.response import Response
from m_shared.models.survey import Survey


class ResponseExport(NamedTuple):
    """One adapter-emitted response export.

    Different platforms accept different file formats from their admin-UI
    importers (LimeSurvey: VV / TSV; Qualtrics: CSV; future adapters: their
    own). The adapter knows which format the platform's importer expects and
    returns the bytes plus the metadata the calling layer needs to deliver
    them as a browser download.
    """

    content: bytes
    """File payload as encoded bytes (UTF-8, with BOM where the platform expects it)."""

    media_type: str
    """RFC 7231 media type, used verbatim as the HTTP ``Content-Type`` header."""

    filename_suffix: str
    """Trailing portion of the filename INCLUDING the leading connector, so
    the adapter chooses the joining character. E.g. LimeSurvey uses
    ``"_vv.csv"`` to match LS's own ``vvexport_{sid}.csv`` naming style;
    Qualtrics uses ``".csv"`` for a plain extension. The endpoint composes
    ``responses-{platform}-{sid}-{ts}{suffix}`` (no inserted character)."""


class SurveyAdapter(ABC):
    """Platform-agnostic interface for importing, exporting, and submitting surveys.

    Each concrete adapter handles one survey platform (LimeSurvey, Qualtrics, etc.)
    and translates between that platform's format and the internal Survey model.

    Consumers should call `capabilities()` before invoking optional methods like
    `submit_responses()` to avoid NotImplementedError at runtime.
    """

    @abstractmethod
    def import_survey(self, raw: str) -> Survey:
        """Parse a platform-specific survey format and return an internal Survey.

        Args:
            raw: Raw survey content as a string (XML, JSON, etc.).

        Returns:
            Survey: The parsed survey in the internal model format.

        Raises:
            ValueError: If the raw content is invalid or cannot be parsed.
        """

    @abstractmethod
    def export_survey(self, survey: Survey) -> str:
        """Serialize an internal Survey to the platform-specific format.

        Args:
            survey: The survey to export.

        Returns:
            str: The serialized survey content (XML, JSON, etc.).
        """

    @abstractmethod
    def capabilities(self) -> set[str]:
        """Return the set of operations this adapter supports.

        Defined capability strings: "import", "export", "submit", "create",
        "api_create", "responses_export".

        Returns:
            set[str]: Supported capability identifiers.
        """

    def submit_responses(self, survey_id: str, responses: list[Response]) -> None:
        """Submit responses to the originating platform.

        Override in adapters that support response write-back.

        Args:
            survey_id: Platform-specific identifier for the target survey.
            responses: Responses to submit.

        Raises:
            NotImplementedError: Always — override in subclasses that support submission.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support response submission."
        )

    def create_survey(self, survey: Survey) -> str:
        """Push survey to platform API or export to file.

        Returns:
            Platform-assigned survey ID, or serialised file content for
            adapters without a write API.

        Raises:
            NotImplementedError: If not overridden by subclass.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support create_survey()")

    def fetch_survey(self, survey_id: str) -> "Survey":
        """Fetch a survey from the platform API by ID (optional override)."""
        raise NotImplementedError(f"{type(self).__name__} does not support fetch_survey")

    def export_responses(self, survey: Survey, responses: list[Response]) -> ResponseExport:
        """Render responses in the file format the platform's admin importer accepts.

        Override in adapters that support file-based response import. The
        returned ``ResponseExport`` SHALL be importable by the originating
        platform's admin UI without further transformation. The format is
        platform-specific and need not be CSV — LimeSurvey's VV importer
        wants TSV with two header rows; Qualtrics wants its own 3-row CSV.

        Args:
            survey: The internal survey, used for column order and per-question metadata.
            responses: The respondent's answers as internal Response objects.

        Returns:
            ResponseExport: ``(content, media_type, filename_suffix)``.

        Raises:
            NotImplementedError: Override in subclasses that advertise the
                ``responses_export`` capability.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support 'responses_export'. "
            "Check capabilities() before invoking."
        )
