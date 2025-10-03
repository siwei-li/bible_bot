import requests
from data.supabase_client import supabaseClient
from gloo.cred import get_auth_headers
from gloo.chat import send_message


CHAT_API_URL = "https://platform.ai.gloo.com/ai/v1/chat"


def _get_or_create_gloo_chat_session(whatsapp_id: str) -> str:
    """Get existing chat session or create new one for WhatsApp user."""

    # Check if user already has a chat session
    result = supabaseClient.table("user_chat_sessions").select("gloo_chat_id").eq("whatsapp_id", whatsapp_id).execute()
    if result.data:
        return result.data[0]["gloo_chat_id"]

    # Create new chat session by sending initial message
    response = requests.post(CHAT_API_URL, headers=get_auth_headers())
    response.raise_for_status()
    gloo_chat_id = response.json()["chat_id"]
    created_at = response.json()["created_at"]

    supabaseClient.table("user_chat_sessions").insert({
        "whatsapp_id": whatsapp_id,
        "gloo_chat_id": gloo_chat_id,
        "created_at": created_at
    }).execute()

    return gloo_chat_id


def send_gloo_message_for_whatsapp_user(
    whatsapp_id: str, message_text: str
) -> dict:
    """Send message using user's existing or new chat session."""
    chat_id = _get_or_create_gloo_chat_session(whatsapp_id)
    return send_message(message_text, chat_id=chat_id)

