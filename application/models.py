from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from flask_login import UserMixin
from application import login_manager, Session

class Base(DeclarativeBase):
    pass

class User(Base, UserMixin):
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    username: Mapped[str] = mapped_column(nullable=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    profile: Mapped[str] = mapped_column(nullable=True)

    def __repr__(self):
        return f"<User (name={self.username},email={self.email})>"

class UserProfile(Base):
    __tablename__ = 'user_profiles'

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), unique=True, nullable=False)
    age: Mapped[int] = mapped_column(nullable=False)
    sex: Mapped[str] = mapped_column(nullable=False) # 'Male', 'Female', 'Prefer not to say'
    height: Mapped[float] = mapped_column(nullable=False)
    height_unit: Mapped[str] = mapped_column(nullable=False) # 'cm' or 'ft/in'
    weight: Mapped[float] = mapped_column(nullable=False)
    weight_unit: Mapped[str] = mapped_column(nullable=False) # 'kg' or 'lb'
    diet: Mapped[str] = mapped_column(nullable=False) # 'Vegetarian', 'Vegan', 'Mixed diet', 'Prefer not to say'
    bmi: Mapped[float] = mapped_column(nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(default=True)

    def __repr__(self):
        return f"<UserProfile (user_id={self.user_id}, age={self.age}, bmi={self.bmi})>"

class HealthReport(Base):
    __tablename__ = 'health_reports'

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    title: Mapped[str] = mapped_column(nullable=False) # e.g. "General Health Screening"
    screening_type: Mapped[str] = mapped_column(nullable=False) # e.g. "Preliminary Visual & Symptom Intake"
    category_count: Mapped[int] = mapped_column(default=4)
    nutrition_risk: Mapped[str] = mapped_column(default="Low screening risk")
    metabolic_risk: Mapped[str] = mapped_column(default="Low screening risk")
    general_risk: Mapped[str] = mapped_column(default="Low screening risk")
    summary: Mapped[str] = mapped_column(nullable=True)
    selected_modules_json: Mapped[str] = mapped_column(nullable=True)
    risk_results_json: Mapped[str] = mapped_column(nullable=True)
    visual_summary: Mapped[str] = mapped_column(nullable=True)
    questionnaire_summary: Mapped[str] = mapped_column(nullable=True)
    lab_findings: Mapped[str] = mapped_column(nullable=True)
    pdf_path: Mapped[str] = mapped_column(nullable=True)
    has_lab_report: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[str] = mapped_column(nullable=False) # e.g. "Sep 15, 2026"

    def __repr__(self):
        return f"<HealthReport (id={self.id}, user_id={self.user_id}, title={self.title})>"

class ClinicalRoom(Base):
    __tablename__ = 'clinical_rooms'

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    description: Mapped[str] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(nullable=False)

    def __repr__(self):
        return f"<ClinicalRoom (id={self.id}, code={self.code}, name={self.name})>"

class RoomMember(Base):
    __tablename__ = 'room_members'

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey('clinical_rooms.id'), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    role: Mapped[str] = mapped_column(default='patient') # 'doctor' or 'patient'
    joined_at: Mapped[str] = mapped_column(nullable=False)

    def __repr__(self):
        return f"<RoomMember (room_id={self.room_id}, user_id={self.user_id}, role={self.role})>"

@login_manager.user_loader
def load_user(user_id):
    with Session() as session:
        user = session.get(User, int(user_id))
        if user:
            session.expunge(user)
            return user
    return None