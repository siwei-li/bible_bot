"""
Campaign Creation Routes for Linguist UI
Handles Bible verse and TAME campaign creation
"""

from fastapi import APIRouter, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List
import os
import json
import uuid
from datetime import datetime

from linguist import auth
from data.supabase_client import supabaseClient
from services.campaign_generator import (
    create_bible_campaign,
    create_tame_campaign,
    create_text_to_text_campaign,
    create_image_to_text_campaign,
    create_audio_to_audio_campaign,
    create_ordered_campaign,
    BibleAPIError
)

router = APIRouter(prefix="/linguist/campaigns", tags=["campaigns"])

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)


@router.get("/create/bible", response_class=HTMLResponse)
async def bible_campaign_form(request: Request, project_id: int):
    """Show Bible verse campaign creation form"""
    user = await auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)

    return templates.TemplateResponse("campaigns/create_bible_campaign.html", {
        "request": request,
        "user": user,
        "project_id": project_id
    })


@router.post("/create/bible")
async def create_bible_campaign_submit(
    request: Request,
    project_id: int = Form(...),
    campaign_name: str = Form(...),
    book: str = Form(...),
    start_chapter: int = Form(...),
    start_verse: int = Form(...),
    end_chapter: int = Form(...),
    end_verse: int = Form(...),
    response_type: str = Form("either"),
    translation: str = Form("web")
):
    """Handle Bible campaign creation"""
    user = await auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)

    try:
        result = await create_bible_campaign(
            project_id=project_id,
            campaign_name=campaign_name,
            book=book,
            start_chapter=start_chapter,
            start_verse=start_verse,
            end_chapter=end_chapter,
            end_verse=end_verse,
            response_type=response_type,
            translation=translation
        )

        # Redirect to campaign view
        return RedirectResponse(
            url=f"/linguist/campaigns/{result['campaign']['id']}",
            status_code=303
        )

    except BibleAPIError as e:
        return templates.TemplateResponse("campaigns/create_bible_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": f"Bible API Error: {str(e)}"
        })
    except Exception as e:
        return templates.TemplateResponse("campaigns/create_bible_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": f"Error creating campaign: {str(e)}"
        })


@router.get("/create/tame", response_class=HTMLResponse)
async def tame_campaign_form(request: Request, project_id: int):
    """Show TAME campaign creation form"""
    user = await auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)

    return templates.TemplateResponse("campaigns/create_tame_campaign.html", {
        "request": request,
        "user": user,
        "project_id": project_id
    })


@router.post("/create/tame")
async def create_tame_campaign_submit(
    request: Request,
    project_id: int = Form(...),
    campaign_name: str = Form(...),
    base_sentences: str = Form(...),  # JSON string of sentences
    categories: List[str] = Form(...),  # Multiple select
    response_type: str = Form("either")
):
    """Handle TAME campaign creation"""
    user = await auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)

    try:
        # Parse base sentences JSON
        sentences = json.loads(base_sentences)
        if not isinstance(sentences, list):
            raise ValueError("Base sentences must be a list")

        result = await create_tame_campaign(
            project_id=project_id,
            campaign_name=campaign_name,
            base_sentences=sentences,
            categories=categories,
            response_type=response_type
        )

        # Redirect to campaign view
        return RedirectResponse(
            url=f"/linguist/campaigns/{result['campaign']['id']}",
            status_code=303
        )

    except json.JSONDecodeError:
        return templates.TemplateResponse("create_tame_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": "Invalid sentence format. Please check your JSON."
        })
    except Exception as e:
        return templates.TemplateResponse("create_tame_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": f"Error creating campaign: {str(e)}"
        })


@router.get("/preview/tame", response_class=JSONResponse)
async def preview_tame_questions(
    request: Request,
    categories: str,  # Comma-separated
    sentence: str
):
    """Preview what questions will be generated for a TAME campaign"""
    user = await auth.get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from data.supabase_client import supabaseClient

    try:
        category_list = [c.strip() for c in categories.split(',')]
        preview_questions = []

        for category in category_list:
            # Get variations for this category
            variations_result = supabaseClient.table('tame_variations').select('*').eq(
                'category', category
            ).order('sort_order').execute()

            variations = variations_result.data if variations_result.data else []

            for var in variations:
                preview_questions.append({
                    "category": category,
                    "variation": var['variation_type'],
                    "example": var['example_context'],
                    "sample_question": f"How would you say '{sentence}' {var['example_context']}?"
                })

        return {
            "success": True,
            "total_questions": len(preview_questions),
            "questions": preview_questions
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/create/generic", response_class=HTMLResponse)
async def generic_campaign_form(request: Request, project_id: int):
    """Show generic campaign creation form"""
    user = await auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)

    return templates.TemplateResponse("campaigns/create_generic_campaign.html", {
        "request": request,
        "user": user,
        "project_id": project_id
    })


@router.post("/create/generic")
async def create_generic_campaign_submit(
    request: Request,
    project_id: int = Form(...),
    campaign_name: str = Form(...),
    input_type: str = Form(...),
    output_type: str = Form(...),
    questions_data: str = Form(...),  # JSON string
    response_type: str = Form("either")
):
    """Handle generic campaign creation (image->text, audio->audio, etc.)"""
    user = await auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)

    try:
        # Parse questions data
        questions = json.loads(questions_data)
        if not isinstance(questions, list) or len(questions) == 0:
            raise ValueError("Questions data must be a non-empty list")

        # Route to appropriate campaign generator based on input/output types
        if input_type == "text" and output_type == "text":
            result = await create_text_to_text_campaign(
                project_id=project_id,
                campaign_name=campaign_name,
                questions_data=questions,
                response_type="text"
            )
        elif input_type == "image" and output_type == "text":
            result = await create_image_to_text_campaign(
                project_id=project_id,
                campaign_name=campaign_name,
                questions_data=questions,
                response_type="text"
            )
        elif input_type == "audio" and output_type == "audio":
            result = await create_audio_to_audio_campaign(
                project_id=project_id,
                campaign_name=campaign_name,
                questions_data=questions,
                response_type="voice"
            )
        else:
            raise ValueError(f"Unsupported campaign type: {input_type} -> {output_type}")

        # Redirect to campaign view
        return RedirectResponse(
            url=f"/linguist/campaigns/{result['campaign']['id']}",
            status_code=303
        )

    except json.JSONDecodeError:
        return templates.TemplateResponse("campaigns/create_generic_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": "Invalid questions format. Please check your data."
        })
    except ValueError as e:
        return templates.TemplateResponse("campaigns/create_generic_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": str(e)
        })
    except Exception as e:
        return templates.TemplateResponse("campaigns/create_generic_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": f"Error creating campaign: {str(e)}"
        })


@router.get("/create/ordered", response_class=HTMLResponse)
async def ordered_campaign_form(request: Request, project_id: int):
    """Show ordered campaign creation form"""
    user = await auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)

    return templates.TemplateResponse("campaigns/create_ordered_campaign.html", {
        "request": request,
        "user": user,
        "project_id": project_id
    })


@router.post("/create/ordered")
async def create_ordered_campaign_submit(
    request: Request,
    project_id: int = Form(...),
    campaign_name: str = Form(...),
    questions_json: str = Form(...),  # JSON array of question strings
    response_type: str = Form("either")
):
    """Handle ordered campaign creation"""
    user = await auth.get_current_user(request)
    if not user:
        return RedirectResponse(url="/linguist/login", status_code=303)

    try:
        # Parse questions JSON
        questions = json.loads(questions_json)
        if not isinstance(questions, list) or len(questions) == 0:
            raise ValueError("Questions must be a non-empty list")

        result = await create_ordered_campaign(
            project_id=project_id,
            campaign_name=campaign_name,
            questions_list=questions,
            response_type=response_type
        )

        # Redirect to campaign view
        return RedirectResponse(
            url=f"/linguist/campaigns/{result['campaign']['id']}",
            status_code=303
        )

    except json.JSONDecodeError:
        return templates.TemplateResponse("campaigns/create_ordered_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": "Invalid questions format. Please check your data."
        })
    except ValueError as e:
        return templates.TemplateResponse("campaigns/create_ordered_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": str(e)
        })
    except Exception as e:
        return templates.TemplateResponse("campaigns/create_ordered_campaign.html", {
            "request": request,
            "user": user,
            "project_id": project_id,
            "error": f"Error creating campaign: {str(e)}"
        })


@router.post("/upload-media")
async def upload_media_file(
    request: Request,
    file: UploadFile = File(...),
    project_id: int = Form(...)
):
    """Upload media file (image/audio) to Supabase storage and return URL"""
    user = await auth.get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        # Validate file type
        content_type = file.content_type or ""
        file_ext = file.filename.split('.')[-1].lower() if file.filename else ""

        # Determine bucket and validate file type
        if content_type.startswith('image/') or file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            bucket_name = "campaign-images"
            folder = "images"
        elif content_type.startswith('audio/') or file_ext in ['mp3', 'wav', 'ogg', 'm4a', 'aac']:
            bucket_name = "campaign-audio"
            folder = "audio"
        else:
            return JSONResponse(
                {"error": f"Unsupported file type: {content_type or file_ext}"},
                status_code=400
            )

        # Read file content
        file_content = await file.read()

        # Generate unique filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        safe_filename = f"{folder}/project_{project_id}/{timestamp}_{unique_id}.{file_ext}"

        # Upload to Supabase storage
        result = supabaseClient.storage.from_(bucket_name).upload(
            path=safe_filename,
            file=file_content,
            file_options={"content-type": content_type}
        )

        # Get public URL
        public_url = supabaseClient.storage.from_(bucket_name).get_public_url(safe_filename)

        return JSONResponse({
            "success": True,
            "url": public_url,
            "filename": file.filename,
            "size": len(file_content)
        })

    except Exception as e:
        print(f"Error uploading file: {e}")
        return JSONResponse(
            {"error": f"Upload failed: {str(e)}"},
            status_code=500
        )
