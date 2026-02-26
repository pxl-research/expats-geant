"""Abstract base class for platform survey adapters."""

from abc import ABC, abstractmethod

from m_shared.models.response import Response
from m_shared.models.survey import Survey


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

        Defined capability strings: "import", "export", "submit".

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
