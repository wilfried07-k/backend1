from io import BytesIO
from pathlib import PurePath
from typing import Optional
from urllib.parse import quote
from zipfile import ZipFile, is_zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlmodel import Session, select
from pydantic import BaseModel
from ..database import get_session
from ..auth import get_current_user, require_candidate_owner, require_job_company_owner, require_application_candidate_owner, require_application_company_owner
from ..models import Application, ApplicationDocument, JobOffer, CandidateProfile, User
from ..routers.matching import compute_match_score

router = APIRouter(prefix="/applications", tags=["applications"], dependencies=[Depends(get_current_user)])

MAX_APPLICATION_FILE_SIZE = 10 * 1024 * 1024
DOCUMENT_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class ApplicationStatusUpdate(BaseModel):
    status: str   # Envoyée / En examen / Entretien / Refusée / Acceptée


class CompanyApplicationSummary(BaseModel):
    application_id: int
    candidate_id: int
    full_name: Optional[str]
    job_title: Optional[str]
    status: str
    match_score: Optional[float]
    job_offer_id: int


class ApplicationReview(BaseModel):
    application_id: int
    status: str
    motivation_message: Optional[str]
    cv_file_name: Optional[str]
    motivation_letter_file_name: Optional[str]


async def read_application_document(upload: UploadFile) -> tuple[str, str, bytes]:
    if not upload.filename:
        raise HTTPException(status_code=400, detail="Le nom d’un document est manquant")

    file_name = PurePath(upload.filename.replace("\\", "/")).name
    extension = PurePath(file_name).suffix.lower()
    content_type = DOCUMENT_CONTENT_TYPES.get(extension)
    if not content_type:
        raise HTTPException(status_code=400, detail="Les documents doivent être au format PDF ou DOCX")

    content = await upload.read(MAX_APPLICATION_FILE_SIZE + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Le document est vide")
    if len(content) > MAX_APPLICATION_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Chaque document doit faire 10 Mo maximum")

    if extension == ".pdf" and b"%PDF-" not in content[:1024]:
        raise HTTPException(status_code=400, detail="Le fichier sélectionné n’est pas un PDF valide")
    if extension == ".docx":
        if not is_zipfile(BytesIO(content)):
            raise HTTPException(status_code=400, detail="Le fichier sélectionné n’est pas un DOCX valide")
        with ZipFile(BytesIO(content)) as archive:
            if "[Content_Types].xml" not in archive.namelist() or "word/document.xml" not in archive.namelist():
                raise HTTPException(status_code=400, detail="Le fichier sélectionné n’est pas un DOCX valide")

    return file_name[:255], content_type, content


@router.post("", response_model=Application)
async def apply(
    candidate_id: int = Form(...),
    job_offer_id: int = Form(...),
    motivation_message: Optional[str] = Form(default=None, max_length=4000),
    cv_file: UploadFile = File(...),
    motivation_letter_file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """Correspond au bouton d'envoi de CandidatureRapideScreen / CandidatureSpontaneeScreen."""
    candidate = require_candidate_owner(candidate_id, session, current_user)
    job = session.get(JobOffer, job_offer_id)
    if not candidate or not job:
        raise HTTPException(status_code=404, detail="Candidat ou offre introuvable")

    existing = session.exec(
        select(Application).where(
            Application.candidate_id == candidate_id,
            Application.job_offer_id == job_offer_id,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vous avez dÃ©jÃ  postulÃ© Ã  cette offre")

    candidate_text = " ".join(filter(None, [candidate.job_title, candidate.summary, candidate.skills]))
    job_text = " ".join(filter(None, [job.title, job.description, job.requirements]))
    score = compute_match_score(candidate_text, job_text)
    cv_name, cv_content_type, cv_content = await read_application_document(cv_file)
    letter_name, letter_content_type, letter_content = await read_application_document(motivation_letter_file)

    application = Application(
        candidate_id=candidate_id,
        job_offer_id=job_offer_id,
        motivation_message=motivation_message.strip() if motivation_message and motivation_message.strip() else None,
        match_score=score,
    )
    session.add(application)
    session.flush()
    session.add_all([
        ApplicationDocument(
            application_id=application.id,
            document_type="cv",
            file_name=cv_name,
            content_type=cv_content_type,
            content=cv_content,
        ),
        ApplicationDocument(
            application_id=application.id,
            document_type="motivation_letter",
            file_name=letter_name,
            content_type=letter_content_type,
            content=letter_content,
        ),
    ])
    session.commit()
    session.refresh(application)
    return application


@router.get("/candidate/{candidate_id}")
def list_candidate_applications(candidate_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond Ã  SuiviCandidaturesScreen (liste + statistiques)."""
    require_candidate_owner(candidate_id, session, current_user)
    applications = session.exec(select(Application).where(Application.candidate_id == candidate_id)).all()

    results = []
    for app_ in applications:
        job = session.get(JobOffer, app_.job_offer_id)
        from ..models import Company
        company = session.get(Company, job.company_id) if job else None
        results.append({
            "id": app_.id,
            "job_offer_id": app_.job_offer_id,
            "job_title": job.title if job else "Offre supprimÃ©e",
            "company_name": company.name if company else None,
            "company_id": job.company_id if job else None,
            "status": app_.status,
            "match_score": app_.match_score,
            "created_at": app_.created_at.isoformat(),
        })
    return results


@router.get("/job/{job_offer_id}")
def list_job_applications(job_offer_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond au pipeline de GestionDesCandidatsScreen (candidats pour une offre)."""
    require_job_company_owner(job_offer_id, session, current_user)
    applications = session.exec(select(Application).where(Application.job_offer_id == job_offer_id)).all()
    application_ids = [app_.id for app_ in applications]
    documents = session.exec(
        select(ApplicationDocument).where(ApplicationDocument.application_id.in_(application_ids))
    ).all() if application_ids else []
    document_names_by_application: dict[int, dict[str, str]] = {}
    for document in documents:
        document_names_by_application.setdefault(document.application_id, {})[document.document_type] = document.file_name

    results = []
    for app_ in applications:
        candidate = session.get(CandidateProfile, app_.candidate_id)
        user = session.get(User, candidate.user_id) if candidate else None
        document_names = document_names_by_application.get(app_.id, {})
        results.append({
            "application_id": app_.id,
            "candidate_id": app_.candidate_id,
            "full_name": user.full_name if user else "Candidat",
            "job_title": candidate.job_title if candidate else None,
            "status": app_.status,
            "match_score": app_.match_score,
            "job_offer_id": app_.job_offer_id,
            "motivation_message": app_.motivation_message,
            "cv_file_name": document_names.get("cv"),
            "motivation_letter_file_name": document_names.get("motivation_letter"),
        })
    return results


@router.get("/{application_id}/review", response_model=ApplicationReview)
def get_application_review(
    application_id: int,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    application = require_application_company_owner(application_id, session, current_user)
    documents = session.exec(
        select(ApplicationDocument).where(ApplicationDocument.application_id == application_id)
    ).all()
    document_names = {document.document_type: document.file_name for document in documents}
    return ApplicationReview(
        application_id=application.id,
        status=application.status,
        motivation_message=application.motivation_message,
        cv_file_name=document_names.get("cv"),
        motivation_letter_file_name=document_names.get("motivation_letter"),
    )


@router.get("/{application_id}/documents/{document_type}")
def get_application_document(
    application_id: int,
    document_type: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    if document_type not in ("cv", "motivation_letter"):
        raise HTTPException(status_code=404, detail="Document introuvable")
    application = session.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    if current_user.account_type.value == "candidate":
        require_application_candidate_owner(application_id, session, current_user)
    else:
        require_application_company_owner(application_id, session, current_user)

    document = session.exec(
        select(ApplicationDocument).where(
            ApplicationDocument.application_id == application_id,
            ApplicationDocument.document_type == document_type,
        )
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document introuvable")

    fallback_name = "document.pdf" if document.file_name.lower().endswith(".pdf") else "document.docx"
    return Response(
        content=document.content,
        media_type=document.content_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{fallback_name}\"; filename*=UTF-8''{quote(document.file_name)}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.patch("/{application_id}/status", response_model=Application)
def update_application_status(
    application_id: int, payload: ApplicationStatusUpdate, session: Session = Depends(get_session), current_user=Depends(get_current_user)
):
    """
    Correspond au bouton 'Avancer' dans le pipeline Kanban de
    GestionDesCandidatsScreen, et dÃ©clenche la notification au candidat
    (Ã  brancher : crÃ©ation d'une Notification ici).
    """
    application = require_application_company_owner(application_id, session, current_user)
    if not application:
        raise HTTPException(status_code=404, detail="Candidature introuvable")

    application.status = payload.status
    session.add(application)
    session.commit()
    session.refresh(application)
    return application


@router.delete("/{application_id}")
def withdraw_application(application_id: int, session: Session = Depends(get_session), current_user=Depends(get_current_user)):
    """Correspond au bouton 'Retirer ma candidature' de DetailsCandidatureScreen."""
    application = require_application_candidate_owner(application_id, session, current_user)
    if not application:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    documents = session.exec(
        select(ApplicationDocument).where(ApplicationDocument.application_id == application_id)
    ).all()
    for document in documents:
        session.delete(document)
    session.delete(application)
    session.commit()
    return {"withdrawn": True}



