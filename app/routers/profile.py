from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from ..database import get_session
from ..auth import get_current_user, require_owner
from ..models import CandidateProfile, Company, CompanyDirectorProfile, CandidateProject, SkillAssessment, User

router = APIRouter(prefix="/profile", tags=["profile"], dependencies=[Depends(get_current_user)])


class CandidateProfileUpsert(BaseModel):
    user_id: int
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    city: Optional[str] = None
    summary: Optional[str] = None
    skills: Optional[str] = None
    years_experience: Optional[int] = None
    cnps_matricule: Optional[str] = None


class UserProfileResponse(BaseModel):
    user_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    account_type: str
    candidate_profile_id: Optional[int] = None
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    city: Optional[str] = None
    summary: Optional[str] = None
    skills: Optional[str] = None
    years_experience: Optional[int] = None


@router.get("/me/{user_id}", response_model=UserProfileResponse)
def get_my_profile(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    require_owner(user_id, current_user)
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    candidate_profile = session.exec(
        select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    ).first()
    company = session.exec(
        select(Company).where(Company.owner_user_id == user_id)
    ).first()

    return UserProfileResponse(
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        account_type=user.account_type.value,
        candidate_profile_id=candidate_profile.id if candidate_profile else None,
        company_id=company.id if company else None,
        company_name=company.name if company else None,
        job_title=candidate_profile.job_title if candidate_profile else None,
        city=candidate_profile.city if candidate_profile else None,
        summary=candidate_profile.summary if candidate_profile else None,
        skills=candidate_profile.skills if candidate_profile else None,
        years_experience=candidate_profile.years_experience if candidate_profile else None,
    )


@router.put("/candidate", response_model=CandidateProfile)
def upsert_candidate_profile(payload: CandidateProfileUpsert, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """
    Correspond au bouton 'Enregistrer' de CreationProfilCandidatScreen.
    CrÃ©e le profil s'il n'existe pas encore, sinon le met Ã  jour.
    """
    require_owner(payload.user_id, current_user)
    if current_user.account_type.value not in ("candidate", "admin"):
        raise HTTPException(status_code=403, detail="Un compte candidat est requis")
    user = session.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    profile = session.exec(
        select(CandidateProfile).where(CandidateProfile.user_id == payload.user_id)
    ).first()

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
        session.add(user)

    data = payload.dict(exclude={"user_id", "full_name"})
    if profile:
        for field, value in data.items():
            if value is not None:
                setattr(profile, field, value)
    else:
        profile = CandidateProfile(user_id=payload.user_id, **data)

    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.get("/candidate/{candidate_id}")
def get_candidate_profile(candidate_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Correspond Ã  ProfilPublicCandidatScreen (vu par un recruteur ou le candidat lui-mÃªme)."""
    profile = session.get(CandidateProfile, candidate_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    user = session.get(User, profile.user_id)
    if user and user.id != current_user.id and current_user.account_type.value not in ("recruiter", "admin"):
        raise HTTPException(status_code=403, detail="Accès réservé au candidat concerné ou à un recruteur")
    assessments = session.exec(select(SkillAssessment).where(SkillAssessment.candidate_id == profile.id).order_by(SkillAssessment.created_at.desc())).all()
    projects = session.exec(select(CandidateProject).where(CandidateProject.candidate_id == profile.id).order_by(CandidateProject.created_at.desc())).all()
    return {
        "assessments": [{"id": item.id, "test_name": item.test_name, "score": item.score, "total_questions": item.total_questions, "percentage": item.percentage, "badge": item.badge, "created_at": item.created_at.isoformat()} for item in assessments],
        "projects": [{"id": item.id, "title": item.title, "description": item.description, "skills": item.skills.split(", ") if item.skills else [], "url": item.url, "created_at": item.created_at.isoformat()} for item in projects],

        "id": profile.id,
        "full_name": user.full_name if user else None,
        # Email addresses are private; expose them only to the profile owner.
        "email": user.email if user and user.id == current_user.id else None,
        "job_title": profile.job_title,
        "city": profile.city,
        "summary": profile.summary,
        "skills": profile.skills.split(",") if profile.skills else [],
        "years_experience": profile.years_experience,
    }


class CompanyUpsert(BaseModel):
    owner_user_id: int
    name: str
    sector: Optional[str] = None
    description: Optional[str] = None
    cnps_employer_matricule: Optional[str] = None


@router.put("/company", response_model=Company)
def upsert_company(payload: CompanyUpsert, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Correspond Ã  CreationProfilEntrepriseScreen."""
    require_owner(payload.owner_user_id, current_user)
    if current_user.account_type.value not in ("recruiter", "admin"):
        raise HTTPException(status_code=403, detail="Un compte recruteur est requis")
    owner = session.get(User, payload.owner_user_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    company = session.exec(
        select(Company).where(Company.owner_user_id == payload.owner_user_id)
    ).first()

    data = payload.dict(exclude={"owner_user_id"})
    if company:
        for field, value in data.items():
            if value is not None:
                setattr(company, field, value)
    else:
        company = Company(owner_user_id=payload.owner_user_id, kyc_verified=False, **data)

    session.add(company)
    session.commit()
    session.refresh(company)
    return company


@router.get("/company/{company_id}", response_model=Company)
def get_company(company_id: int, session: Session = Depends(get_session)):
    """Correspond Ã  ProfilEntrepriseScreen."""
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    return company












class CompanyDirectorProfileInput(BaseModel):
    full_name: str
    title: str
    professional_email: Optional[str] = None
    phone: Optional[str] = None


def get_owned_company(current_user: User, session: Session) -> Company:
    if current_user.account_type.value not in ("recruiter", "admin"):
        raise HTTPException(status_code=403, detail="Un compte recruteur est requis")
    company = session.exec(select(Company).where(Company.owner_user_id == current_user.id)).first()
    if not company:
        raise HTTPException(status_code=404, detail="Créez d’abord le profil de votre entreprise")
    return company


@router.get("/company/me/director", response_model=Optional[CompanyDirectorProfile])
def get_company_director(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    company = get_owned_company(current_user, session)
    return session.exec(select(CompanyDirectorProfile).where(CompanyDirectorProfile.company_id == company.id)).first()


@router.put("/company/me/director", response_model=CompanyDirectorProfile)
def upsert_company_director(payload: CompanyDirectorProfileInput, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    company = get_owned_company(current_user, session)
    full_name = payload.full_name.strip()
    title = payload.title.strip()
    if not full_name or not title:
        raise HTTPException(status_code=400, detail="Le nom et la fonction sont obligatoires")
    profile = session.exec(select(CompanyDirectorProfile).where(CompanyDirectorProfile.company_id == company.id)).first()
    values = {
        "full_name": full_name,
        "title": title,
        "professional_email": payload.professional_email.strip() or None if payload.professional_email else None,
        "phone": payload.phone.strip() or None if payload.phone else None,
        "updated_at": datetime.utcnow(),
    }
    if profile:
        for key, value in values.items():
            setattr(profile, key, value)
    else:
        profile = CompanyDirectorProfile(company_id=company.id, **values)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile
