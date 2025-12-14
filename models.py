from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import random
import string

db = SQLAlchemy()

def generate_codeword(length=10):
    """Generates a unique random string for use as an ID."""
    letters = string.ascii_letters + string.digits
    return ''.join(random.choice(letters) for i in range(length))

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    session_string = db.Column(db.Text, nullable=True)

    # Relationships
    folders = db.relationship('Folder', backref='owner', lazy=True)
    files = db.relationship('File', backref='owner', lazy=True)

class Folder(db.Model):
    id = db.Column(db.String(20), primary_key=True, default=generate_codeword)
    name = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.String(20), db.ForeignKey('folder.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    subfolders = db.relationship('Folder', backref=db.backref('parent', remote_side=[id]), lazy=True)
    files = db.relationship('File', backref='parent', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': 'folder',
            'parent_id': self.parent_id,
            'created_at': self.created_at.isoformat()
        }

class File(db.Model):
    id = db.Column(db.String(20), primary_key=True, default=generate_codeword)
    name = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.String(20), db.ForeignKey('folder.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    size = db.Column(db.BigInteger, default=0)
    mime_type = db.Column(db.String(100))
    # Store list of message IDs as a JSON string
    _message_ids = db.Column(db.Text, nullable=False, default='[]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def message_ids(self):
        return json.loads(self._message_ids)

    @message_ids.setter
    def message_ids(self, value):
        self._message_ids = json.dumps(value)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'type': 'file',
            'size': self.size,
            'mime_type': self.mime_type,
            'parent_id': self.parent_id,
            'created_at': self.created_at.isoformat()
        }
