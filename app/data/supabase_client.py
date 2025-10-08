from supabase import create_client, Client

import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY environment variables"
                     "must be set")
supabaseClient: Client = create_client(supabase_url, supabase_key)


async def store_response(
    user_id: str,
    question_id: int,
    user_answer: str,
    validation: str,
    score: int,
    message_type: str = "text"
):
    """Store user response with message type"""
    try:
        response_data = {
            'user_id': user_id,
            'question_id': question_id,
            'user_answer': user_answer,
            'validation': validation,
            'score': score,
            'message_type': message_type,
            'timestamp': datetime.utcnow().isoformat()
        }
        result = supabaseClient.table('user_responses').insert(response_data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error storing response: {e}")
        return None


async def get_user_progress(user_id: str):
    """Get user progress from database"""
    try:
        result = (
            supabase.table('user_progress')
            .select('*')
            .eq('user_id', user_id)
            .execute()
        )
        if result.data:
            return result.data[0]
        else:
            # Create new user progress
            new_progress = {
                'user_id': user_id,
                'domain': None,
                'answered_questions': [],
                'created_at': datetime.utcnow().isoformat()
            }
            supabase.table('user_progress').insert(new_progress).execute()
            return new_progress
    except Exception as e:
        print(f"Database error: {e}")
        return {'user_id': user_id, 'domain': None, 'answered_questions': []}


async def update_user_progress(
    user_id: str,
    domain: str = None,
    answered_id: int = None
):
    """Update user progress in database"""
    try:
        current_progress = await get_user_progress(user_id)
        
        updates = {'updated_at': datetime.utcnow().isoformat()}
        if domain:
            updates['domain'] = domain
        if answered_id:
            answered_list = current_progress.get('answered_questions', [])
            if answered_id not in answered_list:
                answered_list.append(answered_id)
            updates['answered_questions'] = answered_list
        
        (
            supabase.table('user_progress')
            .update(updates)
            .eq('user_id', user_id)
            .execute()
        )
    except Exception as e:
        print(f"Error updating progress: {e}")


async def update_transcription_in_db(audio_id: int, corrected_text: str, validation_type: str):
    """Update transcription in database when user corrects it"""
    try:
        # Update the audio_files table
        supabaseClient.table("audio_files").update({
            "transcription": corrected_text,
            "transcription_confidence": 1.0,  # User correction = 100% confidence
            "processed_at": "now()"
        }).eq("id", audio_id).execute()
        
        print(f"Updated transcription for audio_id {audio_id}")
        
    except Exception as e:
        print(f"Error updating transcription: {e}")


#LATER - 
def store_user_metadata(whatsapp_id: str, profile_name: str = None):
    """Store additional user metadata"""
    try:
        # Get user profile info if available
        user_data = {
            'user_id': whatsapp_id,
            'domain': 'whatsapp',
            'answered_questions': []
        }
        
        if profile_name:
            user_data['profile_name'] = profile_name
            
        # Upsert user data
        result = supabase.table('user_progress').upsert(user_data).execute()
        return result.data
        
    except Exception as e:
        print(f"Error storing user metadata: {e}")
        return None
