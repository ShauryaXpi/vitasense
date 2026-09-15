import os
from flask import Flask
from dotenv import load_dotenv, find_dotenv
from authlib.integrations.flask_client import OAuth
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from flask_login import LoginManager

envpath = find_dotenv()
load_dotenv(envpath)

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET") or os.getenv("SECRET_KEY", "so_fucking_secret")

# Database Setup with pure SQLAlchemy
engine = create_engine(f"sqlite:///..appdata.db")
Session = sessionmaker(bind=engine)

# Authlib Google OAuth setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    access_token_url='https://oauth2.googleapis.com/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
)

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "danger"

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Create tables
from application.models import Base
Base.metadata.create_all(bind=engine)

import application.routes