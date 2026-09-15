import os
import uuid
import requests
from flask import render_template, redirect, url_for, request, session, flash, send_from_directory, abort, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from application import app, google, Session
from application.models import User, UserProfile

@app.route('/')
@login_required
def index():
    with Session() as db_session:
        profile = db_session.query(UserProfile).filter_by(user_id=current_user.id).first()
        if profile:
            db_session.expunge(profile)

    if not profile or not profile.onboarding_completed:
        return redirect(url_for('onboarding'))

    return render_template('index.html', user=current_user, profile=profile)

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
        # Convert height to meters
        if height_unit == 'cm':
            height_m = height / 100.0
        else:
            # height is in inches
            height_m = height * 0.0254

        # Convert weight to kg
        if weight_unit == 'kg':
            weight_kg = weight
        else:
            # weight is in lb
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

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))