"""Adapter registry — maps format strings to adapter classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from m_shared.adapters.base import SurveyAdapter

_REGISTRY: dict[str, type] = {}


def _build_registry() -> dict[str, type]:
    from m_shared.adapters.limesurvey import LimeSurveyAdapter
    from m_shared.adapters.qti import QTIAdapter
    from m_shared.adapters.qualtrics import QualtricsAdapter
    from m_shared.adapters.surveymonkey import SurveyMonkeyAdapter

    return {
        "limesurvey": LimeSurveyAdapter,
        "lss": LimeSurveyAdapter,
        "qualtrics": QualtricsAdapter,
        "qsf": QualtricsAdapter,
        "qti": QTIAdapter,
        "surveymonkey": SurveyMonkeyAdapter,
        "sm": SurveyMonkeyAdapter,
    }


def get_adapter(format_name: str, **kwargs) -> SurveyAdapter:
    """Return an initialised adapter for the given format name.

    Args:
        format_name: Case-insensitive format/platform identifier
                     (e.g. "limesurvey", "lss").
        **kwargs: Passed through to the adapter constructor
                  (e.g. api_url, username, password for LimeSurvey).

    Returns:
        SurveyAdapter: A ready-to-use adapter instance.

    Raises:
        KeyError: If no adapter is registered for the given format.
    """
    registry = _build_registry()
    key = format_name.lower()
    if key not in registry:
        supported = ", ".join(sorted(registry))
        raise KeyError(f"No adapter for format '{format_name}'. Supported: {supported}")
    return registry[key](**kwargs)
