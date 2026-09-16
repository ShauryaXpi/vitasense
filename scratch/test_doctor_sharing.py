import sys
import os
import json
import time
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from application import app, engine, Session
from application.models import Base, User, UserProfile, UserPersonalHealth, MedicalDocument, DoctorShare

def run_tests():
    print("--- 1. Initializing Database Schema ---")
    Base.metadata.create_all(bind=engine)
    client = app.test_client()

    print("--- 2. Setting Up Test Patient Account ---")
    with Session() as db_session:
        test_user = db_session.query(User).filter_by(email="doctorshare_test@vitasense.io").first()
        if not test_user:
            test_user = User(username="doctorshare_patient", email="doctorshare_test@vitasense.io")
            db_session.add(test_user)
            db_session.commit()
            db_session.refresh(test_user)

        user_id = test_user.id
        profile = db_session.query(UserProfile).filter_by(user_id=user_id).first()
        if not profile:
            profile = UserProfile(
                user_id=user_id, age=35, sex="Female", height=165.0, height_unit="cm",
                weight=60.0, weight_unit="kg", diet="Vegetarian", bmi=22.0, onboarding_completed=True
            )
            db_session.add(profile)

        ph = db_session.query(UserPersonalHealth).filter_by(user_id=user_id).first()
        if not ph:
            ph = UserPersonalHealth(
                user_id=user_id, full_name="Jane Patient", dob="1990-01-01", blood_group="A+",
                emergency_contact="+1 555-123-4567", known_allergies="Sulfa drugs",
                medical_conditions="Hypothyroidism", current_medications="Levothyroxine 50mcg",
                preferred_hospital_doctor="Dr. Miller - Metro Health"
            )
            db_session.add(ph)

        db_session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True

    print("--- 3. Testing Creation of Doctor Share Link ---")
    res_create = client.post('/health-locker/doctor-share/create', data={
        'shared_items': ['personal_info', 'allergies', 'blood_group'],
        'duration_option': '24'
    }, follow_redirects=True)

    assert res_create.status_code == 200
    assert b"Doctor Share link created successfully" in res_create.data

    with Session() as db_session:
        ds = db_session.query(DoctorShare).filter_by(user_id=user_id, is_revoked=False).order_by(DoctorShare.id.desc()).first()
        assert ds is not None
        assert float(ds.duration_hours) == 24.0
        token = ds.token
        ds_id = ds.id
        items = json.loads(ds.shared_sections_json)
        assert 'personal_info' in items
        assert 'allergies' in items
        assert 'blood_group' in items
        assert 'medications' not in items
    print("Doctor share link created and stored in DB.")

    print("--- 4. Testing Read-Only Doctor View (Unauthenticated Access) ---")
    doctor_client = app.test_client()
    res_doc = doctor_client.get(f'/doctor-share/{token}')

    assert res_doc.status_code == 200
    assert b"Jane Patient" in res_doc.data
    assert b"Sulfa drugs" in res_doc.data
    assert b"A+" in res_doc.data
    assert b"Levothyroxine 50mcg" not in res_doc.data
    print("Read-only doctor view correctly displayed authorized fields only.")

    print("--- 5. Testing Audit Log (Last Accessed Timestamp) ---")
    with Session() as db_session:
        ds_after = db_session.get(DoctorShare, ds_id)
        assert ds_after.last_accessed_at is not None
        print(f"Audit timestamp recorded: {ds_after.last_accessed_at}")

    print("--- 6. Testing Revocation of Doctor Share ---")
    res_revoke = client.post(f'/health-locker/doctor-share/{ds_id}/revoke', follow_redirects=True)
    assert res_revoke.status_code == 200
    assert b"Doctor access has been revoked" in res_revoke.data

    res_doc_revoked = doctor_client.get(f'/doctor-share/{token}')
    assert res_doc_revoked.status_code == 200
    assert b"Doctor Access Revoked" in res_doc_revoked.data or b"revoked" in res_doc_revoked.data.lower()
    print("Revoked share correctly displays revocation warning.")

    print("\nALL DOCTOR SHARING TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_tests()
