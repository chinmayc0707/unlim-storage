import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # Get database URL and handle postgres:// -> postgresql:// conversion for SQLAlchemy
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = db_url
    else:
        # Fallback to in-memory SQLite for testing/local development
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Telegram Config
    API_ID = os.environ.get('API_ID')
    API_HASH = os.environ.get('API_HASH') 
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    # Chat ID to store files (can be a channel or "me")
    STORAGE_CHAT_ID = os.environ.get('STORAGE_CHAT_ID') or "me"
