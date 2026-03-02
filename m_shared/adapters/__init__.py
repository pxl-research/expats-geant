"""Platform survey adapters for Expat-GÉANT.

Each adapter translates between a specific survey platform's format and
the internal Survey model. Use `capabilities()` to check what operations
an adapter supports before calling optional methods.

Available adapters:
    - LimeSurveyAdapter: Import/export LSS XML; submit via RemoteControl 2 API
    - QualtricsAdapter: Import/export QSF JSON; submit via Response Import API
    - SurveyMonkeyAdapter: Import/export only (submission requires paid plan)
    - QTIAdapter: Import/export QTI 3.0 XML only (no submission concept)

Registry:
    Use `get_adapter(format_name)` to retrieve an adapter by format string.
"""

from m_shared.adapters.base import SurveyAdapter
from m_shared.adapters.limesurvey import LimeSurveyAdapter
from m_shared.adapters.qti import QTIAdapter
from m_shared.adapters.qualtrics import QualtricsAdapter
from m_shared.adapters.registry import get_adapter
from m_shared.adapters.surveymonkey import SurveyMonkeyAdapter

__all__ = [
    "SurveyAdapter",
    "LimeSurveyAdapter",
    "QualtricsAdapter",
    "QTIAdapter",
    "SurveyMonkeyAdapter",
    "get_adapter",
]
