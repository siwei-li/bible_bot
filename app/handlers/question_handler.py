import random
from typing import Optional, Dict
from session.session_manager import SessionManager, UserState
from services.questions_service import QuestionsService
from data.supabase_client import get_user_progress, insert_question, supabaseClient
from data.users import send_gloo_message_for_whatsapp_user
from shared.constants import GLOO_FALLBACK_MSG


class QuestionHandler:
    def __init__(self, session_manager: SessionManager, questions_service: QuestionsService):
        self.session_manager = session_manager
        self.questions_service = questions_service
    
    async def give_next_question(self, wa_client, user_id: str):
        """Give user the next random question"""
        session = self.session_manager.get_session(user_id)
        domain = session.get("domain")
        
        if not domain:
            await wa_client.send_message(
                to=user_id,
                text="Please start a domain first by inputting '[domain]', like 'bot'."
            )
            return

        if domain.lower() == 'bot':
            language_code = supabaseClient.table("user_progress").select("language_code").eq("user_id", user_id).execute().data[0]['language_code'] or 'zh'
            try:
                prompt = (
                    f"Suggest a Bible translation question for a speaker of '{language_code}'. "
                    f"Keep it simple and focused on helping linguists."
                )
                gloo_response = await send_gloo_message_for_whatsapp_user(
                    whatsapp_id=user_id,
                    message=prompt
                )
                if not gloo_response or gloo_response.startswith(GLOO_FALLBACK_MSG):
                    raise ValueError("Gloo API connection error")

                new_question = await insert_question(gloo_response, 'bot', '')
                if not new_question:
                    raise ValueError("Failed to insert question into database")
                
                session["current_question_id"] = new_question['id']
                self.session_manager.set_state(user_id, UserState.IN_QUESTION)
                
                await wa_client.send_message(
                    to=user_id,
                    text=(
                        f"📝 Here's a question suggested by bot for you:\n\n"
                        f"{new_question['text']}\n\n"
                        # f"You may also send a voice message to us!\n\n"
                    )
                )
            
            except Exception as e:
                print(f"Error getting AI-generated question: {e}")
                await wa_client.send_message(
                    to=user_id,
                    text="Sorry, I'm having trouble generating a question right now. Please try again later."
                )
                # Optionally fall back to pre-defined questions
                return
        
        progress = await get_user_progress(user_id)
        answered_ids = progress.get('answered_questions', [])
        remaining_questions = await self.questions_service.get_unanswered_questions(
            domain, answered_ids
        )
        if not remaining_questions:
            await wa_client.send_message(
                to=user_id,
                text=(
                    "🎉 Congratulations! You've answered all questions in this domain!\n\n"
                    "Thank you for your valuable contributions to Bible translation research."
                )
            )
            self.session_manager.clear_session(user_id)
            self.session_manager.set_state(user_id, UserState.AWAITING_DOMAIN)
            return
        
        # # Get total questions count for progress
        # all_questions = await self.questions_service.get_questions_by_domain(domain)
        # total_count = len(all_questions)
        
        # ELSE: suggest a random question
        next_question = random.choice(remaining_questions)
        session["current_question_id"] = next_question['id']
        self.session_manager.set_state(user_id, UserState.IN_QUESTION)
        
        await wa_client.send_message(
            to=user_id,
            text=(
                f"📝 Question:\n\n"
                f"{next_question['text']}\n\n"
                # f"You may also send a voice message to us!\n\n"
            )
        )
    
    async def get_current_question(self, user_id: str) -> Optional[Dict]:
        """Get the current question for a user"""
        session = self.session_manager.get_session(user_id)
        question_id = session.get("current_question_id")
        
        if question_id:
            return await self.questions_service.get_question_by_id(question_id)
        return None
