import os
import sys

# Ensure root project directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from application import app, Session, engine
from application.models import Base, User, UserProfile, HealthReport

def test_all_pages_and_endpoints():
    print("1. Ensuring DB tables exist...")
    Base.metadata.create_all(bind=engine)

    with Session() as db_session:
        user = db_session.query(User).filter_by(email="testcheckup@vitasense.com").first()
        if not user:
            user = User(username="testcheckup", email="testcheckup@vitasense.com", profile="default.jpg")
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        profile = db_session.query(UserProfile).filter_by(user_id=user.id).first()
        if not profile:
            profile = UserProfile(
                user_id=user.id,
                age=28,
                sex="Female",
                height=165.0,
                height_unit="cm",
                weight=58.0,
                weight_unit="kg",
                diet="Vegetarian",
                bmi=21.3,
                onboarding_completed=True
            )
            db_session.add(profile)
            db_session.commit()

        user_id = user.id

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)
            sess['_fresh'] = True

        endpoints_to_test = [
            ('/', 'index'),
            ('/checkup', 'checkup'),
            ('/screening', 'screening'),
            ('/checkup/select', 'checkup_select'),
            ('/checkup/questionnaire', 'checkup_questionnaire'),
            ('/checkup/visual', 'checkup_visual'),
            ('/checkup/lab', 'checkup_lab'),
            ('/reports', 'reports'),
            ('/health-history', 'health_history'),
            ('/profile', 'profile'),
            ('/visual-screening', 'visual_screening'),
            ('/lab-analysis', 'lab_analysis'),
            ('/symptom-assessment', 'symptom_assessment'),
        ]

        print("\n2. Testing GET request rendering for all authenticated endpoints:")
        for url, name in endpoints_to_test:
            res = client.get(url)
            assert res.status_code == 200, f"Failed on endpoint '{name}' ({url}): Status {res.status_code}"
            print(f"  [OK] {url} -> Endpoint '{name}' (Status 200)")

    print("\nALL URL ENDPOINTS AND TEMPLATES RENDERED SUCCESSFULLY WITH NO BUILDERRORS!")

if __name__ == "__main__":
    test_all_pages_and_endpoints()
