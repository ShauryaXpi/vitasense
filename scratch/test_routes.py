import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from application import app, Session
from application.models import User, UserProfile

app.config['TESTING'] = True
client = app.test_client()

# Create or get test user
with Session() as db_session:
    user = db_session.query(User).first()
    user_id = user.id if user else 1

with client.session_transaction() as sess:
    sess['_user_id'] = str(user_id)
    sess['_fresh'] = True

routes_to_test = ['/', '/health-locker', '/doctor-sharing', '/diet-plan', '/reports', '/health-history']

for r in routes_to_test:
    res = client.get(r, follow_redirects=True)
    print(f"Route '{r}': Status Code = {res.status_code}")
    if res.status_code != 200:
        print(f"ERROR on {r}:\n{res.data.decode('utf-8', errors='ignore')[:500]}")
