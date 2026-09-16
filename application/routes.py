import os
import uuid
import json
from datetime import datetime
import requests
from flask import render_template, redirect, url_for, request, session, flash, send_from_directory, abort, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from application import app, google, Session
from application.models import User, UserProfile, HealthReport, UserPersonalHealth, MedicalDocument, EmergencyAccessShare, DoctorShare
from application.diet_engine import generate_diet_guidance
from application.pdf_generator import generate_diet_pdf
import time

@app.route('/')
@login_required
def index():
    with Session() as db_session:
        profile = db_session.query(UserProfile).filter_by(user_id=current_user.id).first()
        if profile:
            db_session.expunge(profile)

        # Fetch health reports for the user
        reports = db_session.query(HealthReport).filter_by(user_id=current_user.id).order_by(HealthReport.id.desc()).all()
        for r in reports:
            db_session.expunge(r)

    if not profile or not profile.onboarding_completed:
        return redirect(url_for('onboarding'))

    has_screenings = len(reports) > 0
    latest_report = reports[0] if has_screenings else None
    recent_reports = reports[:3] if has_screenings else []
    has_lab_report = any(r.has_lab_report for r in reports) if has_screenings else False

    return render_template(
        'index.html',
        user=current_user,
        profile=profile,
        reports=reports,
        latest_report=latest_report,
        recent_reports=recent_reports,
        has_screenings=has_screenings,
        has_lab_report=has_lab_report
    )

@app.route('/login')
def login():
    if current_user.is_authenticated:
        with Session() as db_session:
            profile = db_session.query(UserProfile).filter_by(user_id=current_user.id).first()
        if profile and profile.onboarding_completed:
            return redirect(url_for('index'))
        return redirect(url_for('onboarding'))
    
    return render_template('login.html')

@app.route('/register')
def register():
    return redirect(url_for('login'))

@app.route('/assets/<path:filename>')
def serve_asset(filename):
    assets_directory = os.path.join(app.root_path, '..', 'assets')
    return send_from_directory(assets_directory, filename)

@app.route('/login/google')
def google_login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/callback")
def authorize():
    try:
        token = google.authorize_access_token()
        resp = google.get("userinfo")
        user_info = resp.json()
    except Exception as e:
        flash(f"Google login failed: {e}", "danger")
        return redirect(url_for('login'))

    if not user_info or not user_info.get('email'):
        flash("Could not retrieve profile info from Google.", "danger")
        return redirect(url_for('login'))

    with Session() as db_session:
        user = db_session.query(User).filter_by(email=user_info["email"]).first()
        if not user:
            new_user = User(
                username = user_info.get("given_name", user_info["email"].split("@")[0]).lower(),
                email = user_info["email"],
                profile = user_info.get("picture")
            )
            db_session.add(new_user)
            db_session.commit()
            db_session.refresh(new_user)
            user = new_user

        db_session.expunge(user)

        # Check if user already completed onboarding
        profile = db_session.query(UserProfile).filter_by(user_id=user.id).first()
        has_completed_onboarding = bool(profile and profile.onboarding_completed)

    login_user(user)

    if has_completed_onboarding:
        flash(f"Login as @{user.username}", "success")
        return redirect(url_for("index"))
    else:
        return redirect(url_for("onboarding"))

@app.route('/onboarding', methods=['GET', 'POST'])
@login_required
def onboarding():
    if request.method == 'GET':
        with Session() as db_session:
            profile = db_session.query(UserProfile).filter_by(user_id=current_user.id).first()
        if profile and profile.onboarding_completed:
            return redirect(url_for('index'))
        return render_template('onboarding.html')

    # Handle POST Submission
    try:
        age = int(request.form.get('age', 0))
        sex = request.form.get('sex', '').strip()
        height = float(request.form.get('height', 0))
        height_unit = request.form.get('height_unit', 'cm').strip()
        weight = float(request.form.get('weight', 0))
        weight_unit = request.form.get('weight_unit', 'kg').strip()
        diet = request.form.get('diet', '').strip()

        # Validate inputs
        if age < 1 or age > 120:
            flash("Please enter a valid age between 1 and 120.", "danger")
            return render_template('onboarding.html')

        if sex not in ['Male', 'Female', 'Prefer not to say']:
            flash("Please select a valid option for sex.", "danger")
            return render_template('onboarding.html')

        if height <= 0 or weight <= 0:
            flash("Please enter valid positive numbers for height and weight.", "danger")
            return render_template('onboarding.html')

        if diet not in ['Vegetarian', 'Vegan', 'Mixed diet', 'Prefer not to say']:
            flash("Please select a valid option for diet.", "danger")
            return render_template('onboarding.html')

        # Calculate BMI
        if height_unit == 'cm':
            height_m = height / 100.0
        else:
            height_m = height * 0.0254

        if weight_unit == 'kg':
            weight_kg = weight
        else:
            weight_kg = weight * 0.45359237

        bmi = round(weight_kg / (height_m ** 2), 1) if height_m > 0 else None

        # Save to database
        with Session() as db_session:
            profile = db_session.query(UserProfile).filter_by(user_id=current_user.id).first()
            if not profile:
                profile = UserProfile(
                    user_id=current_user.id,
                    age=age,
                    sex=sex,
                    height=height,
                    height_unit=height_unit,
                    weight=weight,
                    weight_unit=weight_unit,
                    diet=diet,
                    bmi=bmi,
                    onboarding_completed=True
                )
                db_session.add(profile)
            else:
                profile.age = age
                profile.sex = sex
                profile.height = height
                profile.height_unit = height_unit
                profile.weight = weight
                profile.weight_unit = weight_unit
                profile.diet = diet
                profile.bmi = bmi
                profile.onboarding_completed = True
            db_session.commit()

        flash("Onboarding completed successfully! Welcome to your Health Screening dashboard.", "success")
        return redirect(url_for('index'))

    except Exception as e:
        flash(f"Error saving onboarding details: {e}", "danger")
        return render_template('onboarding.html')

# ================= Multi-Stage Checkup Flow Routes =================

@app.route('/screening', endpoint='screening')
@app.route('/checkup', endpoint='checkup')
@app.route('/checkup/select', endpoint='checkup_select')
@login_required
def checkup_select():
    return render_template('checkup_select.html')

@app.route('/checkup/start', methods=['POST'])
@login_required
def start_checkup():
    selected_modules = request.form.getlist('modules')
    if not selected_modules:
        selected_modules = ['anemia', 'vitamin_d', 'folate', 'iodine']
    session['checkup_data'] = {
        'selected_modules': selected_modules,
        'questionnaire': {},
        'visual': {},
        'lab': {}
    }
    return redirect(url_for('checkup_questionnaire'))

@app.route('/checkup/questionnaire')
@login_required
def checkup_questionnaire():
    checkup_data = session.get('checkup_data', {})
    selected_ids = checkup_data.get('selected_modules', ['anemia', 'vitamin_d', 'folate', 'iodine'])

    with Session() as db_session:
        past_reports = db_session.query(HealthReport).filter_by(user_id=current_user.id).order_by(HealthReport.id.desc()).limit(3).all()
        past_reports_summary = []
        for r in past_reports:
            results = []
            if r.risk_results_json:
                try:
                    results = json.loads(r.risk_results_json)
                except Exception:
                    pass
            past_reports_summary.append({
                'id': r.id,
                'created_at': r.created_at,
                'title': r.title,
                'results': results,
                'summary': r.summary
            })

    return render_template(
        'checkup_questionnaire.html',
        is_repeat=bool(past_reports_summary),
        past_reports=past_reports_summary,
        selected_modules=selected_ids
    )

@app.route('/checkup/questionnaire/baseline', methods=['POST'])
@app.route('/checkup/questionnaire/repeat', methods=['POST'])
@login_required
def save_repeat_questionnaire():
    if 'checkup_data' not in session:
        session['checkup_data'] = {'selected_modules': ['anemia', 'vitamin_d', 'folate', 'iodine'], 'questionnaire': {}, 'visual': {}, 'lab': {}}
    
    q_data = {}
    for k in request.form.keys():
        if k != 'csrf_token':
            vals = request.form.getlist(k)
            if len(vals) == 1:
                q_data[k] = vals[0].strip()
            else:
                q_data[k] = [v.strip() for v in vals]

    # Normalize tiredness & symptoms for Risk Engine
    all_symptoms = []
    for key in ['symptoms', 'past_symptoms', 'anemia_symptoms', 'b12_symptoms', 'vitd_symptoms', 'folate_symptoms']:
        val = q_data.get(key, [])
        if isinstance(val, str):
            val = [val]
        all_symptoms.extend(val)

    if any('tiredness' in s.lower() or 'fatigue' in s.lower() for s in all_symptoms):
        q_data['tiredness'] = 'Often'
    if any('tingling' in s.lower() or 'numbness' in s.lower() for s in all_symptoms):
        q_data['b12_tingling'] = 'Yes'

    chk = session['checkup_data']
    chk['questionnaire'] = q_data
    session['checkup_data'] = chk
    return redirect(url_for('checkup_visual'))

@app.route('/checkup/visual')
@login_required
def checkup_visual():
    return render_template('checkup_visual.html')

@app.route('/checkup/visual', methods=['POST'])
@login_required
def save_visual_checkup():
    import base64

    if 'checkup_data' not in session:
        session['checkup_data'] = {'selected_modules': ['anemia', 'vitamin_d', 'folate', 'iodine'], 'questionnaire': {}, 'visual': {}, 'lab': {}}

    upload_dir = os.path.join(app.root_path, '..', 'assets', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    saved_images = {}
    
    # 1. Base64 Live Camera Snapshots
    base64_mappings = {
        'eye_base64': 'eye_image',
        'knuckle_base64': 'knuckle_image',
        'nail_base64': 'nail_image',
        'tongue_base64': 'tongue_image'
    }
    for b64_key, img_key in base64_mappings.items():
        b64_val = request.form.get(b64_key, '')
        if b64_val and b64_val.startswith('data:image'):
            try:
                header, encoded = b64_val.split(',', 1)
                img_data = base64.b64decode(encoded)
                filename = f"cam_{img_key}_{uuid.uuid4().hex[:8]}.jpg"
                filepath = os.path.join(upload_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(img_data)
                saved_images[img_key] = f"assets/uploads/{filename}"
            except Exception:
                pass

    # 2. File Input Uploads Fallback
    for key in ['eye_image', 'tongue_image', 'nail_image', 'knuckle_image']:
        if key not in saved_images:
            file = request.files.get(key)
            if file and file.filename != '':
                ext = os.path.splitext(file.filename)[1] or '.jpg'
                filename = f"up_{key}_{uuid.uuid4().hex[:8]}{ext}"
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                saved_images[key] = f"assets/uploads/{filename}"

    chk = session['checkup_data']
    chk['visual'] = saved_images
    session['checkup_data'] = chk
    return compute_analysis_results()

@app.route('/checkup/lab')
@login_required
def checkup_lab():
    return redirect(url_for('checkup_visual'))

@app.route('/checkup/lab', methods=['POST'])
@login_required
def save_lab_checkup():
    return compute_analysis_results()

@app.route('/checkup/analysis')
@login_required
def checkup_analysis():
    return render_template('checkup_analysis.html')

@app.route('/checkup/compute', methods=['POST'])
@login_required
def compute_analysis_results():
    from risk_engine.engine import risk_engine
    from application.pdf_generator import generate_screening_pdf

    checkup_data = session.get('checkup_data', {})
    selected_modules = checkup_data.get('selected_modules', ['anemia', 'vitamin_d', 'folate', 'iodine'])
    questionnaire_data = checkup_data.get('questionnaire', {})
    visual_data = checkup_data.get('visual', {})
    lab_data = checkup_data.get('lab', {})

    with Session() as db_session:
        user_profile = db_session.query(UserProfile).filter_by(user_id=current_user.id).first()
        profile_dict = {
            'age': user_profile.age if user_profile else 30,
            'sex': user_profile.sex if user_profile else 'Unspecified',
            'height': user_profile.height if user_profile else 170,
            'height_unit': user_profile.height_unit if user_profile else 'cm',
            'weight': user_profile.weight if user_profile else 70,
            'weight_unit': user_profile.weight_unit if user_profile else 'kg',
            'diet': user_profile.diet if user_profile else 'Mixed diet',
            'bmi': user_profile.bmi if user_profile else 24.2
        }

    # Run Risk Engine
    risk_eval = risk_engine.run(selected_modules, questionnaire_data, visual_data, lab_data)

    # Format summaries
    formatted_date = datetime.now().strftime("%b %d, %Y")
    
    vis_count = len(visual_data)
    vis_summary = f"{vis_count} observational image(s) processed for visual screening indicators." if vis_count > 0 else "No observational images uploaded."
    
    if questionnaire_data.get('type') == 'repeat':
        q_summary = f"Repeat checkup follow-up recorded: {', '.join(questionnaire_data.get('changes', ['No changes']))}."
    else:
        q_summary = f"Tiredness: {questionnaire_data.get('tiredness', 'N/A')}, Visual changes: {questionnaire_data.get('visual_changes', 'N/A')}, Supplements: {questionnaire_data.get('supplements', 'N/A')}."

    if lab_data.get('has_lab'):
        lab_parts = []
        if 'hb' in lab_data: lab_parts.append(f"Hemoglobin {lab_data['hb']} g/dL")
        if 'vitd' in lab_data: lab_parts.append(f"Vitamin D {lab_data['vitd']} ng/mL")
        if 'folate' in lab_data: lab_parts.append(f"Folate {lab_data['folate']} ng/mL")
        if 'tsh' in lab_data: lab_parts.append(f"TSH {lab_data['tsh']} mIU/L")
        if 'file' in lab_data: lab_parts.append("Lab document attached")
        lab_summary = ", ".join(lab_parts) if lab_parts else "Laboratory values confirmed."
    else:
        lab_summary = "No laboratory values provided."

    mod_titles = [r['title'] for r in risk_eval['results']]
    highest_mod = max(risk_eval['results'], key=lambda x: x['score']) if risk_eval['results'] else {'title': 'General Risk', 'score': 0.0}
    
    line1 = f"Multimodal screening evaluation completed across {len(selected_modules)} health area(s): {', '.join(mod_titles)}."
    line2 = f"Primary calculated deficiency probability is led by {highest_mod['title']} at {highest_mod['score']:.2f}% risk based on observational image indicators and symptom intake responses."
    line3 = "Initial observational indicators and self-reported intake factors suggest reviewing findings with a healthcare professional for potential follow-up diagnostic blood testing."
    
    exec_summary = f"{line1}\n{line2}\n{line3}"

    with Session() as db_session:
        new_report = HealthReport(
            user_id=current_user.id,
            title="Personalized Health Risk Assessment",
            screening_type="Multimodal Visual, Intake & Lab Screening",
            category_count=len(selected_modules),
            nutrition_risk=risk_eval['nutrition_risk'],
            metabolic_risk=risk_eval['metabolic_risk'],
            general_risk=risk_eval['general_risk'],
            summary=exec_summary,
            selected_modules_json=json.dumps(selected_modules),
            risk_results_json=json.dumps(risk_eval['results']),
            visual_summary=vis_summary,
            questionnaire_summary=q_summary,
            lab_findings=lab_summary,
            has_lab_report=bool(lab_data.get('has_lab')),
            created_at=formatted_date
        )
        db_session.add(new_report)
        db_session.commit()
        db_session.refresh(new_report)
        report_id = new_report.id

        # Generate PDF report
        pdf_dir = os.path.join(app.root_path, '..', 'assets', 'reports')
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_filename = f"report_{report_id}_{uuid.uuid4().hex[:8]}.pdf"
        pdf_path = os.path.join(pdf_dir, pdf_filename)

        report_dict = {
            'created_at': formatted_date,
            'results': risk_eval['results'],
            'visual_summary': vis_summary,
            'questionnaire_summary': q_summary,
            'lab_findings': lab_summary,
            'has_lab_report': bool(lab_data.get('has_lab'))
        }
        
        generate_screening_pdf(
            pdf_path,
            user_name=current_user.username or "Valued Patient",
            user_email=current_user.email,
            report_data=report_dict,
            profile_data=profile_dict
        )

        new_report.pdf_path = f"assets/reports/{pdf_filename}"
        db_session.commit()

    # Clear checkup session data
    session.pop('checkup_data', None)

    return redirect(url_for('checkup_results', report_id=report_id))

@app.route('/checkup/results/<int:report_id>')
@login_required
def checkup_results(report_id):
    with Session() as db_session:
        report = db_session.query(HealthReport).filter_by(id=report_id, user_id=current_user.id).first()
        if report:
            db_session.expunge(report)

    if not report:
        flash("Report not found.", "warning")
        return redirect(url_for('reports'))

    module_results = []
    if report.risk_results_json:
        try:
            module_results = json.loads(report.risk_results_json)
        except Exception:
            module_results = []

    return render_template('checkup_results.html', report=report, module_results=module_results)

@app.route('/reports/<int:report_id>/pdf')
@login_required
def download_report_pdf(report_id):
    with Session() as db_session:
        report = db_session.query(HealthReport).filter_by(id=report_id, user_id=current_user.id).first()
        if report:
            db_session.expunge(report)

    if not report or not report.pdf_path:
        flash("PDF report not available.", "warning")
        return redirect(url_for('reports'))

    full_pdf_path = os.path.join(app.root_path, '..', report.pdf_path)
    if not os.path.exists(full_pdf_path):
        flash("PDF file not found on server.", "warning")
        return redirect(url_for('reports'))

    return send_from_directory(os.path.dirname(full_pdf_path), os.path.basename(full_pdf_path), as_attachment=True)

# Placeholder routes for standalone sub-screenings
@app.route('/visual-screening')
@login_required
def visual_screening():
    return render_template(
        'feature_placeholder.html',
        title="Visual Health Screening",
        description="Analyze observational features such as the tongue, eyes, and nails for preliminary nutritional and metabolic risk markers.",
        icon="bi bi-eye-fill",
        action_type="screening"
    )

@app.route('/lab-analysis')
@login_required
def lab_analysis():
    return render_template(
        'feature_placeholder.html',
        title="Lab Report Analysis",
        description="Upload blood panel and laboratory reports to organize relevant clinical values alongside screening indicators.",
        icon="bi bi-clipboard2-pulse-fill",
        action_type="screening"
    )

@app.route('/symptom-assessment')
@login_required
def symptom_assessment():
    return render_template(
        'feature_placeholder.html',
        title="Symptom Assessment",
        description="Answer targeted guided questions about current symptoms to evaluate potential physiological risk factors.",
        icon="bi bi-question-circle-fill",
        action_type="screening"
    )

@app.route('/run-mock-screening', methods=['POST'])
@login_required
def run_mock_screening():
    formatted_date = datetime.now().strftime("%b %d, %Y")
    with Session() as db_session:
        new_report = HealthReport(
            user_id=current_user.id,
            title="General Health Screening",
            screening_type="Preliminary Visual & Symptom Assessment",
            category_count=4,
            nutrition_risk="Moderate screening risk",
            metabolic_risk="Low screening risk",
            general_risk="Low screening risk",
            summary="Observational analysis and symptom review completed. Moderate screening risk noted in nutritional category. All other evaluated categories within baseline bounds.",
            has_lab_report=False,
            created_at=formatted_date
        )
        db_session.add(new_report)
        db_session.commit()

    flash("Sample Health Screening generated successfully!", "success")
    return redirect(url_for('reports'))

@app.route('/reports')
@login_required
def reports():
    with Session() as db_session:
        user_reports = db_session.query(HealthReport).filter_by(user_id=current_user.id).order_by(HealthReport.id.desc()).all()
        for r in user_reports:
            db_session.expunge(r)

    return render_template('reports.html', reports=user_reports, single_report=None)

@app.route('/reports/<int:report_id>')
@login_required
def report_detail(report_id):
    with Session() as db_session:
        report = db_session.query(HealthReport).filter_by(id=report_id, user_id=current_user.id).first()
        if report:
            db_session.expunge(report)

    if not report:
        flash("Report not found.", "warning")
        return redirect(url_for('reports'))

    return render_template('reports.html', reports=[], single_report=report)

@app.route('/health-history')
@login_required
def health_history():
    with Session() as db_session:
        user_reports = db_session.query(HealthReport).filter_by(user_id=current_user.id).order_by(HealthReport.id.desc()).all()
        for r in user_reports:
            db_session.expunge(r)

    return render_template('health_history.html', reports=user_reports)

@app.route('/profile')
@login_required
def profile():
    with Session() as db_session:
        user_profile = db_session.query(UserProfile).filter_by(user_id=current_user.id).first()
        if user_profile:
            db_session.expunge(user_profile)

    return render_template('profile.html', profile=user_profile)

# ==================================================
# HEALTH LOCKER & DOCTOR SHARING ROUTES
# ==================================================

@app.route('/health-locker')
@login_required
def health_locker():
    now_ts = time.time()
    with Session() as db_session:
        personal_health = db_session.query(UserPersonalHealth).filter_by(user_id=current_user.id).first()
        if personal_health:
            db_session.expunge(personal_health)

        documents = db_session.query(MedicalDocument).filter_by(user_id=current_user.id).order_by(MedicalDocument.id.desc()).all()
        for d in documents:
            db_session.expunge(d)

        reports = db_session.query(HealthReport).filter_by(user_id=current_user.id).order_by(HealthReport.id.desc()).all()
        for r in reports:
            db_session.expunge(r)

        active_emergency_share = db_session.query(EmergencyAccessShare).filter_by(user_id=current_user.id, is_revoked=False).order_by(EmergencyAccessShare.id.desc()).first()
        if active_emergency_share:
            db_session.expunge(active_emergency_share)

        all_doc_shares = db_session.query(DoctorShare).filter_by(user_id=current_user.id).order_by(DoctorShare.id.desc()).all()
        
        active_doctor_shares = []
        expired_doctor_shares = []
        for ds in all_doc_shares:
            db_session.expunge(ds)
            try:
                items = json.loads(ds.shared_sections_json)
                ds.shared_count = len(items)
            except Exception:
                ds.shared_count = 0
            
            # Format expiration date
            exp_dt = datetime.fromtimestamp(ds.expires_at_timestamp)
            ds.formatted_expires = exp_dt.strftime("%b %d, %Y %I:%M %p")

            if not ds.is_revoked and now_ts < ds.expires_at_timestamp:
                active_doctor_shares.append(ds)
            else:
                expired_doctor_shares.append(ds)

    return render_template(
        'health_locker.html',
        user=current_user,
        personal_health=personal_health,
        documents=documents,
        reports=reports,
        active_emergency_share=active_emergency_share,
        active_doctor_shares=active_doctor_shares,
        expired_doctor_shares=expired_doctor_shares
    )

@app.route('/health-locker/update-personal-info', methods=['POST'])
@login_required
def update_personal_health_info():
    full_name = request.form.get('full_name', '').strip()
    dob = request.form.get('dob', '').strip()
    blood_group = request.form.get('blood_group', '').strip()
    emergency_contact = request.form.get('emergency_contact', '').strip()
    known_allergies = request.form.get('known_allergies', '').strip()
    medical_conditions = request.form.get('medical_conditions', '').strip()
    current_medications = request.form.get('current_medications', '').strip()
    preferred_hospital_doctor = request.form.get('preferred_hospital_doctor', '').strip()

    with Session() as db_session:
        ph = db_session.query(UserPersonalHealth).filter_by(user_id=current_user.id).first()
        if not ph:
            ph = UserPersonalHealth(user_id=current_user.id)
            db_session.add(ph)

        ph.full_name = full_name
        ph.dob = dob
        ph.blood_group = blood_group
        ph.emergency_contact = emergency_contact
        ph.known_allergies = known_allergies
        ph.medical_conditions = medical_conditions
        ph.current_medications = current_medications
        ph.preferred_hospital_doctor = preferred_hospital_doctor
        db_session.commit()

    flash("Personal health details updated successfully.", "success")
    return redirect(url_for('health_locker'))

@app.route('/health-locker/upload', methods=['POST'])
@login_required
def upload_medical_document():
    doc_name = request.form.get('doc_name', '').strip()
    doc_type = request.form.get('doc_type', 'Medical document').strip()
    file_obj = request.files.get('document_file')

    if not doc_name or not file_obj or not file_obj.filename:
        flash("Please provide a document title and select a valid file.", "warning")
        return redirect(url_for('health_locker'))

    ext = os.path.splitext(file_obj.filename)[1].lower()
    allowed_exts = ['.pdf', '.jpg', '.jpeg', '.png']
    if ext not in allowed_exts:
        flash("Unsupported file format. Please upload PDF, JPG, or PNG files.", "danger")
        return redirect(url_for('health_locker'))

    locker_dir = os.path.join(app.root_path, 'uploads', 'locker', str(current_user.id))
    os.makedirs(locker_dir, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex[:10]}_{file_obj.filename}"
    full_save_path = os.path.join(locker_dir, unique_filename)
    file_obj.save(full_save_path)

    relative_file_path = os.path.join('application', 'uploads', 'locker', str(current_user.id), unique_filename)
    formatted_date = datetime.now().strftime("%d %b %Y")

    with Session() as db_session:
        new_doc = MedicalDocument(
            user_id=current_user.id,
            doc_name=doc_name,
            doc_type=doc_type,
            file_path=relative_file_path,
            file_name=file_obj.filename,
            upload_date=formatted_date
        )
        db_session.add(new_doc)
        db_session.commit()

    flash(f"Document '{doc_name}' uploaded successfully to your Health Locker.", "success")
    return redirect(url_for('health_locker'))

@app.route('/health-locker/document/<int:doc_id>/view')
@login_required
def view_medical_document(doc_id):
    with Session() as db_session:
        doc = db_session.get(MedicalDocument, doc_id)
        if not doc or doc.user_id != current_user.id:
            flash("Document not found or unauthorized access.", "danger")
            return redirect(url_for('health_locker'))
        db_session.expunge(doc)

    full_path = os.path.join(app.root_path, '..', doc.file_path)
    if not os.path.exists(full_path):
        flash("Document file not found on server.", "warning")
        return redirect(url_for('health_locker'))

    return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path), as_attachment=False)

@app.route('/health-locker/document/<int:doc_id>/download')
@login_required
def download_medical_document(doc_id):
    with Session() as db_session:
        doc = db_session.get(MedicalDocument, doc_id)
        if not doc or doc.user_id != current_user.id:
            flash("Document not found or unauthorized access.", "danger")
            return redirect(url_for('health_locker'))
        db_session.expunge(doc)

    full_path = os.path.join(app.root_path, '..', doc.file_path)
    if not os.path.exists(full_path):
        flash("Document file not found on server.", "warning")
        return redirect(url_for('health_locker'))

    return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path), as_attachment=True, download_name=doc.file_name)

@app.route('/health-locker/document/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_medical_document(doc_id):
    with Session() as db_session:
        doc = db_session.get(MedicalDocument, doc_id)
        if not doc or doc.user_id != current_user.id:
            flash("Document not found or unauthorized.", "danger")
            return redirect(url_for('health_locker'))

        full_path = os.path.join(app.root_path, '..', doc.file_path)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except Exception:
                pass

        doc_name = doc.doc_name
        db_session.delete(doc)
        db_session.commit()

    flash(f"Document '{doc_name}' has been deleted from your Health Locker.", "info")
    return redirect(url_for('health_locker'))

@app.route('/health-locker/emergency-access/generate', methods=['POST'])
@login_required
def generate_emergency_access():
    shared_items = request.form.getlist('shared_items')
    formatted_date = datetime.now().strftime("%b %d, %Y %I:%M %p")
    new_token = uuid.uuid4().hex

    with Session() as db_session:
        active_shares = db_session.query(EmergencyAccessShare).filter_by(user_id=current_user.id, is_revoked=False).all()
        for share in active_shares:
            share.is_revoked = True

        new_share = EmergencyAccessShare(
            user_id=current_user.id,
            token=new_token,
            shared_sections_json=json.dumps(shared_items),
            is_revoked=False,
            created_at=formatted_date
        )
        db_session.add(new_share)
        db_session.commit()

    flash("Emergency access link generated successfully!", "success")
    return redirect(url_for('health_locker'))

@app.route('/health-locker/emergency-access/revoke', methods=['POST'])
@login_required
def revoke_emergency_access():
    with Session() as db_session:
        active_shares = db_session.query(EmergencyAccessShare).filter_by(user_id=current_user.id, is_revoked=False).all()
        for share in active_shares:
            share.is_revoked = True
        db_session.commit()

    flash("Emergency access link has been revoked.", "info")
    return redirect(url_for('health_locker'))

@app.route('/emergency-access/<string:token>')
def view_emergency_access(token):
    with Session() as db_session:
        share = db_session.query(EmergencyAccessShare).filter_by(token=token).first()
        if not share or share.is_revoked:
            return render_template('emergency_view.html', is_revoked=True, share=None)

        db_session.expunge(share)
        patient_user = db_session.get(User, share.user_id)
        if patient_user:
            db_session.expunge(patient_user)

        personal_health = db_session.query(UserPersonalHealth).filter_by(user_id=share.user_id).first()
        if personal_health:
            db_session.expunge(personal_health)

    patient_name = personal_health.full_name if (personal_health and personal_health.full_name) else (patient_user.username if patient_user else "Patient")
    try:
        shared_items = json.loads(share.shared_sections_json)
    except Exception:
        shared_items = []

    return render_template(
        'emergency_view.html',
        is_revoked=False,
        share=share,
        personal_health=personal_health,
        patient_name=patient_name,
        shared_items=shared_items
    )

# ==================================================
# DOCTOR SHARING ENDPOINTS
# ==================================================

@app.route('/health-locker/doctor-share/create', methods=['POST'])
@login_required
def create_doctor_share():
    shared_items = request.form.getlist('shared_items')
    if not shared_items:
        flash("Please select at least one item to share with your doctor.", "warning")
        return redirect(url_for('health_locker'))

    duration_option = request.form.get('duration_option', '24')
    if duration_option == 'custom':
        try:
            duration_hours = float(request.form.get('custom_hours', '24'))
        except ValueError:
            duration_hours = 24.0
    else:
        try:
            duration_hours = float(duration_option)
        except ValueError:
            duration_hours = 24.0

    now = datetime.now()
    now_ts = time.time()
    expires_at_ts = now_ts + (duration_hours * 3600.0)
    formatted_created = now.strftime("%b %d, %Y %I:%M %p")
    new_token = uuid.uuid4().hex

    with Session() as db_session:
        new_share = DoctorShare(
            user_id=current_user.id,
            token=new_token,
            shared_sections_json=json.dumps(shared_items),
            duration_hours=duration_hours,
            created_at=formatted_created,
            expires_at_timestamp=expires_at_ts,
            is_revoked=False
        )
        db_session.add(new_share)
        db_session.commit()

    flash("Doctor Share link created successfully! Copy or share the link with your doctor.", "success")
    return redirect(url_for('health_locker'))

@app.route('/health-locker/doctor-share/<int:share_id>/revoke', methods=['POST'])
@login_required
def revoke_doctor_share(share_id):
    with Session() as db_session:
        share = db_session.get(DoctorShare, share_id)
        if not share or share.user_id != current_user.id:
            flash("Doctor share link not found or unauthorized.", "danger")
            return redirect(url_for('health_locker'))

        share.is_revoked = True
        db_session.commit()

    flash("Doctor access has been revoked. The link is no longer usable.", "info")
    return redirect(url_for('health_locker'))

@app.route('/doctor-share/<string:token>')
def view_doctor_share(token):
    now_ts = time.time()
    now_str = datetime.now().strftime("%b %d, %Y %I:%M %p")

    with Session() as db_session:
        share = db_session.query(DoctorShare).filter_by(token=token).first()
        if not share or share.is_revoked:
            return render_template('doctor_share_view.html', is_revoked=True, is_expired=False, share=None)

        if now_ts >= share.expires_at_timestamp:
            return render_template('doctor_share_view.html', is_revoked=False, is_expired=True, share=None)

        # Audit log update: record last accessed timestamp
        share.last_accessed_at = now_str
        db_session.commit()
        db_session.refresh(share)

        db_session.expunge(share)
        patient_user = db_session.get(User, share.user_id)
        if patient_user:
            db_session.expunge(patient_user)

        personal_health = db_session.query(UserPersonalHealth).filter_by(user_id=share.user_id).first()
        if personal_health:
            db_session.expunge(personal_health)

        reports = db_session.query(HealthReport).filter_by(user_id=share.user_id).order_by(HealthReport.id.desc()).all()
        for r in reports:
            db_session.expunge(r)

        documents = db_session.query(MedicalDocument).filter_by(user_id=share.user_id).order_by(MedicalDocument.id.desc()).all()
        for d in documents:
            db_session.expunge(d)

    patient_name = personal_health.full_name if (personal_health and personal_health.full_name) else (patient_user.username if patient_user else "Patient")
    try:
        shared_items = json.loads(share.shared_sections_json)
    except Exception:
        shared_items = []

    exp_dt = datetime.fromtimestamp(share.expires_at_timestamp)
    formatted_expires_at = exp_dt.strftime("%b %d, %Y %I:%M %p")

    return render_template(
        'doctor_share_view.html',
        is_revoked=False,
        is_expired=False,
        share=share,
        patient_name=patient_name,
        personal_health=personal_health,
        reports=reports,
        documents=documents,
        shared_items=shared_items,
        formatted_expires_at=formatted_expires_at
    )

@app.route('/doctor-share/<string:token>/document/<int:doc_id>/view')
def view_shared_doctor_document(token, doc_id):
    now_ts = time.time()
    with Session() as db_session:
        share = db_session.query(DoctorShare).filter_by(token=token).first()
        if not share or share.is_revoked or now_ts >= share.expires_at_timestamp:
            flash("Doctor sharing link is invalid or expired.", "danger")
            return redirect(url_for('login'))

        doc = db_session.get(MedicalDocument, doc_id)
        if not doc or doc.user_id != share.user_id:
            flash("Document not found or unauthorized.", "danger")
            return redirect(url_for('login'))

        try:
            shared_items = json.loads(share.shared_sections_json)
        except Exception:
            shared_items = []

        if 'lab_reports' not in shared_items and 'medical_documents' not in shared_items:
            flash("Patient did not authorize document sharing.", "danger")
            return redirect(url_for('view_doctor_share', token=token))

        db_session.expunge(doc)

    full_path = os.path.join(app.root_path, '..', doc.file_path)
    if not os.path.exists(full_path):
        flash("File not found on server.", "warning")
        return redirect(url_for('view_doctor_share', token=token))

    return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path), as_attachment=False)

@app.route('/doctor-share/<string:token>/document/<int:doc_id>/download')
def download_shared_doctor_document(token, doc_id):
    now_ts = time.time()
    with Session() as db_session:
        share = db_session.query(DoctorShare).filter_by(token=token).first()
        if not share or share.is_revoked or now_ts >= share.expires_at_timestamp:
            flash("Doctor sharing link is invalid or expired.", "danger")
            return redirect(url_for('login'))

        doc = db_session.get(MedicalDocument, doc_id)
        if not doc or doc.user_id != share.user_id:
            flash("Document not found or unauthorized.", "danger")
            return redirect(url_for('login'))

        try:
            shared_items = json.loads(share.shared_sections_json)
        except Exception:
            shared_items = []

        if 'lab_reports' not in shared_items and 'medical_documents' not in shared_items:
            flash("Patient did not authorize document sharing.", "danger")
            return redirect(url_for('view_doctor_share', token=token))

        db_session.expunge(doc)

    full_path = os.path.join(app.root_path, '..', doc.file_path)
    if not os.path.exists(full_path):
        flash("File not found on server.", "warning")
        return redirect(url_for('view_doctor_share', token=token))

    return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path), as_attachment=True, download_name=doc.file_name)

@app.route('/diet-plan')
@login_required
def diet_plan():
    with Session() as db_session:
        profile = db_session.query(UserProfile).filter_by(user_id=current_user.id).first()
        personal_health = db_session.query(UserPersonalHealth).filter_by(user_id=current_user.id).first()
        reports = db_session.query(HealthReport).filter_by(user_id=current_user.id).order_by(HealthReport.id.desc()).all()
        if profile:
            db_session.expunge(profile)
        if personal_health:
            db_session.expunge(personal_health)
        for r in reports:
            db_session.expunge(r)

    latest_report = reports[0] if reports else None
    diet_guidance = generate_diet_guidance(current_user, profile, personal_health, latest_report)

    return render_template(
        'diet_plan.html',
        user=current_user,
        profile=profile,
        personal_health=personal_health,
        latest_report=latest_report,
        diet_guidance=diet_guidance
    )

@app.route('/diet-plan/pdf')
@login_required
def diet_plan_pdf():
    with Session() as db_session:
        profile = db_session.query(UserProfile).filter_by(user_id=current_user.id).first()
        personal_health = db_session.query(UserPersonalHealth).filter_by(user_id=current_user.id).first()
        reports = db_session.query(HealthReport).filter_by(user_id=current_user.id).order_by(HealthReport.id.desc()).all()
        if profile:
            db_session.expunge(profile)
        if personal_health:
            db_session.expunge(personal_health)
        for r in reports:
            db_session.expunge(r)

    latest_report = reports[0] if reports else None
    diet_guidance = generate_diet_guidance(current_user, profile, personal_health, latest_report)

    pdf_dir = os.path.join(app.root_path, '..', 'reports', 'pdf')
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_filename = f"diet_guidance_user_{current_user.id}.pdf"
    pdf_path = os.path.join(pdf_dir, pdf_filename)

    generate_diet_pdf(
        output_path=pdf_path,
        user_name=current_user.username,
        user_email=current_user.email,
        diet_guidance=diet_guidance
    )

    return send_from_directory(
        pdf_dir,
        pdf_filename,
        as_attachment=True,
        download_name=f"VitaSense_Diet_Guidance_{current_user.username}.pdf"
    )

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))
