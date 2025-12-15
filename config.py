import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') 
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Telegram Config
    API_ID = os.environ.get('API_ID')
    API_HASH = os.environ.get('API_HASH') 
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    # Chat ID to store files (can be a channel or "me")
    STORAGE_CHAT_ID = os.environ.get('STORAGE_CHAT_ID') or "me"
