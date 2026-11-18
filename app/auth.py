import os
from datetime import datetime, timedelta
import hmac
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlmodel import Session, select

from .database import get_session
from .models import AccountType, BannedAccount, User

APP_ENV = os.getenv("APP_ENV", "development").lower()
SECRET_KEY = os.getenv("SECRET_KEY", "development-only-insecure-change-before-deploy")
if APP_ENV in {"preview", "production"} and (len(SECRET_KEY) < 32 or SECRET_KEY.startswith("development-only")):
    raise RuntimeError("SECRET_KEY must contain at least 32 characters in preview/production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _password_version(hashed_password: str) -> str:
    return hmac.digest(SECRET_KEY.encode(), hashed_password.encode(), "sha256").hex()


def create_access_token(user_id: int, account_type: AccountType, hashed_password: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {
            "sub": str(user_id),
            "account_type": account_type.value,
            "pwd": _password_version(hashed_password),
            "exp": expire,
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants invalides ou expirés",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_error
        user_id_int = int(user_id)
    except (JWTError, ValueError):
        raise credentials_error

    user = session.get(User, user_id_int)
    if user is None:
        raise credentials_error
    token_password_version = payload.get("pwd")
    if not isinstance(token_password_version, str) or not hmac.compare_digest(
        token_password_version, _password_version(user.hashed_password)
    ):
        raise credentials_error
    active_ban = session.exec(
        select(BannedAccount).where(
            BannedAccount.user_id == user.id,
            BannedAccount.active == True,
        )
    ).first()
    if active_ban:
        raise HTTPException(status_code=403, detail="Ce compte est suspendu")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.account_type != AccountType.admin:
        raise HTTPException(status_code=403, detail="Accès réservé à l'administration")
    return user


def require_owner(user_id: int, user: User) -> None:
    if user.id != user_id and user.account_type != AccountType.admin:
        raise HTTPException(status_code=403, detail="Accès interdit")

def require_candidate_owner(candidate_id: int, session: Session, user: User):
    from .models import CandidateProfile

    candidate = session.get(CandidateProfile, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Profil candidat introuvable")
    if candidate.user_id != user.id and user.account_type != AccountType.admin:
        raise HTTPException(status_code=403, detail="Accès interdit")
    return candidate


def require_company_owner(company_id: int, session: Session, user: User):
    from .models import Company

    company = session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    owner = session.get(User, company.owner_user_id)
    if owner is None or (owner.account_type != AccountType.recruiter and user.account_type != AccountType.admin):
        raise HTTPException(status_code=403, detail="Un compte recruteur est requis")
    if company.owner_user_id != user.id and user.account_type != AccountType.admin:
        raise HTTPException(status_code=403, detail="Accès interdit")
    return company


def require_job_company_owner(job_id: int, session: Session, user: User):
    from .models import JobOffer

    job = session.get(JobOffer, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    require_company_owner(job.company_id, session, user)
    return job


def require_application_candidate_owner(application_id: int, session: Session, user: User):
    from .models import Application

    application = session.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    require_candidate_owner(application.candidate_id, session, user)
    return application


def require_application_company_owner(application_id: int, session: Session, user: User):
    from .models import Application

    application = session.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    require_job_company_owner(application.job_offer_id, session, user)
    return application


