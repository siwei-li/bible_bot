import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor
from data.supabase_client import supabaseClient
from gloo.cred import get_auth_headers
from gloo.chat import send_message


CHAT_API_URL = "https://platform.ai.gloo.com/ai/v1/chat"


async def _get_or_create_gloo_chat_session(whatsapp_id: str) -> str:
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


# Global thread pool for sync operations
executor = ThreadPoolExecutor(max_workers=5)


async def send_gloo_message_for_whatsapp_user(whatsapp_id: str, message: str):
    """Async wrapper around sync Gloo API calls"""
    try:
        chat_id = await _get_or_create_gloo_chat_session(whatsapp_id)

        loop = asyncio.get_event_loop()
        # Send message in thread pool
        response = await loop.run_in_executor(
            executor,
            send_message,
            message,
            chat_id
        )
        
        return response.get('message', _get_fallback_response(message))
        
    except Exception as e:
        print(f"Error sending Gloo message: {e}")
        return _get_fallback_response(message)


def _get_fallback_response(message: str) -> str:
    """Fallback when API fails"""
    error_msg = "Sorry, I'm having trouble connecting to the service right now."
    if len(message.lower()) % 2:
        error_msg += " Here's a verse about hope: 'For I know the plans I have for you, declares the Lord, plans for welfare and not for evil, to give you a future and a hope.' - Jeremiah 29:11"
    else:
        error_msg += " About God's love: 'For God so loved the world that he gave his one and only Son.' - John 3:16"
    return error_msg

# Example response data from Gloo chat API (formatted for readability)
example_response = {
    'chat_id': 'cf7077e20-20fa-46f0-8c1a-f10de262a5d5',
    'query_id': 'q743f10c1-ede5-480b-9a9d-4f69b91ec61b',
    'message_id': 'm435eabfd-b9a9-4988-a34f-9225a8c9d50a',
    'timestamp': '2025-10-08T23:17:55.133329',
    'success': True,
    'message': (
        "\n\n**Psalm 25:5** says, “Lead me in your truth and teach me, for you are the God of my salvation; "
        "for you I wait all the day long.” **Psalm 119:114** adds, “You are my hiding place and my shield; "
        "I hope in your word.” These verses emphasize hope as patient trust in God’s guidance and reliance "
        "on His Word for protection and assurance."
    ),
    'model': 'us.deepseek.r1-v1:0',
    'sources': [
        {
            'item_id': '5253c693-ef92-408f-9dd5-70c4e0142d09',
            'author': ['Anthony Eshun'],
            'filename': 'getting-inspiration-from-10-powerful-bible-verses-about-hope-kUGcZpSAonjBPYoy6vRg-.txt',
            'count': 1,
            'denomination': '',
            'duration': '',
            'item_title': 'Getting Inspiration From 10 Powerful Bible Verses About Hope',
            'item_subtitle': '',
            'item_image': '',
            'item_url': 'https://blogs.crossmap.com/stories/getting-inspiration-from-10-powerful-bible-verses-about-hope-kUGcZpSAonjBPYoy6vRg-',
            'item_tags': ['Uncategorized'],
            'publication_date': 'Oct 15 2019',
            'publisher': 'Crossmap',
            'publisher_id': '1b653cec-d9ae-4310-9c66-394fcb950726',
            'publisher_url': 'www.crossmap.com',
            'publisher_logo': 'https://dapologeticsimages.s3.us-east-1.amazonaws.com/logos/logo_1751930142598.png',
            'summary': (
                "The passage emphasizes the transformative power of hope through biblical teachings, "
                "highlighting how faith can provide strength during challenging times. It encourages "
                "believers to remain resilient and trust in God's guidance, drawing inspiration from "
                "scripture that promises a future filled with possibility and divine intervention."
            ),
            'type': 'article',
            'uuids': [
                {
                    'uuid': 'dbeaa184-a1c3-5ac7-a8f0-cef9e5cb54c6',
                    'ai_title': 'Finding Hope Through Biblical Truth',
                    'ai_subtitle': 'Strengthening Your Faith with Scripture',
                    'ai_bible_references': ['Proverbs 23:18', 'Psalms 43:5'],
                    'ai_book_of_the_bible': 'Proverbs and Psalms',
                    'ai_bible_characters': ['Jesus'],
                    'ai_bible_verses': [
                        'Indeed surely there is a future hope, and your hope will not be cut off',
                        'Why are you depressed, O my soul? Why are you upset? Wait for God! For I will again give thanks to my God for his saving intervention'
                    ],
                    'ai_scripture_parallels': ['Romans 15:13', 'Hebrews 6:19', 'Jeremiah 29:11'],
                    'snippet': (
                        'Hope The moment you start yearning for Bible verses for hope; you must be prepared to fight against all the challenges '
                        'that would try to destroy your life. Jesus is the fountain of water that gives life. With him, you would be free from the Devil’s plans '
                        'to destroy your life. Take a minute and read these Bible verses about life . They will inspire you to lay down your whole life on God. '
                        'You would need to psych yourself up in defiance to any obstruction that may crop up\xa0from the Spiritual realm or the physical realm. '
                        '“Indeed surely there is a future hope, and your hope will not be cut off ( Proverbs 23:18 ).” We are already at war and so must put on the full armor of God. '
                        'With Him everything is possible. Your hope wouldn’t be in vain and nothing will bog you down. Selected Bible Verses About Hope 1. '
                        '“Why are you depressed, O my soul? Why are you upset? Wait for God! For I will again give thanks to my God for his saving intervention ( Psalms 43:5 ).”'
                    ),
                    'summary': (
                        'Within the sacred text lies an eternal message of hope, wherein the divine presence of Jesus Christ serves as an inexhaustible wellspring of spiritual sustenance.'
                    ),
                    'part': 3,
                    'certainty': 0.8238045573234558
                }
            ],
            'hosted_url': 'https://blogs.crossmap.com/stories/getting-inspiration-from-10-powerful-bible-verses-about-hope-kUGcZpSAonjBPYoy6vRg-'
        },
        # ... (other sources omitted for brevity)
    ],
    'sources_limit': 5,
    'suggestions': [
        'What does biblical hope mean compared to everyday hope?',
        'Can you share verses about hope during difficult times?',
        "How can I build stronger hope in God's promises?",
        "What's the connection between faith and hope in Scripture?"
    ],
    'intent': 1
}
