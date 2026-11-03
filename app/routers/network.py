from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlmodel import Session, select

from ..auth import get_current_user
from ..database import get_session
from ..models import AccountType, CandidateConnection, CandidateProfile, User

router = APIRouter(prefix="/network", tags=["network"], dependencies=[Depends(get_current_user)])


class NetworkPerson(BaseModel):
    id: int
    user_id: int
    full_name: str
    job_title: str | None = None
    city: str | None = None


def get_people(user_ids: set[int], session: Session) -> list[NetworkPerson]:
    if not user_ids:
        return []
    rows = session.exec(
        select(CandidateProfile, User)
        .join(User, CandidateProfile.user_id == User.id)
        .where(User.id.in_(user_ids))
    ).all()
    return [
        NetworkPerson(
            id=profile.id,
            user_id=user.id,
            full_name=user.full_name,
            job_title=profile.job_title,
            city=profile.city,
        )
        for profile, user in rows
    ]


@router.get("/me")
def get_my_network(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if current_user.account_type != AccountType.candidate:
        raise HTTPException(status_code=403, detail="Le réseau est réservé aux candidats")

    relations = session.exec(
        select(CandidateConnection).where(
            or_(
                CandidateConnection.requester_user_id == current_user.id,
                CandidateConnection.connected_user_id == current_user.id,
            )
        )
    ).all()
    connected_ids = {
        relation.connected_user_id if relation.requester_user_id == current_user.id else relation.requester_user_id
        for relation in relations
    }
    candidate_rows = session.exec(
        select(CandidateProfile.user_id)
        .join(User, CandidateProfile.user_id == User.id)
        .where(User.account_type == AccountType.candidate, User.id != current_user.id)
    ).all()
    candidate_ids = set(candidate_rows)
    suggestions = list(candidate_ids - connected_ids)[:30]

    return {
        "connections": get_people(connected_ids, session),
        "suggestions": get_people(set(suggestions), session),
        "total_connections": len(connected_ids),
    }


@router.post("/{candidate_id}")
def connect_candidate(candidate_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if current_user.account_type != AccountType.candidate:
        raise HTTPException(status_code=403, detail="Le réseau est réservé aux candidats")
    target_profile = session.get(CandidateProfile, candidate_id)
    if not target_profile or target_profile.user_id == current_user.id:
        raise HTTPException(status_code=404, detail="Candidat introuvable")

    existing = session.exec(
        select(CandidateConnection).where(
            or_(
                (CandidateConnection.requester_user_id == current_user.id) & (CandidateConnection.connected_user_id == target_profile.user_id),
                (CandidateConnection.requester_user_id == target_profile.user_id) & (CandidateConnection.connected_user_id == current_user.id),
            )
        )
    ).first()
    if not existing:
        session.add(CandidateConnection(requester_user_id=current_user.id, connected_user_id=target_profile.user_id))
        session.commit()
    return {"connected": True}


@router.delete("/{candidate_id}")
def disconnect_candidate(candidate_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    target_profile = session.get(CandidateProfile, candidate_id)
    if not target_profile:
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    relation = session.exec(
        select(CandidateConnection).where(
            or_(
                (CandidateConnection.requester_user_id == current_user.id) & (CandidateConnection.connected_user_id == target_profile.user_id),
                (CandidateConnection.requester_user_id == target_profile.user_id) & (CandidateConnection.connected_user_id == current_user.id),
            )
        )
    ).first()
    if relation:
        session.delete(relation)
        session.commit()
    return {"connected": False}