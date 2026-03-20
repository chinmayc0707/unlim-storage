with open('app.py', 'r') as f:
    content = f.read()

# I will add /api/auth/register route
register_route = """@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    phone = data.get('phone')
    password = data.get('password')

    if not phone or not password:
        return jsonify({'error': 'Phone and password required'}), 400

    existing_user = User.query.filter_by(phone=phone).first()
    if existing_user:
        return jsonify({'error': 'User already exists'}), 400

    hashed_password = generate_password_hash(password)
    new_user = User(phone=phone, password_hash=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'status': 'registered'}), 201

"""

# Insert register_route before /api/auth/login
content = content.replace("@app.route('/api/auth/login', methods=['POST'])", register_route + "@app.route('/api/auth/login', methods=['POST'])")

with open('app.py', 'w') as f:
    f.write(content)
