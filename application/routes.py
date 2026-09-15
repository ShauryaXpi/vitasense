import os
import uuid
import json
from datetime import datetime
import requests
from flask import render_template, redirect, url_for, request, session, flash, send_from_directory, abort, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from application import app, google, Session
from application.models import User, UserProfile, HealthReport

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
    with Session() as db_session:
        has_past_reports = db_session.query(HealthReport).filter_by(user_id=current_user.id).first() is not None
    return render_template('checkup_questionnaire.html', is_repeat=has_past_reports)

@app.route('/checkup/questionnaire/baseline', methods=['POST'])
@login_required
def save_baseline_questionnaire():
    if 'checkup_data' not in session:
        session['checkup_data'] = {'selected_modules': ['anemia', 'vitamin_d', 'folate', 'iodine'], 'questionnaire': {}, 'visual': {}, 'lab': {}}
    
    q_data = {
        'tiredness': request.form.get('tiredness', ''),
        'visual_changes': request.form.get('visual_changes', ''),
        'supplements': request.form.get('supplements', ''),
        'recent_blood_test': request.form.get('recent_blood_test', ''),
        'health_changes': request.form.get('health_changes', ''),
        'additional_notes': request.form.get('additional_notes', ''),
        'type': 'baseline'
    }
    chk = session['checkup_data']
    chk['questionnaire'] = q_data
    session['checkup_data'] = chk
    return redirect(url_for('checkup_visual'))

@app.route('/checkup/questionnaire/repeat', methods=['POST'])
@login_required
def save_repeat_questionnaire():
    if 'checkup_data' not in session:
        session['checkup_data'] = {'selected_modules': ['anemia', 'vitamin_d', 'folate', 'iodine'], 'questionnaire': {}, 'visual': {}, 'lab': {}}
    
    changes = request.form.getlist('changes')
    q_data = {
        'changes': changes,
        'type': 'repeat'
    }
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
    if 'checkup_data' not in session:
        session['checkup_data'] = {'selected_modules': ['anemia', 'vitamin_d', 'folate', 'iodine'], 'questionnaire': {}, 'visual': {}, 'lab': {}}

    upload_dir = os.path.join(app.root_path, '..', 'assets', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    saved_images = {}
    for key in ['eye_image', 'tongue_image', 'nail_image']:
        file = request.files.get(key)
        if file and file.filename != '':
            ext = os.path.splitext(file.filename)[1]
            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)
            saved_images[key] = f"assets/uploads/{filename}"

    chk = session['checkup_data']
    chk['visual'] = saved_images
    session['checkup_data'] = chk
    return redirect(url_for('checkup_lab'))

@app.route('/checkup/lab')
@login_required
def checkup_lab():
    return render_template('checkup_lab.html')

@app.route('/checkup/lab', methods=['POST'])
@login_required
def save_lab_checkup():
    if 'checkup_data' not in session:
        session['checkup_data'] = {'selected_modules': ['anemia', 'vitamin_d', 'folate', 'iodine'], 'questionnaire': {}, 'visual': {}, 'lab': {}}

    lab_data = {}
    if not request.form.get('skip_lab'):
        upload_dir = os.path.join(app.root_path, '..', 'assets', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        lab_file = request.files.get('lab_file')
        if lab_file and lab_file.filename != '':
            ext = os.path.splitext(lab_file.filename)[1]
            filename = f"lab_{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(upload_dir, filename)
            lab_file.save(filepath)
            lab_data['file'] = f"assets/uploads/{filename}"

        if request.form.get('hb_val'):
            try: lab_data['hb'] = float(request.form.get('hb_val'))
            except ValueError: pass
        if request.form.get('vitd_val'):
            try: lab_data['vitd'] = float(request.form.get('vitd_val'))
            except ValueError: pass
        if request.form.get('folate_val'):
            try: lab_data['folate'] = float(request.form.get('folate_val'))
            except ValueError: pass
        if request.form.get('tsh_val'):
            try: lab_data['tsh'] = float(request.form.get('tsh_val'))
            except ValueError: pass

    lab_data['has_lab'] = len(lab_data) > 0
    chk = session['checkup_data']
    chk['lab'] = lab_data
    session['checkup_data'] = chk
    return redirect(url_for('checkup_analysis'))

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

    exec_summary = f"Screening evaluation completed across {len(selected_modules)} health areas. Primary risk indicator: {risk_eval['nutrition_risk']}."

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

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))