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

@login_manager.user_loader
def load_user(user_id):
    with Session() as session:
        user = session.get(User, int(user_id))
        if user:
            session.expunge(user)
            return user
    return None