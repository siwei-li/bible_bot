import pytest
from unittest.mock import patch, MagicMock
from gloo.chat import send_message


# @patch("gloo.chat.ensure_valid_token")
# @patch("gloo.chat.requests.post")
# def test_send_message_success(mock_post, mock_token):
#     mock_token.return_value = "fake-token"
#     mock_response = MagicMock()
#     mock_response.json.return_value = {"result": "ok"}
#     mock_response.raise_for_status.return_value = None
#     mock_post.return_value = mock_response

#     result = send_message("Hello, world!")
#     assert result == {"result": "ok"}
#     mock_post.assert_called_once()
#     args, kwargs = mock_post.call_args
#     assert kwargs["headers"]["Authorization"] == "Bearer fake-token"
#     assert kwargs["json"]["query"] == "Hello, world!"
#     assert "chat_id" not in kwargs["json"]


# @patch("gloo.chat.ensure_valid_token")
# @patch("gloo.chat.requests.post")
# def test_send_message_with_chat_id(mock_post, mock_token):
#     mock_token.return_value = "fake-token"
#     mock_response = MagicMock()
#     mock_response.json.return_value = {"result": "ok"}
#     mock_response.raise_for_status.return_value = None
#     mock_post.return_value = mock_response

#     result = send_message("Test message", chat_id="12345")
#     assert result == {"result": "ok"}
#     args, kwargs = mock_post.call_args
#     assert kwargs["json"]["chat_id"] == "12345"


# @patch("gloo.chat.ensure_valid_token")
# @patch("gloo.chat.requests.post")
# def test_send_message_raises_for_status(mock_post, mock_token):
#     mock_token.return_value = "fake-token"
#     mock_response = MagicMock()
#     mock_response.raise_for_status.side_effect = Exception("HTTP error")
#     mock_post.return_value = mock_response

#     with pytest.raises(Exception) as excinfo:
#         send_message("Error message")
#     assert "HTTP error" in str(excinfo.value)