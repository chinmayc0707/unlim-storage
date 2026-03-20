with open('models.py', 'r') as f:
    content = f.read()

# Replace User model
import re

user_model_regex = r"class User\(db\.Model\):.*?(?=\nclass Folder\(db\.Model\):)"
new_user_model = """class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True) # Adding password hash
    jwt_token = db.Column(db.String(512), nullable=True) # Adding jwt token
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    session_string = db.Column(db.Text, nullable=True)

    # Relationships
    folders = db.relationship('Folder', backref='owner', lazy=True)
    files = db.relationship('File', backref='owner', lazy=True)
"""

content = re.sub(user_model_regex, new_user_model, content, flags=re.DOTALL)

with open('models.py', 'w') as f:
    f.write(content)

print("models.py updated")
