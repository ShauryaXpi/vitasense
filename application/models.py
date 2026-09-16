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

class DoctorShare(Base):
    __tablename__ = 'doctor_shares'

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    token: Mapped[str] = mapped_column(unique=True, nullable=False)
    shared_sections_json: Mapped[str] = mapped_column(nullable=False) # JSON array of selected categories
    duration_hours: Mapped[float] = mapped_column(default=24.0)
    created_at: Mapped[str] = mapped_column(nullable=False)
    expires_at_timestamp: Mapped[float] = mapped_column(nullable=False) # POSIX timestamp for exact expiration
    is_revoked: Mapped[bool] = mapped_column(default=False)
    last_accessed_at: Mapped[str] = mapped_column(nullable=True)

    def __repr__(self):
        return f"<DoctorShare (token={self.token}, user_id={self.user_id}, is_revoked={self.is_revoked})>"


class UserPersonalHealth(Base):
    __tablename__ = 'user_personal_health'

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(nullable=True)
    dob: Mapped[str] = mapped_column(nullable=True)
    blood_group: Mapped[str] = mapped_column(nullable=True) # e.g. "A+", "O-", etc.
    emergency_contact: Mapped[str] = mapped_column(nullable=True)
    known_allergies: Mapped[str] = mapped_column(nullable=True)
    medical_conditions: Mapped[str] = mapped_column(nullable=True)
    current_medications: Mapped[str] = mapped_column(nullable=True)
    preferred_hospital_doctor: Mapped[str] = mapped_column(nullable=True)
    notes: Mapped[str] = mapped_column(nullable=True)

    def __repr__(self):
        return f"<UserPersonalHealth (user_id={self.user_id}, blood_group={self.blood_group})>"

class MedicalDocument(Base):
    __tablename__ = 'medical_documents'

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    doc_name: Mapped[str] = mapped_column(nullable=False)
    doc_type: Mapped[str] = mapped_column(nullable=False) # e.g. "Blood test", "CBC", "Vitamin test", "Thyroid", "Diabetes", "Prescription", "Other"
    file_path: Mapped[str] = mapped_column(nullable=False)
    file_name: Mapped[str] = mapped_column(nullable=False)
    upload_date: Mapped[str] = mapped_column(nullable=False)

    def __repr__(self):
        return f"<MedicalDocument (id={self.id}, user_id={self.user_id}, doc_name={self.doc_name})>"

class EmergencyAccessShare(Base):
    __tablename__ = 'emergency_access_shares'

    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    token: Mapped[str] = mapped_column(unique=True, nullable=False)
    shared_sections_json: Mapped[str] = mapped_column(nullable=False) # JSON array of shared field names/ids
    is_revoked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[str] = mapped_column(nullable=False)

    def __repr__(self):
        return f"<EmergencyAccessShare (token={self.token}, user_id={self.user_id}, is_revoked={self.is_revoked})>"


@login_manager.user_loader
def load_user(user_id):
    with Session() as session:
        user = session.get(User, int(user_id))
        if user:
            session.expunge(user)
            return user
    return None