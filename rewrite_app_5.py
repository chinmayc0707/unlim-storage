import re
from datetime import datetime

with open('app.py', 'r') as f:
    content = f.read()

# Make sure we import datetime properly
if "from datetime import datetime, timedelta" not in content:
    content = content.replace("from datetime import datetime", "from datetime import datetime, timedelta")

# Fix the timedelta usage in login:
content = content.replace("datetime.utcnow() + datetime.timedelta(days=7)", "datetime.utcnow() + timedelta(days=7)")

# Replace get_current_manager logic
manager_logic = """# Helper to get current manager
def get_current_manager():
    user_id = get_current_user_id()
    if user_id:
        user = User.query.get(user_id)
        if user and user.session_string:
             manager = get_manager(user_id, session_string=user.session_string)
        else:
             manager = get_manager(user_id)
        return manager
    return None
"""
# Keep it, but we also need to apply token_required everywhere!

# Apply token_required to routes:
# /api/files, /api/storage, /api/upload, /api/download, /api/folders, /api/move, /api/copy, /api/rename, /api/delete

routes_to_protect = [
    "@app.route('/api/files')",
    "@app.route('/api/storage')",
    "@app.route('/api/upload', methods=['POST'])",
    "@app.route('/api/download/<file_id>')",
    "@app.route('/api/folders', methods=['POST'])",
    "@app.route('/api/move', methods=['POST'])",
    "@app.route('/api/copy', methods=['POST'])",
    "@app.route('/api/rename', methods=['POST'])",
    "@app.route('/api/delete', methods=['POST'])"
]

for route in routes_to_protect:
    content = content.replace(route, route + "\n@token_required")

# Also, index route:
# Since index is the html page, we don't necessarily want token_required returning 401 JSON.
# The frontend should redirect if no token. But wait! Direct visits will fail auth.
# Actually, index is just returning the html. The frontend app.js fetches /api/files, which will 401 if not authed.
# So index shouldn't redirect on backend!

new_index = """@app.route('/')
def index():
    return render_template('index.html')"""

content = re.sub(r"@app\.route\('/'\).*?def index\(\):.*?return render_template\('index\.html'\)", new_index, content, flags=re.DOTALL)

# Same for /api/auth/status
new_status = """@app.route('/api/auth/status')
@token_required
def auth_status():
    return jsonify({'authenticated': True})"""

content = re.sub(r"@app\.route\('/api/auth/status'\).*?def auth_status\(\):.*?return jsonify\({'authenticated': manager\.connect\(\)}\)", new_status, content, flags=re.DOTALL)

# Update logout
new_logout = """@app.route('/api/auth/logout', methods=['POST'])
@token_required
def logout():
    user_id = get_current_user_id()
    user = User.query.get(user_id)
    if user:
        user.jwt_token = None
        db.session.commit()
    return jsonify({'status': 'logged_out'})"""

content = re.sub(r"@app\.route\('/api/auth/logout', methods=\['POST'\]\).*?def logout\(\):.*?return jsonify\({'status': 'logged_out'}\)", new_logout, content, flags=re.DOTALL)

with open('app.py', 'w') as f:
    f.write(content)
