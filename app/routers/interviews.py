from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel, Field as PydanticField
from ..database import get_session
from ..auth import get_current_user, require_candidate_owner, require_company_owner, require_job_company_owner
from ..models import Interview, InterviewReport, Application, JobOffer, Company, CandidateProfile, User

router = APIRouter(prefix="/interviews", tags=["interviews"], dependencies=[Depends(get_current_user)])


class InterviewCreate(BaseModel):
    application_id: int
    scheduled_at: datetime
    mode: str = "video"
    location_or_link: Optional[str] = None


@router.post("", response_model=Interview)
def schedule_interview(payload: InterviewCreate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """
    Correspond au bouton 'Confirmer l'entretien' de PlanifierEntretienScreen.
    Met aussi la candidature au statut 'Entretien'.
    """
    application = session.get(Application, payload.application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Candidature introuvable")

    require_job_company_owner(application.job_offer_id, session, current_user)
    interview = Interview(**payload.dict())
    session.add(interview)

    application.status = "Entretien"
    session.add(application)

    session.commit()
    session.refresh(interview)
    return interview


@router.get("/candidate/{candidate_id}")
def list_candidate_interviews(candidate_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  CalendrierCandidatScreen."""
    require_candidate_owner(candidate_id, session, current_user)
    applications = session.exec(select(Application).where(Application.candidate_id == candidate_id)).all()
    application_ids = [a.id for a in applications]
    if not application_ids:
        return []

    interviews = session.exec(select(Interview).where(Interview.application_id.in_(application_ids))).all()

    results = []
    for interview in interviews:
        application = session.get(Application, interview.application_id)
        job = session.get(JobOffer, application.job_offer_id) if application else None
        company = session.get(Company, job.company_id) if job else None
        results.append({
            "interview_id": interview.id,
            "application_id": application.id if application else None,
            "candidate_id": candidate.id if candidate else None,
            "job_title": job.title if job else None,
            "company_name": company.name if company else None,
            "scheduled_at": interview.scheduled_at.isoformat(),
            "mode": interview.mode,
            "location_or_link": interview.location_or_link,
            "status": interview.status,
        })
    return results


@router.get("/company/{company_id}")
def list_company_interviews(company_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  GestionEntretiensVideoScreen cÃ´tÃ© recruteur."""
    require_company_owner(company_id, session, current_user)
    jobs = session.exec(select(JobOffer).where(JobOffer.company_id == company_id)).all()
    job_ids = [j.id for j in jobs]
    if not job_ids:
        return []

    applications = session.exec(select(Application).where(Application.job_offer_id.in_(job_ids))).all()
    application_ids = [a.id for a in applications]
    if not application_ids:
        return []

    interviews = session.exec(select(Interview).where(Interview.application_id.in_(application_ids))).all()

    results = []
    for interview in interviews:
        report = session.exec(select(InterviewReport).where(InterviewReport.interview_id == interview.id)).first()
        application = session.get(Application, interview.application_id)
        candidate = session.get(CandidateProfile, application.candidate_id) if application else None
        user = session.get(User, candidate.user_id) if candidate else None
        job = session.get(JobOffer, application.job_offer_id) if application else None
        company = session.get(Company, job.company_id) if job else None
        results.append({
            "interview_id": interview.id,
            "application_id": application.id if application else None,
            "candidate_id": candidate.id if candidate else None,
            "job_title": job.title if job else None,
            "company_name": company.name if company else None,
            "candidate_name": user.full_name if user else None,
            "scheduled_at": interview.scheduled_at.isoformat(),
            "mode": interview.mode,
            "location_or_link": interview.location_or_link,
            "status": interview.status,
            "report_status": report.status if report else None,
        })
    return results


class InterviewStatusUpdate(BaseModel):
    status: str   # PlanifiÃ© / TerminÃ© / AnnulÃ©


@router.patch("/{interview_id}", response_model=Interview)
def update_interview_status(interview_id: int, payload: InterviewStatusUpdate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    interview = session.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Entretien introuvable")
    application = session.get(Application, interview.application_id)
    if application:
        if current_user.account_type.value == "candidate":
            require_candidate_owner(application.candidate_id, session, current_user)
        else:
            require_job_company_owner(application.job_offer_id, session, current_user)
    interview.status = payload.status
    session.add(interview)
    session.commit()
    session.refresh(interview)
    return interview




class InterviewReportUpdate(BaseModel):
    notes: Optional[str] = PydanticField(default=None, max_length=4000)
    positives: Optional[str] = PydanticField(default=None, max_length=4000)
    concerns: Optional[str] = PydanticField(default=None, max_length=4000)
    technical_rating: Optional[int] = PydanticField(default=None, ge=0, le=5)
    communication_rating: Optional[int] = PydanticField(default=None, ge=0, le=5)
    soft_skills_rating: Optional[int] = PydanticField(default=None, ge=0, le=5)
    impressions: Optional[str] = PydanticField(default=None, max_length=4000)
    recommendation: Optional[str] = None
    status: str = "Brouillon"


def require_interview_company_owner(interview_id: int, session: Session, current_user):
    interview = session.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Entretien introuvable")
    application = session.get(Application, interview.application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    require_job_company_owner(application.job_offer_id, session, current_user)
    return interview


@router.get("/{interview_id}/report", response_model=Optional[InterviewReport])
def get_interview_report(interview_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    require_interview_company_owner(interview_id, session, current_user)
    return session.exec(select(InterviewReport).where(InterviewReport.interview_id == interview_id)).first()


@router.put("/{interview_id}/report", response_model=InterviewReport)
def save_interview_report(interview_id: int, payload: InterviewReportUpdate, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    require_interview_company_owner(interview_id, session, current_user)
    if payload.recommendation not in (None, "hire", "further", "reject"):
        raise HTTPException(status_code=400, detail="Recommandation invalide")
    if payload.status not in ("Brouillon", "Soumis", "Validé", "À réviser"):
        raise HTTPException(status_code=400, detail="Statut de rapport invalide")
    report = session.exec(select(InterviewReport).where(InterviewReport.interview_id == interview_id)).first()
    values = payload.dict(exclude_unset=True)
    if report:
        for key, value in values.items():
            setattr(report, key, value)
        report.updated_at = datetime.utcnow()
    else:
        report = InterviewReport(interview_id=interview_id, recruiter_user_id=current_user.id, **values)
    session.add(report)
    session.commit()
    session.refresh(report)
    return report