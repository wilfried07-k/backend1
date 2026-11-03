from datetime import datetime, timedelta
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel, Field as PydanticField
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError
from ..database import get_session
from ..auth import require_admin
from ..models import ModerationReport, BannedAccount, AccountType, BillingPayment, BillingSubscription, Company, JobOffer, CompanyKycReview, MarketingCampaign, User

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class AdminReportResponse(BaseModel):
    id: int
    job_offer_id: Optional[int] = None
    reported_user_id: Optional[int] = None
    reported_by_user_id: int
    reason: str
    status: str
    created_at: datetime
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    reporter_name: Optional[str] = None
    reported_user_name: Optional[str] = None


@router.get("/reports", response_model=list[AdminReportResponse])
def list_reports(status: str = "En attente", session: Session = Depends(get_session)):
    reports = session.exec(select(ModerationReport).where(ModerationReport.status == status).order_by(ModerationReport.created_at.desc())).all()
    results = []
    for report in reports:
        job = session.get(JobOffer, report.job_offer_id) if report.job_offer_id else None
        company = session.get(Company, job.company_id) if job else None
        reporter = session.get(User, report.reported_by_user_id)
        reported_user = session.get(User, report.reported_user_id) if report.reported_user_id else None
        results.append(AdminReportResponse(
            id=report.id, job_offer_id=report.job_offer_id, reported_user_id=report.reported_user_id,
            reported_by_user_id=report.reported_by_user_id, reason=report.reason,
            status=report.status, created_at=report.created_at,
            job_title=job.title if job else None, company_name=company.name if company else None,
            reporter_name=reporter.full_name if reporter else None,
            reported_user_name=reported_user.full_name if reported_user else None,
        ))
    return results

class ReportResolve(BaseModel):
    status: str            # RÃ©solu / EscaladÃ©
    remove_job: bool = False


@router.patch("/reports/{report_id}")
def resolve_report(report_id: int, payload: ReportResolve, session: Session = Depends(get_session)):
    """Correspond aux boutons 'Ignorer' / 'Supprimer l'offre' de ModerationLitigesScreen."""
    report = session.get(ModerationReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Signalement introuvable")

    report.status = payload.status
    session.add(report)

    if payload.remove_job and report.job_offer_id:
        job = session.get(JobOffer, report.job_offer_id)
        if job:
            job.status = "FermÃ©"
            session.add(job)

    session.commit()
    return {"updated": True}


class KycCompanyResponse(BaseModel):
    id: int
    owner_user_id: int
    name: str
    sector: Optional[str] = None
    description: Optional[str] = None
    cnps_employer_matricule: Optional[str] = None
    kyc_verified: bool
    review_status: str
    review_notes: Optional[str] = None


@router.get("/kyc/pending", response_model=list[KycCompanyResponse])
def list_pending_kyc(session: Session = Depends(get_session)):
    companies = session.exec(select(Company).where(Company.kyc_verified == False)).all()
    results = []
    for company in companies:
        review = session.exec(select(CompanyKycReview).where(CompanyKycReview.company_id == company.id)).first()
        results.append(KycCompanyResponse(
            id=company.id, owner_user_id=company.owner_user_id, name=company.name,
            sector=company.sector, description=company.description,
            cnps_employer_matricule=company.cnps_employer_matricule,
            kyc_verified=company.kyc_verified,
            review_status=review.status if review else "En attente",
            review_notes=review.notes if review else None,
        ))
    return results


@router.patch("/kyc/{company_id}")
def review_kyc(company_id: int, approve: bool, notes: Optional[str] = None, session: Session = Depends(get_session), admin_user: User = Depends(require_admin)):
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Entreprise introuvable")
    company.kyc_verified = approve
    review = session.exec(select(CompanyKycReview).where(CompanyKycReview.company_id == company_id)).first()
    if not review:
        review = CompanyKycReview(company_id=company_id, reviewed_by_user_id=admin_user.id)
    review.reviewed_by_user_id = admin_user.id
    review.status = "Validé" if approve else "Compléments requis"
    review.notes = notes.strip() if notes and notes.strip() else None
    review.updated_at = datetime.utcnow()
    session.add(company)
    session.add(review)
    session.commit()
    return {"company_id": company_id, "kyc_verified": company.kyc_verified, "review_status": review.status}

class BanRequest(BaseModel):
    user_id: int
    reason: str
    definitive: bool = False


@router.post("/ban", response_model=BannedAccount)
def ban_user(payload: BanRequest, session: Session = Depends(get_session)):
    """Correspond Ã  GestionBannissementsScreen et BannissementDefinitifScreen (double confirmation faite cÃ´tÃ© app)."""
    user = session.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    existing = session.exec(select(BannedAccount).where(BannedAccount.user_id == payload.user_id)).first()
    if existing:
        existing.reason = payload.reason
        existing.definitive = payload.definitive
        existing.active = True
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    banned = BannedAccount(user_id=payload.user_id, reason=payload.reason, definitive=payload.definitive)
    session.add(banned)
    session.commit()
    session.refresh(banned)
    return banned


@router.get("/banned", response_model=list[BannedAccount])
def list_banned(session: Session = Depends(get_session)):
    """Correspond Ã  la liste de GestionBannissementsScreen."""
    return session.exec(select(BannedAccount).where(BannedAccount.active == True)).all()


@router.patch("/unban/{user_id}")
def unban_user(user_id: int, session: Session = Depends(get_session)):
    """Correspond au bouton 'RÃ©habiliter' de GestionBannissementsScreen."""
    banned = session.exec(select(BannedAccount).where(BannedAccount.user_id == user_id)).first()
    if not banned:
        raise HTTPException(status_code=404, detail="Compte non banni")
    if banned.definitive:
        raise HTTPException(status_code=403, detail="Bannissement dÃ©finitif, rÃ©habilitation impossible")
    banned.active = False
    session.add(banned)
    session.commit()
    return {"unbanned": True}







@router.get("/dashboard/summary")
def dashboard_summary(session: Session = Depends(get_session)):
    """Operational counters for the admin dashboard; no estimated billing data."""
    from sqlalchemy import func

    return {
        "users": session.exec(select(func.count(User.id))).one(),
        "open_jobs": session.exec(select(func.count(JobOffer.id)).where(JobOffer.status == "Ouvert")).one(),
        "pending_reports": session.exec(select(func.count(ModerationReport.id)).where(ModerationReport.status == "En attente")).one(),
        "companies": session.exec(select(func.count(Company.id))).one(),
        "verified_companies": session.exec(select(func.count(Company.id)).where(Company.kyc_verified == True)).one(),
        "pending_kyc": session.exec(select(func.count(Company.id)).where(Company.kyc_verified == False)).one(),
        "active_bans": session.exec(select(func.count(BannedAccount.id)).where(BannedAccount.active == True)).one(),
    }
class BillingPaymentReview(BaseModel):
    status: Literal["Payé", "Rejeté"]


@router.get("/billing/payments", response_model=list[BillingPayment])
def list_billing_payments(status: str = "À vérifier", session: Session = Depends(get_session)):
    query = select(BillingPayment).order_by(BillingPayment.created_at.asc())
    if status != "Toutes":
        query = query.where(BillingPayment.status == status)
    return session.exec(query).all()


@router.patch("/billing/payments/{payment_id}", response_model=BillingPayment)
def review_billing_payment(payment_id: int, payload: BillingPaymentReview, session: Session = Depends(get_session), admin_user: User = Depends(require_admin)):
    payment = session.get(BillingPayment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Paiement introuvable")
    if payment.status != "À vérifier":
        raise HTTPException(status_code=409, detail="Ce paiement ne peut pas être vérifié dans son état actuel")
    if payload.status == "Payé" and not payment.external_reference:
        raise HTTPException(status_code=400, detail="Aucune référence de transaction à vérifier")
    payment.status = payload.status
    payment.reviewed_at = datetime.utcnow()
    if payload.status == "Payé":
        subscription = session.exec(select(BillingSubscription).where(BillingSubscription.company_id == payment.company_id)).first()
        now = datetime.utcnow()
        starts_at = subscription.starts_at if subscription and subscription.status == "Actif" else now
        base_date = subscription.expires_at if subscription and subscription.expires_at > now else now
        expires_at = base_date + timedelta(days=30)
        if subscription:
            subscription.plan = payment.plan
            subscription.starts_at = starts_at
            subscription.expires_at = expires_at
            subscription.status = "Actif"
        else:
            subscription = BillingSubscription(company_id=payment.company_id, plan=payment.plan, starts_at=now, expires_at=expires_at)
        session.add(subscription)
    payment.reviewed_by_user_id = admin_user.id
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return payment
class CampaignCreate(BaseModel):
    name: str = PydanticField(min_length=3, max_length=160)
    channel: Literal["SMS", "Email", "Push"]
    content: str = PydanticField(min_length=10, max_length=4000)
    audience_segment: Literal["candidates", "recruiters", "all", "premium"]


class CampaignTargetUpdate(BaseModel):
    name: str = PydanticField(min_length=3, max_length=160)
    channel: Literal["SMS", "Email", "Push"]
    content: str = PydanticField(min_length=10, max_length=4000)
    audience_segment: Literal["candidates", "recruiters", "all", "premium"]
    prepared: bool = False


def count_campaign_audience(segment: str, session: Session) -> int:
    from sqlalchemy import func
    if segment == "candidates":
        return session.exec(select(func.count(User.id)).where(User.account_type == AccountType.candidate)).one()
    if segment == "recruiters":
        return session.exec(select(func.count(User.id)).where(User.account_type == AccountType.recruiter)).one()
    if segment == "all":
        return session.exec(select(func.count(User.id)).where(User.account_type != AccountType.admin)).one()
    now = datetime.utcnow()
    return session.exec(select(func.count(BillingSubscription.id)).where(BillingSubscription.status == "Actif", BillingSubscription.expires_at > now)).one()


@router.get("/campaigns", response_model=list[MarketingCampaign])
def list_campaigns(session: Session = Depends(get_session)):
    return session.exec(select(MarketingCampaign).order_by(MarketingCampaign.updated_at.desc())).all()


@router.get("/campaigns/{campaign_id}", response_model=MarketingCampaign)
def get_campaign(campaign_id: int, session: Session = Depends(get_session)):
    campaign = session.get(MarketingCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne introuvable")
    return campaign

@router.post("/campaigns", response_model=MarketingCampaign)
def create_campaign(payload: CampaignCreate, session: Session = Depends(get_session), admin_user: User = Depends(require_admin)):
    campaign = MarketingCampaign(
        created_by_user_id=admin_user.id,
        name=payload.name.strip(),
        channel=payload.channel,
        content=payload.content.strip(),
        audience_segment=payload.audience_segment,
        audience_size=count_campaign_audience(payload.audience_segment, session),
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


@router.patch("/campaigns/{campaign_id}", response_model=MarketingCampaign)
def update_campaign_target(campaign_id: int, payload: CampaignTargetUpdate, session: Session = Depends(get_session)):
    campaign = session.get(MarketingCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campagne introuvable")
    campaign.name = payload.name.strip()
    campaign.channel = payload.channel
    campaign.content = payload.content.strip()
    campaign.audience_segment = payload.audience_segment
    campaign.audience_size = count_campaign_audience(payload.audience_segment, session)
    campaign.status = "Prête à envoyer" if payload.prepared else "Brouillon"
    campaign.updated_at = datetime.utcnow()
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign
@router.get("/campaigns-summary")
def campaign_summary(session: Session = Depends(get_session)):
    from sqlalchemy import func
    return {
        "candidate_accounts": session.exec(select(func.count(User.id)).where(User.account_type == AccountType.candidate)).one(),
        "recruiter_accounts": session.exec(select(func.count(User.id)).where(User.account_type == AccountType.recruiter)).one(),
        "campaigns_total": session.exec(select(func.count(MarketingCampaign.id))).one(),
        "campaigns_prepared": session.exec(select(func.count(MarketingCampaign.id)).where(MarketingCampaign.status == "Prête à envoyer")).one(),
    }


class AdminUserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    account_type: str
    created_at: datetime


class AdminUserCreate(BaseModel):
    full_name: str = PydanticField(min_length=2, max_length=255)
    email: EmailStr
    password: str = PydanticField(min_length=8)
    account_type: Literal["candidate", "recruiter"]


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = PydanticField(default=None, min_length=2, max_length=255)
    account_type: Optional[Literal["candidate", "recruiter"]] = None


@router.get("/users", response_model=list[AdminUserResponse])
def list_admin_users(search: str = "", account_type: Optional[str] = None, session: Session = Depends(get_session)):
    query = select(User).order_by(User.created_at.desc())
    if account_type in {AccountType.candidate.value, AccountType.recruiter.value, AccountType.admin.value}:
        query = query.where(User.account_type == AccountType(account_type))
    if search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where((User.full_name.ilike(pattern)) | (User.email.ilike(pattern)))
    return session.exec(query).all()


@router.post("/users", response_model=AdminUserResponse, status_code=201)
def create_admin_user(payload: AdminUserCreate, session: Session = Depends(get_session)):
    email = str(payload.email).lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=409, detail="Un compte existe déjà avec cette adresse email")
    from ..auth import hash_password
    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        account_type=AccountType(payload.account_type),
    )
    session.add(user)
    session.flush()
    if user.account_type == AccountType.candidate:
        from ..models import CandidateProfile
        session.add(CandidateProfile(user_id=user.id))
    session.commit()
    session.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def update_admin_user(user_id: int, payload: AdminUserUpdate, session: Session = Depends(get_session), admin_user: User = Depends(require_admin)):
    from ..models import CandidateProfile

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.account_type == AccountType.admin:
        raise HTTPException(status_code=403, detail="La modification des comptes administrateur est protégée")
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.account_type is not None and payload.account_type != user.account_type.value:
        new_type = AccountType(payload.account_type)
        if new_type == AccountType.candidate and not session.exec(select(CandidateProfile).where(CandidateProfile.user_id == user.id)).first():
            session.add(CandidateProfile(user_id=user.id))
        user.account_type = new_type
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_admin_user(user_id: int, session: Session = Depends(get_session), admin_user: User = Depends(require_admin)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.id == admin_user.id or user.account_type == AccountType.admin:
        raise HTTPException(status_code=403, detail="La suppression de comptes administrateur est interdite")
    try:
        session.delete(user)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Ce compte possède des données liées; suspendez-le plutôt que de supprimer son historique")
    return {"deleted": True}


@router.get("/jobs/open")
def list_open_admin_jobs(session: Session = Depends(get_session)):
    jobs = session.exec(select(JobOffer).where(JobOffer.status == "Ouvert").order_by(JobOffer.created_at.desc())).all()
    return jobs