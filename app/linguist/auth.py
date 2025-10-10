from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from linguist.db_helpers import supabaseClient as supabase
# from linguist.mock_db.mock_supabase import supabase
from typing import Optional, Dict, Any
import os

async def create_user_account(email: str, password: str, phone: Optional[str] = None) -> Dict[str, Any]:
    """Create a new user account with Supabase Auth"""
    try:
        # Sign up with Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })

        if auth_response.user:
            # Insert into User table with linguist role
            user_data = {
                'email': email,
                'user_role': 'linguist'
            }
            if phone:
                user_data['phone_whatsapp'] = phone

            # Use the Supabase auth user ID as the primary key
            user_data['id'] = auth_response.user.id

            supabase.table('users').insert(user_data).execute()

            return {"success": True, "user": auth_response.user}
        else:
            return {"success": False, "error": "Failed to create account"}
    except Exception as e:
        print(f"Signup error: {e}")
        return {"success": False, "error": str(e)}

async def login_user(email: str, password: str) -> Dict[str, Any]:
    """Login user with Supabase Auth"""
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if auth_response.session:
            return {
                "success": True,
                "session": auth_response.session,
                "user": auth_response.user
            }
        else:
            return {"success": False, "error": "Invalid credentials"}
    except Exception as e:
        print(f"Login error: {e}")
        return {"success": False, "error": str(e)}

async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user from session cookie"""
    try:
        access_token = request.cookies.get("access_token")
        if not access_token:
            return None

        # Verify token with Supabase
        user_response = supabase.auth.get_user(access_token)

        if user_response.user:
            # Get full user details from users table
            db_user = supabase.table('users').select('*').eq('id', user_response.user.id).execute()
            if db_user.data:
                return db_user.data[0]

        return None
    except Exception as e:
        print(f"Auth check error: {e}")
        return None

async def require_auth(request: Request):
    """Dependency to require authentication"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user

def redirect_if_not_authenticated(user: Optional[Dict[str, Any]]):
    """Helper to redirect to login if not authenticated"""
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)
    return None

async def get_google_oauth_url() -> str:
    """Get Google OAuth URL from Supabase"""
    try:
        redirect_to = os.getenv("NGROK_URL", "http://localhost:5017") + "/linguist/auth/callback"

        # Supabase provides OAuth URLs
        response = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": redirect_to
            }
        })

        return response.url if hasattr(response, 'url') else ""
    except Exception as e:
        print(f"Google OAuth error: {e}")
        return ""

async def handle_oauth_callback(code: str) -> Dict[str, Any]:
    """Handle OAuth callback and create/update user"""
    try:
        # Exchange code for session
        response = supabase.auth.exchange_code_for_session({"auth_code": code})

        if response.session and response.user:
            # Check if user exists in users table
            db_user = supabase.table('users').select('*').eq('id', response.user.id).execute()

            if not db_user.data:
                # Create new user record
                user_data = {
                    'id': response.user.id,
                    'email': response.user.email,
                    'user_role': 'linguist'
                }
                supabase.table('users').insert(user_data).execute()

            return {
                "success": True,
                "session": response.session,
                "user": response.user
            }

        return {"success": False, "error": "OAuth callback failed"}
    except Exception as e:
        print(f"OAuth callback error: {e}")
        return {"success": False, "error": str(e)}
