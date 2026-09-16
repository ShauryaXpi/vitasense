import os
import uuid
import json
from datetime import datetime
import requests
from flask import render_template, redirect, url_for, request, session, flash, send_from_directory, abort, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from application import app, google, Session
from application.models import User, UserProfile, HealthReport, ClinicalRoom, RoomMember

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

        # Fetch clinical room for user if exists
        user_member = db_session.query(RoomMember).filter_by(user_id=current_user.id).first()
        user_room = None
        if user_member:
            user_room = db_session.get(ClinicalRoom, user_member.room_id)
            if user_room:
                db_session.expunge(user_room)

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
        has_lab_report=has_lab_report,
        user_room=user_room
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

# ================= Clinical Doctor Room Routes =================

@app.route('/room/create', methods=['POST'])
@login_required
def create_room():
    room_name = request.form.get('room_name', '').strip()
    description = request.form.get('description', '').strip()

    if not room_name:
        room_name = f"Dr. {current_user.username.capitalize()}'s Clinical Room"

    room_code = f"DOC-{uuid.uuid4().hex[:6].upper()}"
    formatted_date = datetime.now().strftime("%b %d, %Y")

    with Session() as db_session:
        new_room = ClinicalRoom(
            doctor_id=current_user.id,
            name=room_name,
            code=room_code,
            description=description,
            created_at=formatted_date
        )
        db_session.add(new_room)
        db_session.commit()
        db_session.refresh(new_room)

        # Add doctor as room member
        doc_member = RoomMember(
            room_id=new_room.id,
            user_id=current_user.id,
            role='doctor',
            joined_at=formatted_date
        )
        db_session.add(doc_member)
        db_session.commit()
        room_id = new_room.id

    flash(f"Clinical Room '{room_name}' created! Code: {room_code}", "success")
    return redirect(url_for('view_room', room_id=room_id))

@app.route('/room/join', methods=['POST'])
@login_required
def join_room():
    room_code = request.form.get('room_code', '').strip().upper()
    if not room_code:
        flash("Please enter a valid Room Code.", "warning")
        return redirect(url_for('index'))

    formatted_date = datetime.now().strftime("%b %d, %Y")

    with Session() as db_session:
        room = db_session.query(ClinicalRoom).filter_by(code=room_code).first()
        if not room:
            flash(f"No clinical room found with code '{room_code}'. Please check code and try again.", "danger")
            return redirect(url_for('index'))

        existing_member = db_session.query(RoomMember).filter_by(room_id=room.id, user_id=current_user.id).first()
        if not existing_member:
            new_member = RoomMember(
                room_id=room.id,
                user_id=current_user.id,
                role='patient',
                joined_at=formatted_date
            )
            db_session.add(new_member)
            db_session.commit()
            flash(f"Successfully joined clinical room '{room.name}'!", "success")
        else:
            flash(f"You are already a member of '{room.name}'.", "info")

        room_id = room.id

    return redirect(url_for('view_room', room_id=room_id))

@app.route('/room/<int:room_id>')
@login_required
def view_room(room_id):
    with Session() as db_session:
        room = db_session.get(ClinicalRoom, room_id)
        if not room:
            flash("Clinical Room not found.", "warning")
            return redirect(url_for('index'))

        members = db_session.query(RoomMember).filter_by(room_id=room.id).all()
        member_user_ids = [m.user_id for m in members]
        
        users_list = db_session.query(User).filter(User.id.in_(member_user_ids)).all()
        users_map = {u.id: u for u in users_list}
        doctor_user = users_map.get(room.doctor_id)

        # Collect all health reports for room members (patients)
        member_reports = {}
        for uid in member_user_ids:
            reps = db_session.query(HealthReport).filter_by(user_id=uid).order_by(HealthReport.id.desc()).all()
            for r in reps:
                db_session.expunge(r)
            member_reports[uid] = reps

        is_member = current_user.id in member_user_ids
        is_doctor = (current_user.id == room.doctor_id)
        db_session.expunge(room)

    if not is_member:
        flash("You are not a member of this clinical room.", "danger")
        return redirect(url_for('index'))

    return render_template(
        'room_dashboard.html',
        room=room,
        members=members,
        users_map=users_map,
        doctor_user=doctor_user,
        member_reports=member_reports,
        is_doctor=is_doctor
    )

@app.route('/room/<int:room_id>/add-patient', methods=['POST'])
@login_required
def add_patient_to_room(room_id):
    email = request.form.get('patient_email', '').strip().lower()
    if not email:
        flash("Please enter a patient email address.", "warning")
        return redirect(url_for('view_room', room_id=room_id))

    formatted_date = datetime.now().strftime("%b %d, %Y")

    with Session() as db_session:
        room = db_session.get(ClinicalRoom, room_id)
        if not room or room.doctor_id != current_user.id:
            flash("Only the room doctor can add patients by email.", "danger")
            return redirect(url_for('index'))

        patient_user = db_session.query(User).filter_by(email=email).first()
        if not patient_user:
            flash(f"No registered user found with email '{email}'. Make sure patient has an account.", "warning")
            return redirect(url_for('view_room', room_id=room_id))

        existing_member = db_session.query(RoomMember).filter_by(room_id=room_id, user_id=patient_user.id).first()
        if existing_member:
            flash(f"Patient ({email}) is already in this room.", "info")
        else:
            new_member = RoomMember(
                room_id=room_id,
                user_id=patient_user.id,
                role='patient',
                joined_at=formatted_date
            )
            db_session.add(new_member)
            db_session.commit()
            flash(f"Patient ({patient_user.username or email}) successfully added to room!", "success")

    return redirect(url_for('view_room', room_id=room_id))

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))