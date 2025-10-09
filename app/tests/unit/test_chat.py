import pytest
from gloo.chat import send_message, get_chat_history


def test_send_message_success(monkeypatch):

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "chat_id": "test_chat_id",
                "message": "Hello!",
                "expires_in": 3600,
                "access_token": "dummy_token"
            }

    def mock_post(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr("requests.post", mock_post)
    result = send_message("Hello!")
    assert "chat_id" in result
    assert result["message"] == "Hello!"


def test_send_message_timeout(monkeypatch):

    def mock_post(*args, **kwargs):
        raise Exception("Request timed out")

    monkeypatch.setattr("requests.post", mock_post)
    with pytest.raises(Exception, match="Request timed out"):
        send_message("Hello!")


def test_get_chat_history_success(monkeypatch):

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"messages": [{"message": "Hello!"}]}

    def mock_get(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr("requests.get", mock_get)
    result = get_chat_history("test_chat_id")
    assert "messages" in result
    assert result["messages"][0]["message"] == "Hello!"


def test_get_chat_history_http_error(monkeypatch):
    class MockResponse:
        def raise_for_status(self): raise Exception("HTTP error")
    def mock_get(*args, **kwargs):
        return MockResponse()
    monkeypatch.setattr("requests.get", mock_get)
    with pytest.raises(Exception):
        get_chat_history("test_chat_id")
