import pytest

from llmtape.testing import scripted_async_client, scripted_client

pytest_plugins = ["pytester"]


class Echo:
    """Scripted model: echoes the last user text, or calls a tool when asked to."""

    def __init__(self):
        self.calls = 0

    def __call__(self, request):
        self.calls += 1
        last = request["messages"][-1]["content"]
        if isinstance(last, str) and last.startswith("tool:"):
            return [{"type": "tool_use", "name": last[5:], "input": {"q": last}}]
        text = last if isinstance(last, str) else "done"
        return [{"type": "text", "text": f"echo {text}"}]


@pytest.fixture
def echo():
    return Echo()


@pytest.fixture
def client(echo):
    return scripted_client(echo)


@pytest.fixture
def aclient(echo):
    return scripted_async_client(echo)


def ask(client, text, model="claude-haiku-5-5", system="be brief"):
    return client.messages.create(model=model, max_tokens=50, system=system,
                                  messages=[{"role": "user", "content": text}])
