import os

import pytest

from llmtape.testing import scripted_client

from .scripted_model import respond


@pytest.fixture
def client():
    """Claude when recording with a key; the scripted stand-in otherwise.

    In replay mode the client is never called, so tests need no key and cost nothing."""
    if os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("LLMTAPE_MODE") in ("record", "update"):
        import anthropic
        return anthropic.Anthropic()
    return scripted_client(respond)
