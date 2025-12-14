import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///drive.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Telegram Config
    API_ID = os.environ.get('API_ID') or 27074457
    API_HASH = os.environ.get('API_HASH') or 'ce5c2fa2973a1385e8290f0fa8cb7459'
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    # Chat ID to store files (can be a channel or "me")
    STORAGE_CHAT_ID = os.environ.get('STORAGE_CHAT_ID') or "me"
