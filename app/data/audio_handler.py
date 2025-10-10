import requests
from pathlib import Path
import openai
from typing import Optional, Dict, Any
from data.supabase_client import supabaseClient
from datetime import datetime, timedelta


class AudioHandler:
    def __init__(self, whatsapp_token: str):
        self.whatsapp_token = whatsapp_token
        self.audio_storage_path = Path("./audio_files")
        self.audio_storage_path.mkdir(exist_ok=True)
        self.pending_transcriptions: Dict[str, Dict[str, Any]] = {}

    async def process_audio_message(self, media_id: str, user_id: str) -> Dict[str, Any]:
        """Download, transcribe, and store audio message"""
        try:
            file_info = await self._download_whatsapp_media(media_id)
            if not file_info:
                return {"error": "Failed to download audio"}

            transcription_result = await self._transcribe_audio(file_info["file_path"])
            
            audio_record = await self._store_audio_metadata(
                media_id=media_id,
                user_id=user_id,
                file_info=file_info,
            )

            return {
                "transcription": transcription_result["text"],
                "confidence": -getattr(transcription_result, 'avg_logprob', 0.0),
                "file_path": file_info["file_path"],
                "audio_id": audio_record["id"]
            }

        except Exception as e:
            print(f"Error processing audio: {e}")
            return {"error": str(e)}

    # Clean up old pending transcriptions periodically
    async def cleanup_old_transcriptions(self):
        """Remove pending transcriptions older than 5 minutes"""
        while True:
            try:
                current_time = datetime.now()
                expired_users = []
                
                for user_id, data in self.pending_transcriptions.items():
                    if current_time - data["timestamp"] > timedelta(minutes=5):
                        expired_users.append(user_id)
                
                for user_id in expired_users:
                    del self.pending_transcriptions[user_id]
                    print(f"Cleaned up expired transcription for user {user_id}")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                print(f"Error in cleanup: {e}")
                await asyncio.sleep(60)

    async def _download_whatsapp_media(self, media_id: str) -> Optional[Dict[str, Any]]:
        """Download media file from WhatsApp"""
        try:
            # Get media URL
            url = f"https://graph.facebook.com/v18.0/{media_id}"
            headers = {"Authorization": f"Bearer {self.whatsapp_token}"}
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            media_info = response.json()

            # Download the actual file
            file_response = requests.get(media_info["url"], headers=headers)
            file_response.raise_for_status()

            # Save to local storage
            file_extension = self._get_file_extension(
                media_info.get("mime_type", "")
            )
            filename = f"{media_id}{file_extension}"
            file_path = self.audio_storage_path / filename

            with open(file_path, "wb") as f:
                f.write(file_response.content)

            return {
                "file_path": str(file_path),
                "file_size": len(file_response.content),
                "mime_type": media_info.get("mime_type"),
                "filename": filename
            }

        except Exception as e:
            print(f"Error downloading media: {e}")
            return None

    async def _transcribe_audio(self, file_path: str) -> Dict[str, Any]:
        """Transcribe audio using OpenAI Whisper"""
        try:
            with open(file_path, "rb") as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json"
                )

            return {
                "text": transcript.text,
                "confidence": getattr(transcript, 'confidence', 0.0),
                "language": getattr(transcript, 'language', 'unknown')
            }

        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return {"text": "", "confidence": 0.0, "error": str(e)}

    async def _store_audio_metadata(self, media_id: str, user_id: str, 
                                    file_info: Dict) -> Dict:
        """Store audio file metadata in database"""
        audio_data = {
            "whatsapp_id": media_id,
            "user_id": user_id,
            "file_id": media_id,
            "file_path": file_info["file_path"],
            "file_size": file_info["file_size"],
            "mime_type": file_info["mime_type"],
            "processed_at": "now()"
        }

        result = supabaseClient.table("audio_files").insert(
            audio_data).execute()
        return result.data[0]

    def _get_file_extension(self, mime_type: str) -> str:
        """Get file extension from MIME type"""
        mime_to_ext = {
            "audio/ogg": ".ogg",
            "audio/mpeg": ".mp3",
            "audio/mp4": ".mp4",
            "audio/wav": ".wav",
            "audio/aac": ".aac"
        }
        return mime_to_ext.get(mime_type, ".audio")
