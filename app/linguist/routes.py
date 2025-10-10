from fastapi import APIRouter, Request, Form, Response, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
import os
import json
import csv
from io import StringIO

from linguist import db_helpers, auth

router = APIRouter(prefix="/linguist", tags=["linguist"])

# Get absolute path to templates directory
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Auth routes
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Show login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
async def login(request: Request, response: Response, email: str = Form(...), password: str = Form(...)):
    """Handle login"""
    result = await auth.login_user(email, password)

    if result["success"]:
        # Set session cookie
        resp = RedirectResponse(url="/linguist/projects", status_code=303)
        resp.set_cookie(
            key="access_token",
            value=result["session"].access_token,
            httponly=True,
            max_age=result["session"].expires_in,
            samesite="lax",
            secure=True
        )
        return resp
    else:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": result.get("error", "Login failed")
        })

@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Show signup page"""
    return templates.TemplateResponse("signup.html", {"request": request})

@router.post("/signup", response_class=HTMLResponse)
async def signup(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    phone: Optional[str] = Form(None)
):
    """Handle signup"""
    result = await auth.create_user_account(email, password, phone)

    if result["success"]:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": None,
            "success": "Account created! Please log in."
        })
    else:
        return templates.TemplateResponse("signup.html", {
            "request": request,
            "error": result.get("error", "Signup failed")
        })

@router.get("/logout")
async def logout():
    """Logout user"""
    resp = RedirectResponse(url="/linguist/login", status_code=303)
    resp.delete_cookie("access_token")
    return resp

@router.get("/auth/google")
async def google_login():
    """Initiate Google OAuth login"""
    url = await auth.get_google_oauth_url()
    if url:
        return {"url": url}
    else:
        return {"error": "Failed to get Google OAuth URL"}

@router.get("/auth/callback")
async def oauth_callback(code: str = None):
    """Handle OAuth callback"""
    if not code:
        return RedirectResponse(url="/linguist/login?error=no_code", status_code=303)

    result = await auth.handle_oauth_callback(code)

    if result["success"]:
        resp = RedirectResponse(url="/linguist/projects", status_code=303)
        resp.set_cookie(
            key="access_token",
            value=result["session"].access_token,
            httponly=True,
            max_age=result["session"].expires_in,
            samesite="lax",
            secure=True
        )
        return resp
    else:
        return RedirectResponse(
            url=f"/linguist/login?error={result.get('error', 'oauth_failed')}",
            status_code=303
        )

@router.get("/", response_class=HTMLResponse)
async def linguist_home(request: Request):
    """Redirect to projects page"""
    user = await auth.get_current_user(request)
    redirect = auth.redirect_if_not_authenticated(user)
    if redirect:
        return redirect
    return RedirectResponse(url="/linguist/projects")

@router.get("/projects", response_class=HTMLResponse)
async def list_projects(request: Request):
    """List all projects"""
    user = await auth.get_current_user(request)
    redirect = auth.redirect_if_not_authenticated(user)
    if redirect:
        return redirect

    try:
        projects = await db_helpers.get_all_projects()
        return templates.TemplateResponse("projects.html", {
            "request": request,
            "projects": projects,
            "user": user
        })
    except Exception as e:
        print(f"Error in list_projects: {e}")
        return templates.TemplateResponse("projects.html", {
            "request": request,
            "projects": [],
            "error": str(e),
            "user": user
        })

@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def view_project(request: Request, project_id: int):
    """View individual project details"""
    user = await auth.get_current_user(request)
    redirect = auth.redirect_if_not_authenticated(user)
    if redirect:
        return redirect

    try:
        project = await db_helpers.get_project_by_id(project_id)
        if not project:
            return templates.TemplateResponse("projects.html", {
                "request": request,
                "projects": [],
                "error": f"Project {project_id} not found",
                "user": user
            })

        # Get campaigns for this project
        campaigns_result = await db_helpers.get_all_campaigns()
        project_campaigns = [c for c in campaigns_result if c.get('project_id') == project_id]

        return templates.TemplateResponse("project_detail.html", {
            "request": request,
            "project": project,
            "campaigns": project_campaigns,
            "user": user
        })
    except Exception as e:
        print(f"Error viewing project: {e}")
        return templates.TemplateResponse("projects.html", {
            "request": request,
            "projects": [],
            "error": str(e),
            "user": user
        })

@router.post("/projects", response_class=HTMLResponse)
async def create_project(
    request: Request,
    title: str = Form(...),
    ui_language: str = Form(...),
    target_language: str = Form(...)
):
    """Create new project and return HTMX partial"""
    user = await auth.get_current_user(request)
    if not user:
        return '<tr><td colspan="5" style="color: red;">Not authenticated</td></tr>'

    try:
        project = await db_helpers.create_project(title, ui_language, target_language, user['id'])
        return f"""
        <tr>
            <td>{project.get('id', 'N/A')}</td>
            <td><a href="/linguist/projects/{project.get('id')}">{project.get('title', '')}</a></td>
            <td>{project.get('ui_language', '')}</td>
            <td>{project.get('target_language', '')}</td>
            <td>{project.get('created_at', '')[:10] if project.get('created_at') else 'N/A'}</td>
        </tr>
        """
    except Exception as e:
        print(f"Error creating project: {e}")
        return f'<tr><td colspan="5" style="color: red;">Error: {str(e)}</td></tr>'

@router.get("/campaigns", response_class=HTMLResponse)
async def list_campaigns(request: Request):
    """List all campaigns"""
    user = await auth.get_current_user(request)
    redirect = auth.redirect_if_not_authenticated(user)
    if redirect:
        return redirect

    try:
        campaigns = await db_helpers.get_all_campaigns()
        projects = await db_helpers.get_all_projects()
        return templates.TemplateResponse("campaigns.html", {
            "request": request,
            "campaigns": campaigns,
            "projects": projects,
            "user": user
        })
    except Exception as e:
        print(f"Error in list_campaigns: {e}")
        return templates.TemplateResponse("campaigns.html", {
            "request": request,
            "campaigns": [],
            "projects": [],
            "error": str(e),
            "user": user
        })

@router.post("/campaigns", response_class=HTMLResponse)
async def create_campaign(
    request: Request,
    campaign_name: str = Form(...),
    project_id: int = Form(...),
    campaign_type: str = Form(...),
    active: Optional[str] = Form(None),
    campaign_file: Optional[UploadFile] = File(None)
):
    """Create new campaign and return HTMX partial"""
    user = await auth.get_current_user(request)
    if not user:
        return '<tr><td colspan="5" style="color: red;">Not authenticated</td></tr>'

    try:
        # Build description from campaign type and file data
        description = f"Campaign type: {campaign_type}"

        # Handle file upload if custom campaign
        if campaign_type == "custom" and campaign_file and campaign_file.filename:
            content = await campaign_file.read()
            file_content = content.decode('utf-8')

            if campaign_file.filename.endswith('.json'):
                file_data = json.loads(file_content)
                description += f" | File: {campaign_file.filename} ({len(file_data)} items)"
            elif campaign_file.filename.endswith('.csv'):
                csv_reader = csv.DictReader(StringIO(file_content))
                file_data = list(csv_reader)
                description += f" | File: {campaign_file.filename} ({len(file_data)} rows)"

        is_active = active == "on"
        campaign = await db_helpers.create_campaign(
            name=campaign_name,
            project_id=project_id,
            description=description,
            active=is_active
        )

        # Get project title for display
        project = await db_helpers.get_project_by_id(project_id)
        project_title = project.get('title', 'N/A') if project else 'N/A'

        return f"""
        <tr>
            <td>{campaign.get('id', 'N/A')}</td>
            <td>{campaign.get('name', '')}</td>
            <td>{project_title}</td>
            <td>{'✓' if campaign.get('active') else '✗'}</td>
            <td>{campaign.get('created_at', '')[:10] if campaign.get('created_at') else 'N/A'}</td>
        </tr>
        """
    except Exception as e:
        print(f"Error creating campaign: {e}")
        return f'<tr><td colspan="5" style="color: red;">Error: {str(e)}</td></tr>'

@router.get("/questions", response_class=HTMLResponse)
async def list_questions(request: Request):
    """List all questions"""
    user = await auth.get_current_user(request)
    redirect = auth.redirect_if_not_authenticated(user)
    if redirect:
        return redirect

    return templates.TemplateResponse("questions.html", {
        "request": request,
        "questions": [],
        "user": user
    })

@router.get("/responses", response_class=HTMLResponse)
async def list_responses(request: Request):
    """List all responses"""
    user = await auth.get_current_user(request)
    redirect = auth.redirect_if_not_authenticated(user)
    if redirect:
        return redirect

    try:
        responses = await db_helpers.get_all_responses()
        return templates.TemplateResponse("responses.html", {
            "request": request,
            "responses": responses,
            "user": user
        })
    except Exception as e:
        print(f"Error in list_responses: {e}")
        return templates.TemplateResponse("responses.html", {
            "request": request,
            "responses": [],
            "error": str(e),
            "user": user
        })
