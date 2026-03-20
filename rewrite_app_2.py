import re

with open('app.py', 'r') as f:
    content = f.read()

# Add imports
imports = """from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session, g
from functools import wraps
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
"""
content = re.sub(r"from flask import Flask.*", imports, content)

# Replace get_current_user_id
new_get_current_user_id = """# Helper to get current user ID
def get_current_user_id():
    return getattr(g, 'user_id', None)
"""
content = re.sub(r"# Helper to get current user ID.*?(?=# Helper to get current manager)", new_get_current_user_id, content, flags=re.DOTALL)

# Add token_required decorator
token_decorator = """
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]

        if not token and 'token' in request.args:
            token = request.args.get('token')

        if not token:
            return jsonify({'error': 'Token is missing!'}), 401

        try:
            secret = app.config.get('SECRET_KEY') or 'super-secret'
            data = jwt.decode(token, secret, algorithms=["HS256"])
            current_user = User.query.filter_by(id=data['user_id']).first()
            if not current_user or current_user.jwt_token != token:
                return jsonify({'error': 'Token is invalid or expired!'}), 401

            g.user_id = current_user.id
        except Exception as e:
            return jsonify({'error': 'Token is invalid!'}), 401

        return f(*args, **kwargs)
    return decorated

"""

# Insert right before @app.route('/')
content = content.replace("@app.route('/')", token_decorator + "@app.route('/')")

with open('app.py', 'w') as f:
    f.write(content)

print("token_required added")
