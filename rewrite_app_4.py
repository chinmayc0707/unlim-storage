import re
import datetime

with open('app.py', 'r') as f:
    content = f.read()

# Replace /api/auth/login and /api/auth/verify with a new local login
login_route = """@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    phone = data.get('phone')
    password = data.get('password')

    if not phone or not password:
        return jsonify({'error': 'Phone and password required'}), 400

    user = User.query.filter_by(phone=phone).first()

    if not user or not user.password_hash or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401

    secret = app.config.get('SECRET_KEY') or 'super-secret'
    # Use datetime directly since datetime is imported
    # Actually wait, let's use datetime.utcnow() directly
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + datetime.timedelta(days=7)
    }, secret, algorithm="HS256")

    user.jwt_token = token
    db.session.commit()

    return jsonify({'token': token, 'status': 'authenticated'})
"""

# Replace the old /api/auth/login and /api/auth/verify
content = re.sub(r"@app\.route\('/api/auth/login'.*?def login\(\):.*?@app\.route\('/api/auth/verify'.*?def verify\(\):.*?(?=@app\.route\('/api/auth/logout')", login_route + '\n', content, flags=re.DOTALL)

with open('app.py', 'w') as f:
    f.write(content)
