import hashlib
import hmac
import logging
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr, Field
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token
from ..database import get_session
from ..models import User, AccountType, ReferralCode, Referral, CandidateProfile, PasswordResetCode
from ..auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
DEFAULT_GOOGLE_CLIENT_ID = "45847298670-fakktka7o2vpe16uejg0g5onhebmpkas.apps.googleusercontent.com"


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    password: str = Field(min_length=8)
    account_type: AccountType
    referral_code: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    account_type: AccountType


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=1)
    account_type: AccountType


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account_type: AccountType
    user_id: int


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class PasswordResetCodeRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)


def send_password_reset_code(email: str, code: str):
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    if not host or not sender or not username or not password:
        raise RuntimeError("SMTP email configuration is missing")

    message = EmailMessage()
    message["Subject"] = "Réinitialisation de votre mot de passe EmploiCamer"
    message["From"] = sender
    message["To"] = email
    message.set_content(f"Votre code de réinitialisation est {code}. Il expire dans 15 minutes.")

    port = int(os.getenv("SMTP_PORT", "587"))
    tls_context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=10, context=tls_context) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls(context=tls_context)
            smtp.login(username, password)
            smtp.send_message(message)


@router.post("/password/forgot")
def request_password_reset(payload: PasswordResetCodeRequest, session: Session = Depends(get_session)):
    if not all(os.getenv(key, "").strip() for key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")):
        raise HTTPException(status_code=503, detail="La récupération par email n’est pas configurée sur le serveur")
    user = session.exec(select(User).where(User.email == payload.email.lower())).first()
    if user:
        code = f"{secrets.randbelow(1_000_000):06d}"
        reset_code = PasswordResetCode(
            user_id=user.id,
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        )
        for previous in session.exec(select(PasswordResetCode).where(PasswordResetCode.user_id == user.id)).all():
            session.delete(previous)
        session.add(reset_code)
        session.commit()
        try:
            send_password_reset_code(user.email, code)
        except Exception:
            logger.exception("Password reset email delivery failed")
            session.delete(reset_code)
            session.commit()
            raise HTTPException(status_code=503, detail="Le service email est temporairement indisponible")
    return {"message": "Si un compte correspond à cette adresse, un code de réinitialisation a été envoyé."}


@router.post("/password/reset")
def reset_password(payload: PasswordResetRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == payload.email.lower())).first()
    if not user:
        raise HTTPException(status_code=400, detail="Code invalide ou expiré")
    reset_code = session.exec(
        select(PasswordResetCode).where(PasswordResetCode.user_id == user.id)
    ).first()
    if not reset_code or reset_code.expires_at <= datetime.utcnow() or reset_code.attempts >= 5:
        raise HTTPException(status_code=400, detail="Code invalide ou expiré")

    code_hash = hashlib.sha256(payload.code.encode()).hexdigest()
    if not hmac.compare_digest(reset_code.code_hash, code_hash):
        reset_code.attempts += 1
        session.add(reset_code)
        session.commit()
        raise HTTPException(status_code=400, detail="Code invalide ou expiré")

    user.hashed_password = hash_password(payload.new_password)
    session.add(user)
    session.delete(reset_code)
    session.commit()
    return {"updated": True}


@router.post("/password/change")
def change_password(payload: PasswordChangeRequest, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Le mot de passe actuel est incorrect")
    current_user.hashed_password = hash_password(payload.new_password)
    session.add(current_user)
    session.commit()
    return {"updated": True}

@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, session: Session = Depends(get_session)):
    """Correspond au bouton 'CrÃ©er mon compte' de InscriptionScreen."""
    if payload.account_type == AccountType.admin:
        raise HTTPException(status_code=403, detail="La création de comptes administrateur est désactivée")

    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un compte existe dÃ©jÃ  avec cet email")

    referral_code = None
    if payload.referral_code and payload.referral_code.strip():
        code = payload.referral_code.strip().upper()
        referral_code = session.exec(select(ReferralCode).where(ReferralCode.code == code)).first()
        if not referral_code:
            raise HTTPException(status_code=400, detail="Code de parrainage invalide")

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        hashed_password=hash_password(payload.password),
        account_type=payload.account_type,
    )
    session.add(user)
    session.flush()
    if referral_code:
        session.add(Referral(referrer_user_id=referral_code.user_id, referred_user_id=user.id, referral_code=referral_code.code))
    if user.account_type == AccountType.candidate:
        session.add(CandidateProfile(user_id=user.id))
    session.commit()
    session.refresh(user)

    token = create_access_token(user.id, user.account_type)
    return TokenResponse(access_token=token, account_type=user.account_type, user_id=user.id)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    """Correspond au bouton 'Se connecter' de ConnexionScreen (avec le sÃ©lecteur candidat/recruteur)."""
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

    if user.account_type != payload.account_type:
        raise HTTPException(
            status_code=403,
            detail=f"Ce compte est un compte {user.account_type.value}, pas {payload.account_type.value}",
        )

    token = create_access_token(user.id, user.account_type)
    return TokenResponse(access_token=token, account_type=user.account_type, user_id=user.id)


@router.post("/google", response_model=TokenResponse)
def login_with_google(payload: GoogleLoginRequest, session: Session = Depends(get_session)):
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip() or DEFAULT_GOOGLE_CLIENT_ID
    if payload.account_type == AccountType.admin:
        raise HTTPException(status_code=403, detail="La connexion Google est réservée aux candidats et recruteurs")

    try:
        claims = google_id_token.verify_oauth2_token(
            payload.id_token,
            GoogleRequest(),
            google_client_id,
        )
    except (ValueError, GoogleAuthError):
        raise HTTPException(status_code=401, detail="Jeton Google invalide ou expiré")

    email = claims.get("email")
    if not email or claims.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="L’adresse e-mail Google n’est pas vérifiée")

    normalized_email = email.lower()
    user = session.exec(select(User).where(User.email == normalized_email)).first()
    if user:
        if user.account_type != payload.account_type:
            raise HTTPException(
                status_code=403,
                detail=f"Ce compte est un compte {user.account_type.value}, pas {payload.account_type.value}",
            )
    else:
        user = User(
            full_name=claims.get("name") or normalized_email.split("@")[0],
            email=normalized_email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            account_type=payload.account_type,
        )
        session.add(user)
        session.flush()
        if user.account_type == AccountType.candidate:
            session.add(CandidateProfile(user_id=user.id))
        session.commit()
        session.refresh(user)

    token = create_access_token(user.id, user.account_type)
    return TokenResponse(access_token=token, account_type=user.account_type, user_id=user.id)



