import os
from app import app
from models import db, User

with app.app_context():
    # Will use memory sqlite if no DATABASE_URL, or actual Postgres if available
    db.create_all()
    # Let's see if we can query User
    users = User.query.all()
    print("Database connection and models verified. User count:", len(users))
