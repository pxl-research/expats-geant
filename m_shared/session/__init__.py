"""Session management for M-Autofill and M-Chat.

Provides session lifecycle management, TTL-based cleanup, and isolated storage.
"""

from m_shared.session.manager import SessionManager

__all__ = ["SessionManager"]
