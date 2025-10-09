from enum import Enum
from typing import Dict, Any, Optional
import random


class UserState(Enum):
    NEW_USER = "new_user"
    AWAITING_CONSENT = "awaiting_consent"
    AWAITING_DOMAIN_SELECTION = "awaiting_domain_selection"
    IN_QUESTION = "in_question"
    AWAITING_TRANSCRIPTION_EDIT = "awaiting_transcription_edit"
    AWAITING_TEXT_VALIDATION = "awaiting_text_validation"
    AWAITING_CONTINUE_DECISION = "awaiting_continue_decision"
    ON_BREAK = "on_break"


class SessionManager:
    def __init__(self):
        self.user_sessions = {}
        self.pending_transcriptions = {}
        self.pending_validations = {}
        self.break_words = ['sunrise', 'forest', 'river', 'mountain', 'ocean', 'bird', 'flower', 'star']
        self.UserState = UserState

    def is_new_user(self, user_id: str) -> bool:
        """Check if this is a completely new user"""
        return user_id not in self.user_sessions

    def get_session(self, user_id: str) -> Dict[str, Any]:
        """Get or create user session"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                "state": UserState.NEW_USER,
                "domain": None,
                "current_question_id": None,
                "break_word": None,
                "questions_answered_this_session": 0
            }
        return self.user_sessions[user_id]

    def set_state(self, user_id: str, state: UserState):
        """Set user state"""
        session = self.get_session(user_id)
        session["state"] = state

    def generate_break_word(self, user_id: str) -> str:
        """Generate and store break word for user"""
        break_word = random.choice(self.break_words)
        session = self.get_session(user_id)
        session["break_word"] = break_word
        return break_word

    def clear_session(self, user_id: str):
        """Clear user session"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        if user_id in self.pending_transcriptions:
            del self.pending_transcriptions[user_id]
        if user_id in self.pending_validations:
            del self.pending_validations[user_id]

    # Storage section
    def store_pending_transcription(self, user_id: str, data: Dict[str, Any]):
        """Store pending transcription data"""
        self.pending_transcriptions[user_id] = data

    def get_pending_transcription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get pending transcription data"""
        return self.pending_transcriptions.get(user_id)

    def clear_pending_transcription(self, user_id: str):
        """Clear pending transcription"""
        if user_id in self.pending_transcriptions:
            del self.pending_transcriptions[user_id]

    def store_pending_validation(self, user_id: str, data: Dict[str, Any]):
        """Store pending validation data"""
        self.pending_validations[user_id] = data

    def get_pending_validation(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get pending validation data"""
        return self.pending_validations.get(user_id)

    def clear_pending_validation(self, user_id: str):
        """Clear pending validation"""
        if user_id in self.pending_validations:
            del self.pending_validations[user_id]
