import random
from typing import Optional, Dict
from session.session_manager import SessionManager, UserState
from services.questions_service import QuestionsService
from data.supabase_client import get_user_progress


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
                text="Please start a domain first by inputting '[domain]' or the number option like '1','2','3' etc."
            )
            return
        
        progress = await get_user_progress(user_id)
        answered_ids = progress.get('answered_questions', [])
        
        # Get remaining questions
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
            return
        
        # Get total questions count for progress
        # all_questions = await self.questions_service.get_questions_by_domain(domain)
        # total_count = len(all_questions)
        
        # TODO - LLM give questions for scarce languages

        next_question = random.choice(remaining_questions)
        session["current_question_id"] = next_question['id']
        self.session_manager.set_state(user_id, UserState.IN_QUESTION)
        
        await wa_client.send_message(
            to=user_id,
            text=(
                f"📝 Question:\n\n"
                f"{next_question['text']}\n\n"
                f"You may also send a voice message to us!\n\n"
            )
        )
    
    async def get_current_question(self, user_id: str) -> Optional[Dict]:
        """Get the current question for a user"""
        session = self.session_manager.get_session(user_id)
        question_id = session.get("current_question_id")
        
        if question_id:
            return await self.questions_service.get_question_by_id(question_id)
        return None

    # create has_remaining_questions_in_current_domain() and get_available
