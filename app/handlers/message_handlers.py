from typing import TYPE_CHECKING
from session.session_manager import SessionManager, UserState
from data.supabase_client import store_response, update_user_progress
from data.gloo_client import send_gloo_message_for_whatsapp_user


if TYPE_CHECKING:
    from pywa_async import WhatsApp


class MessageHandlers:
    def __init__(self, session_manager: SessionManager, consent_handler,
                 audio_handler, question_handler, domain_handler):
        self.session_manager = session_manager
        self.consent_handler = consent_handler
        self.audio_handler = audio_handler
        self.question_handler = question_handler
        self.domain_handler = domain_handler
        self.handlers = {
            # UserState.NEW_USER: pass # Handled in main webhook
            UserState.AWAITING_CONSENT: self.consent_handler.handle_consent_response,
            UserState.AWAITING_DOMAIN_SELECTION: self.domain_handler.handle_domain_selection,
            
            UserState.IN_QUESTION: self.process_text_with_validation,
            UserState.AWAITING_TRANSCRIPTION_EDIT: self._handle_transcription_edit,
            UserState.AWAITING_TEXT_VALIDATION: self._handle_text_validation_edit,

            UserState.AWAITING_CONTINUE_DECISION: self._handle_continue_decision,
            UserState.ON_BREAK: self._handle_break_return,
        }
        self.pending_validations = {}

    async def handle_text_message(self, wa_client: "WhatsApp", user_id: str, text: str):
        """Route text messages based on user state"""
        session = self.session_manager.get_session(user_id)
        state = session["state"]
    
        handler = self.handlers.get(state)
        if handler:
            await handler(wa_client, user_id, text)
        else:
            await wa_client.send_message(
                to=user_id,
                text="Something went wrong. Please start over by sending any message."
            )

    async def handle_audio_message(self, wa_client: "WhatsApp", user_id: str, msg):
        """Handle audio messages"""
        session = self.session_manager.get_session(user_id)
        
        if session["state"] != UserState.IN_QUESTION:
            await wa_client.send_message(
                to=user_id,
                text="Please complete the current step before sending audio."
            )
            return
        
        await wa_client.send_message(
            to=user_id,
            text="🎵 Processing your audio message..."
        )
        
        audio_result = await self.audio_handler.process_audio_message(
            media_id=msg.audio.id,
            user_id=user_id
        )
        
        if "error" in audio_result:
            await wa_client.send_message(
                to=user_id,
                text="Sorry, I couldn't process your audio message. Please try again or send a text message."
            )
            return
        
        if audio_result.get("skipped", False):
            await wa_client.send_message(
                to=user_id,
                text=(
                    f"🎵 Audio received, thank you!"
                    "I can't transcribe this language automatically, but I've saved your audio."
                    "Please send your answer as text instead."
                )
            )
            return
        
        # Store transcription for editing
        self.session_manager.store_pending_transcription(user_id, {
            "original_text": audio_result["transcription"],
            "confidence": audio_result["confidence"],
            "audio_id": audio_result["audio_id"],
            "timestamp": msg.timestamp
        })
        
        confidence = audio_result["confidence"]
        confidence_emoji = "✅" if confidence > 0.8 else "⚠️" if confidence > 0.5 else "❌"
        
        await wa_client.send_message(
            to=user_id,
            text=(
                f"📝 I heard: \"{audio_result['transcription']}\"\n"
                f"{confidence_emoji} Confidence: {confidence:.1%}\n\n"
                f"Reply with:\n"
                f"• 'correct' - if transcription is accurate\n"
                f"• 'edit: [your correction]' - to fix the transcription\n"
                f"• Just continue typing - to proceed as-is"
            )
        )
    
        self.session_manager.set_state(user_id, UserState.AWAITING_TRANSCRIPTION_EDIT)

    async def _handle_transcription_edit(self, wa_client: "WhatsApp", user_id: str, text: str):
        """Handle user edits to transcription"""
        pending = self.session_manager.get_pending_transcription(user_id)
        if not pending:
            await wa_client.send_message(
                to=user_id,
                text="No transcription found to edit. Please answer the question again."
            )
            self.session_manager.set_state(user_id, UserState.IN_QUESTION)
            return
        
        if text.lower().startswith("edit:"):
            corrected_text = text[5:].strip()
            if not corrected_text:
                await wa_client.send_message(
                    to=user_id,
                    text="Please provide the corrected text after 'edit:'."
                )
                return
            final_text = corrected_text
            # TODO
            from data.supabase_client import update_transcription_in_db
            await update_transcription_in_db(pending["audio_id"], final_text, "user_corrected")
            await wa_client.send_message(to=user_id, text=f"✏️ Updated to: \"{final_text}\"")
        elif text.lower() == "correct":
            final_text = pending["original_text"]
            await wa_client.send_message(to=user_id, text="✅ Transcription confirmed!")
        else:
            final_text = text

        # Proceed to validation
        self.session_manager.clear_pending_transcription(user_id)
        await self.process_text_with_validation(wa_client, user_id, final_text)

    async def process_text_with_validation(self, wa_client: "WhatsApp", user_id: str, text: str):
        """Process text answer using LLM validation"""
        session = self.session_manager.get_session(user_id)
        question_id = session.get("current_question_id")
        if not question_id:
            await wa_client.send_message(
                to=user_id,
                text="No active question. Please start a domain first."
            )
            return
    
        question_data = await self.questions_service.get_question_by_id(question_id)
        question_text = question_data.get('text', 'Unknown question') if question_data else 'Unknown question'
        
        await wa_client.send_message(
            to=user_id,
            text="🤔 Let me validate your response..."
        )
    
        try:
            validation_prompt = (
                f"Question: '{question_text}'\n"
                f"Answer: '{text}'\n\n"
                f"Please validate this answer for cultural and linguistic accuracy in relation to the question. "
                f"Provide feedback and a cleaned version if needed, or respond 'valid' if it's good as-is. "
                f"Also provide a score from 1-10 based on relevance, accuracy, and cultural appropriateness."
            )  
            gloo_response = await send_gloo_message_for_whatsapp_user(
                whatsapp_id=user_id,
                message=validation_prompt
            )

            if gloo_response.lower().strip() in ['valid', 'good', 'acceptable'] or 'valid' in gloo_response.lower():
                # Auto-approve: skip user validation and proceed directly
                await wa_client.send_message(
                    to=user_id,
                    text=(
                        f"🤖 AI: {gloo_response}\n\n"
                        f"Moving on to the next question..."
                    )
                )
                score = self._extract_score_from_response(gloo_response) or 8
                await self._store_final_answer(user_id, text, "ai_validated", score)
                await self._ask_continue_or_break(wa_client, user_id)

            else:
                # Store for user confirmation
                self.pending_validations[user_id] = {
                    "original_text": text,
                    "validation_response": gloo_response,
                    "question_id": session["current_question_id"]
                }
                
                await wa_client.send_message(
                    to=user_id,
                    text=(
                        f"🤖 AI feedback: {gloo_response}\n\n"
                        f"Reply with:\n"
                        f"• 'accept' or 'ac' - to use this validation\n"
                        f"• 'edit: [your correction]' - to modify your answer"
                    )
                )
                session["state"] = UserState.AWAITING_TEXT_VALIDATION
            
        except Exception as e:
            print(f"Error in validation: {e}")
            # Fallback - accept answer as-is
            await self._store_final_answer(user_id, text, "no_validation", 5)
            await self._ask_continue_or_break(wa_client, user_id)

    async def _handle_text_validation_edit(self, wa_client: "WhatsApp", user_id: str, text: str):
        """Handle user edits to text validation"""
        pending = self.pending_validations.get(user_id)
        if not pending:
            await wa_client.send_message(
                to=user_id,
                text="No validation found to edit. Please answer the question again."
            )
            self.session_manager.set_state(user_id, UserState.IN_QUESTION)
            return
        
        if text.lower().startswith("edit:"):
            corrected_text = text[5:].strip()
            if not corrected_text:
                await wa_client.send_message(
                    to=user_id,
                    text="Please provide the corrected text after 'edit:'."
                )
                return
            final_text = corrected_text
            validation_type = "user_edited"
            score = 5
            await wa_client.send_message(to=user_id, text=f"✏️ Updated to: \"{final_text}\"")
        elif text.lower() == "accept":
            final_text = pending["validation_response"]
            validation_type = "original_text"
            score = 10
            await wa_client.send_message(to=user_id, text="✅ Validation accepted!")
        else:  # User provided new answer
            final_text = text
            validation_type = "user_new"
            score = 10
            await wa_client.send_message(to=user_id, text=f"📝 Edited: \"{final_text}\"")
        await self._store_final_answer(user_id, final_text, validation_type, score)
        await self._ask_continue_or_break(wa_client, user_id)

    async def _ask_continue_or_break(self, wa_client: "WhatsApp", user_id: str):
        """Ask user if they want to continue or take a break"""
        self.session_manager.set_state(user_id, UserState.AWAITING_CONTINUE_DECISION)
        
        await wa_client.send_message(
            to=user_id,
            text=(
                f"✅ Response saved! Thank you.\n\n"
                f"What would you like to do next?\n\n"
                f"• Reply 'continue' for the next question\n"
                f"• Reply 'break' to pause and resume later\n"
                f"• Reply 'done' to finish this session"
            )
        )

    async def _store_final_answer(self, user_id: str, answer: str, validation: str, score: int):
        """Store the final validated answer"""
        session = self.session_manager.get_session(user_id)
                    
        await store_response(
            user_id=user_id,
            question_id=session["current_question_id"],
            user_answer=answer,
            validation=validation,
            score=score,
            message_type="text"
        )
        
        await update_user_progress(
            user_id,
            domain=session.get("domain"),
            answered_id=session["current_question_id"]
        )

    async def _handle_continue_decision(self, wa_client: "WhatsApp", user_id: str, text: str):
        """Handle user's decision to continue or break"""
        session = self.session_manager.get_session(user_id)
        
        if text.lower() == 'continue':
            await self.question_handler.give_next_question(self, user_id)
            
        elif text.lower() == 'break':
            self.session_manager.generate_break_word(user_id)
            session["state"] = UserState.ON_BREAK
            
            await wa_client.send_message(
                to=user_id,
                text=(
                    f"☕ Taking a break! Your session is saved.\n\n"
                    f"To resume later, send the word: **{break_word}**\n\n"
                    f"Thank you for your contributions so far!"
                )
            )
            
        elif text.lower() == 'done':
            await wa_client.send_message(
                to=user_id,
                text=(
                    "🙏 Thank you for participating in our research!\n\n"
                    "Your contributions are valuable for improving Bible translations. "
                    "Feel free to return anytime by sending any message.\n\n"
                    "Blessings!"
                )
            )
            self.session_manager.clear_session(user_id)
            
        else:
            await wa_client.send_message(
                to=user_id,
                text="Please reply 'continue', 'break', or 'done'."
            )

    async def _handle_break_return(self, wa_client, user_id: str, text: str):
        """Handle user returning from break"""
        session = self.session_manager.get_session(user_id)
        
        if text.lower() == session["break_word"].lower():
            from data.supabase_client import get_user_progress
            progress = await get_user_progress(user_id)
            current_domain = session.get("domain")
            
            # Check if they have unanswered questions in current domain
            if current_domain:
                answered_ids = progress.get('answered_questions', [])
                remaining_questions = await self.questions_service.get_unanswered_questions(
                    current_domain, answered_ids
                )
                has_remaining_in_current = len(remaining_questions) > 0
            else:
                has_remaining_in_current = False
            
            available_domains = await self.questions_service.get_domains()
            
            welcome_message = (
                f"🎉 Welcome back!\n\n"
                f"📊 Previous session: {session.get('questions_answered_this_session', 0)} questions\n\n"
                f"What would you like to do?\n\n"
            )
            
            options = []
            if has_remaining_in_current:
                options.append(f"• 'continue {current_domain}' - Resume {current_domain} domain")
            # Option to start new domains
            for domain in available_domains:
                if domain != current_domain:
                    options.append(f"• '{domain}' - Start {domain} domain")
            
            # # Add info option
            # options.append("• 'info' - Learn more about domains")
            
            welcome_message += "\n".join(options)
            
            await wa_client.send_message(to=user_id, text=welcome_message)
            
            # Set state to domain selection so they can choose
            self.session_manager.set_state(user_id, self.session_manager.UserState.AWAITING_DOMAIN_SELECTION)
            
        # elif text.lower() == 'help':
        #     # Help for users who forgot their break word
        #     await wa_client.send_message(
        #         to=user_id,
        #         text=(
        #             "🤔 Forgot your break word?\n\n"
        #             "Don't worry! Just send any of these to restart:\n"
        #             "• 'restart' - Start fresh\n"
        #             "• 'new session' - Begin a new session\n\n"
        #             "Or try to remember your break word (it was a nature word like 'forest', 'river', etc.)"
        #         )
        #     )
            
        # elif text.lower() in ['restart', 'new session', 'start over']:
        #     # Allow users to restart if they forgot break word
        #     await wa_client.send_message(
        #         to=user_id,
        #         text="🔄 Starting fresh! Let's get you set up again."
        #     )
            
        #     # Reset to domain selection (they already consented before)
        #     self.session_manager.set_state(user_id, self.session_manager.UserState.AWAITING_DOMAIN_SELECTION)
        #     await self._handle_domain_selection(wa_client, user_id, 'info')
            
        else:
            await wa_client.send_message(
                to=user_id,
                text=(
                    f"Please send your break word: **{session['break_word']}** to resume.\n\n"
                    f"Or send 'help' if you need assistance."
                )
            )
