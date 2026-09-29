"""Implementación concreta de UserRepository usando SQLAlchemy + PostgreSQL."""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.entities.user import User
from app.domain.ports.user_repository import UserRepository
from app.infrastructure.db.models import UserModel


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, db: Session):
        self._db = db

    def get_by_email(self, email: str) -> Optional[User]:
        row = self._db.query(UserModel).filter(UserModel.email == email).first()
        return self._to_entity(row) if row else None

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        row = self._db.query(UserModel).filter(UserModel.id == user_id).first()
        return self._to_entity(row) if row else None

    def email_exists(self, email: str) -> bool:
        return self._db.query(UserModel).filter(UserModel.email == email).first() is not None

    def save(self, user: User) -> User:
        row = UserModel(
            id=user.id,
            email=user.email,
            hashed_password=user.hashed_password,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._to_entity(row)

    @staticmethod
    def _to_entity(row: UserModel) -> User:
        return User(
            id=row.id,
            email=row.email,
            hashed_password=row.hashed_password,
            full_name=row.full_name,
            role=row.role,
            is_active=row.is_active,
            created_at=row.created_at,
        )
