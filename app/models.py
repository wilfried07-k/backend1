from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, LargeBinary
from sqlmodel import SQLModel, Field


# ============================================================
# ENUMS
# ============================================================

class AccountType(str, Enum):
    candidate = "candidate"
    recruiter = "recruiter"
    admin = "admin"


# ============================================================
# USER
# ============================================================

class User(SQLModel, table=True):
    """
    Compte utilisateur :
    candidat / recruteur / administrateur.
    """

    __tablename__ = "users"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    full_name: str = Field(
        max_length=255
    )

    email: str = Field(
        max_length=255,
        unique=True,
        index=True
    )

    phone: Optional[str] = Field(
        default=None,
        max_length=30
    )

    hashed_password: str = Field(
        max_length=255
    )

    account_type: AccountType = Field(
        default=AccountType.candidate,
        max_length=20
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


class PasswordResetCode(SQLModel, table=True):
    __tablename__ = "password_reset_codes"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    code_hash: str = Field(max_length=64, index=True)
    expires_at: datetime
    attempts: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# CANDIDATE PROFILE
# ============================================================

class CandidateProfile(SQLModel, table=True):
    """
    Profil dÃ©taillÃ© d'un candidat.
    """

    __tablename__ = "candidate_profiles"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    user_id: int = Field(
        foreign_key="users.id",
        unique=True
    )

    job_title: Optional[str] = Field(
        default=None,
        max_length=255
    )

    city: Optional[str] = Field(
        default=None,
        max_length=100
    )

    summary: Optional[str] = Field(
        default=None,
        max_length=4000
    )

    skills: Optional[str] = Field(
        default=None,
        max_length=2000
    )

    years_experience: Optional[int] = None

    cnps_matricule: Optional[str] = Field(
        default=None,
        max_length=100
    )


# ============================================================
# COMPANY
# ============================================================

class Company(SQLModel, table=True):
    """
    Profil entreprise liÃ© au compte recruteur.
    """

    __tablename__ = "companies"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    owner_user_id: int = Field(
        foreign_key="users.id",
        unique=True
    )

    name: str = Field(
        max_length=255
    )

    sector: Optional[str] = Field(
        default=None,
        max_length=255
    )

    description: Optional[str] = Field(
        default=None,
        max_length=4000
    )

    cnps_employer_matricule: Optional[str] = Field(
        default=None,
        max_length=100
    )

    kyc_verified: bool = Field(
        default=False
    )


# ============================================================
# JOB OFFER
# ============================================================

class JobOffer(SQLModel, table=True):
    """
    Offre d'emploi publiÃ©e par un recruteur.
    """

    __tablename__ = "job_offers"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    company_id: int = Field(
        foreign_key="companies.id"
    )

    title: str = Field(
        max_length=255
    )

    description: str = Field(
        max_length=4000
    )

    requirements: str = Field(
        max_length=4000
    )

    city: Optional[str] = Field(
        default=None,
        max_length=100
    )

    contract_type: Optional[str] = Field(
        default=None,
        max_length=100
    )

    salary_min: Optional[int] = None

    salary_max: Optional[int] = None

    status: str = Field(
        default="Ouvert",
        max_length=50
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# APPLICATION
# ============================================================

class Application(SQLModel, table=True):
    """
    Candidature d'un candidat Ã  une offre.
    """

    __tablename__ = "applications"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    candidate_id: int = Field(
        foreign_key="candidate_profiles.id"
    )

    job_offer_id: int = Field(
        foreign_key="job_offers.id"
    )

    status: str = Field(
        default="EnvoyÃ©e",
        max_length=50
    )

    match_score: Optional[float] = None

    motivation_message: Optional[str] = Field(
        default=None,
        max_length=4000
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


class ApplicationDocument(SQLModel, table=True):
    """A private document submitted with a job application."""

    __tablename__ = "application_documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="applications.id", index=True)
    document_type: str = Field(max_length=30)
    file_name: str = Field(max_length=255)
    content_type: str = Field(max_length=100)
    content: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# SAVED JOB
# ============================================================

class SavedJob(SQLModel, table=True):
    """
    Offre sauvegardÃ©e en favori par un candidat.
    """

    __tablename__ = "saved_jobs"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    candidate_id: int = Field(
        foreign_key="candidate_profiles.id"
    )

    job_offer_id: int = Field(
        foreign_key="job_offers.id"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# CONVERSATION
# ============================================================

class Conversation(SQLModel, table=True):
    """
    Discussion entre un candidat et une entreprise.
    """

    __tablename__ = "conversations"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    candidate_id: int = Field(
        foreign_key="candidate_profiles.id"
    )

    company_id: int = Field(
        foreign_key="companies.id"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# MESSAGE
# ============================================================

class Message(SQLModel, table=True):
    """
    Message individuel dans une conversation.
    """

    __tablename__ = "messages"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    conversation_id: int = Field(
        foreign_key="conversations.id"
    )

    sender_user_id: int = Field(
        foreign_key="users.id"
    )

    text: str = Field(
        max_length=4000
    )

    read: bool = Field(
        default=False
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# INTERVIEW
# ============================================================

class Interview(SQLModel, table=True):
    """
    Entretien planifiÃ© pour une candidature.
    """

    __tablename__ = "interviews"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    application_id: int = Field(
        foreign_key="applications.id"
    )

    scheduled_at: datetime

    mode: str = Field(
        default="video",
        max_length=30
    )

    location_or_link: Optional[str] = Field(
        default=None,
        max_length=500
    )

    status: str = Field(
        default="PlanifiÃ©",
        max_length=50
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# NOTIFICATION
# ============================================================

class Notification(SQLModel, table=True):
    """
    Notification utilisateur.
    """

    __tablename__ = "notifications"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    user_id: int = Field(
        foreign_key="users.id"
    )

    type: str = Field(
        max_length=50
    )

    title: str = Field(
        max_length=255
    )

    body: str = Field(
        max_length=4000
    )

    read: bool = Field(
        default=False
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# JOB ALERT
# ============================================================

class JobAlert(SQLModel, table=True):
    """
    Alerte emploi d'un candidat.
    """

    __tablename__ = "job_alerts"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    candidate_id: int = Field(
        foreign_key="candidate_profiles.id"
    )

    title: str = Field(
        max_length=255
    )

    city: Optional[str] = Field(
        default=None,
        max_length=100
    )

    frequency: str = Field(
        default="instant",
        max_length=30
    )

    active: bool = Field(
        default=True
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# MODERATION REPORT
# ============================================================

class ModerationReport(SQLModel, table=True):
    """
    Signalement d'une offre ou d'un utilisateur.
    """

    __tablename__ = "moderation_reports"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    job_offer_id: Optional[int] = Field(
        default=None,
        foreign_key="job_offers.id"
    )

    reported_user_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id"
    )

    reported_by_user_id: int = Field(
        foreign_key="users.id"
    )

    reason: str = Field(
        max_length=2000
    )

    status: str = Field(
        default="En attente",
        max_length=50
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )


# ============================================================
# BANNED ACCOUNT
# ============================================================

class BannedAccount(SQLModel, table=True):
    """
    Compte utilisateur banni.
    """

    __tablename__ = "banned_accounts"

    id: Optional[int] = Field(
        default=None,
        primary_key=True
    )

    user_id: int = Field(
        foreign_key="users.id",
        unique=True
    )

    reason: str = Field(
        max_length=2000
    )

    definitive: bool = Field(
        default=False
    )

    banned_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    active: bool = Field(
        default=True
    )
class DipeDeclaration(SQLModel, table=True):
    """Déclaration d'embauche préparée dans l'application, à transmettre à la CNPS."""

    __tablename__ = "dipe_declarations"

    id: Optional[int] = Field(default=None, primary_key=True)
    reference: str = Field(max_length=80, unique=True, index=True)
    company_id: int = Field(foreign_key="companies.id", index=True)
    candidate_id: int = Field(foreign_key="candidate_profiles.id", index=True)
    declared_by_user_id: int = Field(foreign_key="users.id")
    contract_type: str = Field(max_length=50)
    start_date: str = Field(max_length=10)
    gross_salary: int
    risk_rate_percent: float
    existing_matricule: Optional[str] = Field(default=None, max_length=100)
    candidate_cni: Optional[str] = Field(default=None, max_length=100)
    status: str = Field(default="À transmettre à la CNPS", max_length=80)
    created_at: datetime = Field(default_factory=datetime.utcnow)
class SupportTicket(SQLModel, table=True):
    __tablename__ = "support_tickets"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    category: str = Field(max_length=80)
    subject: str = Field(max_length=255)
    body: str = Field(max_length=4000)
    status: str = Field(default="Ouvert", max_length=40)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProductFeedback(SQLModel, table=True):
    __tablename__ = "product_feedback"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    applications_rating: int
    usability_rating: int
    value_rating: int
    comment: Optional[str] = Field(default=None, max_length=4000)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CompanyReview(SQLModel, table=True):
    """Anonymous employee review attached to a company."""

    __tablename__ = "company_reviews"

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="companies.id", index=True)
    author_user_id: int = Field(foreign_key="users.id", index=True)
    rating: int
    role: Optional[str] = Field(default=None, max_length=255)
    body: str = Field(max_length=4000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
class CareerExperience(SQLModel, table=True):
    """Candidate-maintained work history; not an official social-security record."""

    __tablename__ = "career_experiences"

    id: Optional[int] = Field(default=None, primary_key=True)
    candidate_id: int = Field(foreign_key="candidate_profiles.id", index=True)
    employer: str = Field(max_length=255)
    job_title: str = Field(max_length=255)
    start_date: datetime
    end_date: Optional[datetime] = None
    description: Optional[str] = Field(default=None, max_length=4000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
class InterviewReport(SQLModel, table=True):
    """Recruiter notes and assessment attached to a scheduled interview."""

    __tablename__ = "interview_reports"

    id: Optional[int] = Field(default=None, primary_key=True)
    interview_id: int = Field(foreign_key="interviews.id", unique=True, index=True)
    recruiter_user_id: int = Field(foreign_key="users.id")
    notes: Optional[str] = Field(default=None, max_length=4000)
    positives: Optional[str] = Field(default=None, max_length=4000)
    concerns: Optional[str] = Field(default=None, max_length=4000)
    technical_rating: Optional[int] = None
    communication_rating: Optional[int] = None
    soft_skills_rating: Optional[int] = None
    impressions: Optional[str] = Field(default=None, max_length=4000)
    recommendation: Optional[str] = Field(default=None, max_length=30)
    status: str = Field(default="Brouillon", max_length=30)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
class SkillAssessment(SQLModel, table=True):
    """Persisted result of an in-app skills quiz; not an external accreditation."""

    __tablename__ = "skill_assessments"

    id: Optional[int] = Field(default=None, primary_key=True)
    candidate_id: int = Field(foreign_key="candidate_profiles.id", index=True)
    test_id: str = Field(max_length=80, index=True)
    test_name: str = Field(max_length=255)
    score: int
    total_questions: int
    percentage: int
    badge: str = Field(max_length=40)
    created_at: datetime = Field(default_factory=datetime.utcnow)
class CompanyDirectorProfile(SQLModel, table=True):
    """Private director contact profile for the owning recruiter."""

    __tablename__ = "company_director_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="companies.id", unique=True, index=True)
    full_name: str = Field(max_length=255)
    title: str = Field(max_length=150)
    professional_email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=30)
    identity_status: str = Field(default="Non vérifiée", max_length=40)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
class ReferralCode(SQLModel, table=True):
    __tablename__ = "referral_codes"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    code: str = Field(max_length=32, unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Referral(SQLModel, table=True):
    __tablename__ = "referrals"

    id: Optional[int] = Field(default=None, primary_key=True)
    referrer_user_id: int = Field(foreign_key="users.id", index=True)
    referred_user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    referral_code: str = Field(max_length=32)
    created_at: datetime = Field(default_factory=datetime.utcnow)
class CandidateProject(SQLModel, table=True):
    """Project published by a candidate in their portfolio."""

    __tablename__ = "candidate_projects"

    id: Optional[int] = Field(default=None, primary_key=True)
    candidate_id: int = Field(foreign_key="candidate_profiles.id", index=True)
    title: str = Field(max_length=255)
    description: str = Field(max_length=4000)
    skills: Optional[str] = Field(default=None, max_length=1000)
    url: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow)
class NotificationPreference(SQLModel, table=True):
    """Per-user delivery and notification category preferences."""

    __tablename__ = "notification_preferences"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True, index=True)
    push_enabled: bool = True
    email_enabled: bool = True
    jobs: bool = True
    messages: bool = True
    applications: bool = True
    interviews: bool = True
    news: bool = False
    marketing: bool = False
    updated_at: datetime = Field(default_factory=datetime.utcnow)
class BillingPayment(SQLModel, table=True):
    """Manual payment request; a provider or admin must verify the transaction."""

    __tablename__ = "billing_payments"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    company_id: int = Field(foreign_key="companies.id", index=True)
    plan: str = Field(max_length=40)
    amount_xaf: int
    payment_method: str = Field(max_length=40)
    external_reference: Optional[str] = Field(default=None, max_length=120)
    status: str = Field(default="En attente de paiement", max_length=40, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    reviewed_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
class BillingSubscription(SQLModel, table=True):
    """Verified company plan period."""

    __tablename__ = "billing_subscriptions"

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="companies.id", unique=True, index=True)
    plan: str = Field(max_length=40)
    starts_at: datetime
    expires_at: datetime
    status: str = Field(default="Actif", max_length=30)
class MarketingCampaign(SQLModel, table=True):
    """Persisted campaign draft and its audience estimate; delivery requires a provider."""

    __tablename__ = "marketing_campaigns"

    id: Optional[int] = Field(default=None, primary_key=True)
    created_by_user_id: int = Field(foreign_key="users.id", index=True)
    name: str = Field(max_length=160)
    channel: str = Field(max_length=20)
    content: str = Field(max_length=4000)
    audience_segment: str = Field(max_length=30)
    audience_size: int = Field(default=0)
class CandidateConnection(SQLModel, table=True):
    __tablename__ = "candidate_connections"

    id: Optional[int] = Field(default=None, primary_key=True)
    requester_user_id: int = Field(foreign_key="users.id", index=True)
    connected_user_id: int = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="Brouillon", max_length=40)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
class CompanyKycReview(SQLModel, table=True):
    """Latest administrative KYC review state for a company."""

    __tablename__ = "company_kyc_reviews"

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="companies.id", unique=True, index=True)
    reviewed_by_user_id: int = Field(foreign_key="users.id")
    status: str = Field(default="En attente", max_length=40)
    notes: Optional[str] = Field(default=None, max_length=1000)
    updated_at: datetime = Field(default_factory=datetime.utcnow)