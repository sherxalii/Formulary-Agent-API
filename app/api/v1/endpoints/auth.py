from fastapi import APIRouter, Depends, HTTPException, Request, status, Response
from app.core.rate_limiter import limiter
from app.core.dependencies import get_auth_service
from app.core.email_service import EmailService
from app.core.oauth import oauth
from app.core.config import settings
from app.models.auth_models import (
    UserCreate,
    UserLogin,
    Token,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordChangeRequest,
    VerifyTokenRequest,
)

router = APIRouter()
email_service = EmailService()

@router.post('/auth/register', tags=['auth'])
@limiter.limit('5/minute')
async def register_user(response: Response, request: Request, user: UserCreate, auth_service=Depends(get_auth_service)):

    try:
        created_user = auth_service.register_user(user.name, user.email, user.password, user.role)
        access_token = auth_service.create_access_token_for_user(created_user)
        
        # Send confirmation email
        email_body = (
            f"Hello {user.name},\n\n"
            f"Welcome to MediFormulary! Your account has been successfully registered.\n"
            "You can now access our clinical drug safety platform and formulary search.\n\n"
            "Best regards,\n"
            "The MediFormulary Team"
        )
        email_service.send_email(user.email, 'Welcome to MediFormulary!', email_body)

        # Set secure HTTP-only cookie

        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite="lax",
            max_age=3600 * 24 * 7
        )
        
        return {
            'success': True,
            'access_token': access_token,
            'token_type': 'bearer',
            'user': created_user,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

@router.post('/auth/login', tags=['auth'])
@limiter.limit('10/minute')
async def login_user(response: Response, request: Request, credentials: UserLogin, auth_service=Depends(get_auth_service)):
    user = auth_service.authenticate_user(credentials.email, credentials.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password')
    access_token = auth_service.create_access_token_for_user(user)
    
    # Set secure HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=3600 * 24 * 7
    )
    
    return {
        'success': True,
        'access_token': access_token,
        'token_type': 'bearer',
        'user': user,
    }

@router.post('/auth/verify', tags=['auth'])
@limiter.limit('10/minute')
async def verify_user(request: Request, request_data: VerifyTokenRequest, auth_service=Depends(get_auth_service)):
    if not auth_service.verify_user(request_data.token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid or expired verification token')
    return {'success': True, 'message': 'Email verified successfully.'}

@router.post('/auth/password-reset', tags=['auth'])
@limiter.limit('5/minute')
async def request_password_reset(request: Request, request_data: PasswordResetRequest, auth_service=Depends(get_auth_service)):
    try:
        reset_token = auth_service.request_password_reset(request_data.email)
        email_body = (
            f"You requested a password reset for {request_data.email}.\n\n"
            f"Use this token to reset your password: {reset_token}\n\n"
            "If you did not request this, please ignore this message."
        )
        email_service.send_email(request_data.email, 'Password Reset Request', email_body)
        return {'success': True, 'message': 'Password reset sent to your email address.'}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

@router.post('/auth/password-reset/confirm', tags=['auth'])
@limiter.limit('5/minute')
async def confirm_password_reset(request: Request, request_data: PasswordResetConfirm, auth_service=Depends(get_auth_service)):
    if not auth_service.reset_password(request_data.token, request_data.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid or expired reset token')
    return {'success': True, 'message': 'Password has been reset successfully.'}

@router.post('/auth/password-change', tags=['auth'])
@limiter.limit('10/minute')
async def change_password(request: Request, request_data: PasswordChangeRequest, auth_service=Depends(get_auth_service)):
    if not auth_service.change_password(request_data.email, request_data.current_password, request_data.new_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Current password is incorrect')
    return {'success': True, 'message': 'Password changed successfully.'}

@router.get('/auth/login/google', tags=['auth'])
async def login_google(request: Request):
    """Initiate Google OAuth flow."""
    redirect_uri = request.url_for('auth_callback_google')
    # Workaround for proxy/HTTPS issues if needed
    if settings.ENVIRONMENT == "production":
        redirect_uri = str(redirect_uri).replace("http://", "https://")
    return await oauth.google.authorize_redirect(request, redirect_uri)

from fastapi.responses import RedirectResponse
import json
import urllib.parse

@router.get('/auth/callback/google', name='auth_callback_google', tags=['auth'])
async def auth_callback_google(request: Request, auth_service=Depends(get_auth_service)):
    """Handle Google OAuth callback."""
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        if not user_info:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Failed to retrieve user info from Google.')
        
        user = auth_service.get_or_create_user_from_oauth(
            name=user_info.get('name'),
            email=user_info.get('email'),
            provider='google'
        )
        
        access_token = auth_service.create_access_token_for_user(user)
        
        # Build redirect URL with token and user data
        frontend_url = "http://localhost:5173/auth/callback" # Update if needed
        user_json = urllib.parse.quote(json.dumps(user))
        redirect_url = f"{frontend_url}?token={access_token}&user={user_json}"
        
        redirect_response = RedirectResponse(url=redirect_url)
        
        # Set secure HTTP-only cookie in redirect
        redirect_response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite="lax",
            max_age=3600 * 24 * 7
        )
        
        return redirect_response
    except Exception as e:
        # On error, redirect back to login with error message
        error_msg = urllib.parse.quote(str(e))
        return RedirectResponse(url=f"http://localhost:5173/signin?error={error_msg}")
