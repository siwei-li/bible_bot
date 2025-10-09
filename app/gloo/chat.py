from gloo.cred import get_auth_headers
import requests
import httpx


MESSAGE_API_URL = "https://platform.ai.gloo.com/ai/v1/message"
CHAT_API_URL = "https://platform.ai.gloo.com/ai/v1/chat"


timeout_config = httpx.Timeout(
    timeout=5,
    connect=10.0,  # Connection timeout
    read=5,  # Read timeout
    write=10.0,  # Write timeout
    pool=5.0   # Pool timeout
)


def send_message(message_text, chat_id=None) -> dict:
    """Send a message to the chat API synchronously with timeout."""
    payload = {
        "query": message_text,
        "character_limit": 1000,
        "sources_limit": 5,
        "stream": False,
        "publishers": []
    }

    if chat_id:
        payload["chat_id"] = chat_id

    try:
        response = requests.post(
            MESSAGE_API_URL,
            headers=get_auth_headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.Timeout:
        raise Exception("Request timed out")
    except requests.exceptions.ConnectionError:
        raise Exception("Connection error - check internet connection")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"HTTP error: {e.response.status_code}")
    except Exception as e:
        raise Exception(f"Unexpected error: {str(e)}")


def get_chat_history(chat_id):
    """Retrieve the full chat history for a given chat ID."""

    params = {"chat_id": chat_id}

    response = requests.get(CHAT_API_URL, headers=get_auth_headers(), params=params)
    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    print("test\n")
    exit()
    chat_response = send_message("Hello, how are you?")
    print(chat_response)

    if 'chat_id' in chat_response:
        history = get_chat_history(chat_response['chat_id'])
        print(history)


    """
{'chat_id': 'c431bdd48-57ee-48a3-8c45-400f5c7b0a86', 
'query_id': 'qa67124c4-d033-4f67-a708-dd8125a69033', 
'message_id': 'mca08d454-f714-4c46-abcd-591d6602f90f', 
'timestamp': '2025-10-03T19:19:51.112340', 'success': True, 
'message': '\n\nHello! As an AI, I don’t experience emotions, but I’m here to help with any questions, prayer requests, or biblical insights you need. How can I serve you today?', 
'model': 'us.deepseek.r1-v1:0', 'sources': [], 'sources_limit': 5, 
'suggestions': ['What topics can you help me with?', 'Can you share a Bible verse for encouragement?', 'I have a prayer request.'], 
'intent': 0}


{'user_id': 'u3fc74e65-c3ab-4dec-8276-09fa52835b7c', 
'chat_id': 'c431bdd48-57ee-48a3-8c45-400f5c7b0a86', 
'created_at': '2025-10-03T19:19:46.624251', 'updated_at': '2025-10-03T19:19:54.802191', 

'messages': [
{'query_id': 'qa67124c4-d033-4f67-a708-dd8125a69033', 
'message_id': 'm139758df-dda3-49fd-82ae-2ddc46526eef', 
'timestamp': '2025-10-03T19:19:48.027899', 'role': 'user', 'character_limit': 1000, 
'stream': False, 'intent': 0, 'message': 'Hello, how are you?', 
'model': 'us.deepseek.r1-v1:0', 'publishers': []},

{'query_id': 'qa67124c4-d033-4f67-a708-dd8125a69033', 
'message_id': 'mca08d454-f714-4c46-abcd-591d6602f90f', 
'timestamp': '2025-10-03T19:19:51.112340', 
'role': 'kallm', 'intent': 0, 
'sources_limit': 5, 'sources': [], 'success': True, 
'suggestions': ['What topics can you help me with?', 'Can you share a Bible verse for encouragement?', 'I have a prayer request.'], 
'message': '\n\nHello! As an AI, I don’t experience emotions, but I’m here to help with any questions, prayer requests, or biblical insights you need. How can I serve you today?', 
'model': 'us.deepseek.r1-v1:0', 'feedback_score': None}], 

'pin': False, 'summary': None, 
'title': 'AI Assistant Greets and Offers Support'}
    """
