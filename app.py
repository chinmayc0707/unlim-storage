from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for
from config import Config
from models import db, File, Folder, User, generate_codeword
from telegram_manager import get_manager, remove_manager
import os
import shutil
import jwt
from functools import wraps
import datetime

app = Flask(__name__)
app.config.from_object(Config)

# Initialize DB
db.init_app(app)

with app.app_context():
    # Drop everything to handle schema changes for this task
    # In production, use migrations
    db.create_all()

def generate_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def decode_token(token):
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# Helper to get current user ID from Request Header or Query Param
def get_current_user_id():
    # 1. Try Authorization header
    auth_header = request.headers.get('Authorization')
    if auth_header:
        try:
            token = auth_header.split(" ")[1]
            return decode_token(token)
        except IndexError:
            pass

    # 2. Try query parameter (for downloads)
    token = request.args.get('token')
    if token:
        return decode_token(token)

    return None

# Helper to get current manager
def get_current_manager():
    user_id = get_current_user_id()
    if user_id:
        manager = get_manager(user_id)
        return manager
    return None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

# --- Auth Routes ---
@app.route('/api/auth/status')
def auth_status():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'authenticated': False})

    manager = get_current_manager()
    return jsonify({'authenticated': manager.connect()})

@app.route('/api/auth/login', methods=['POST'])
def login():
    phone = request.json.get('phone')
    if not phone:
        return jsonify({'error': 'Phone number required'}), 400

    # Use phone as temporary key for manager during login
    # In a real app, we should verify that this request comes from the same user flow
    # Since we don't have a session, we rely on the phone number.
    # We could issue a temporary token here, but for simplicity, let's assume
    # the client will send the same phone number for verification.

    manager = get_manager(f"pending_{phone}")

    success, error = manager.send_code(phone)
    if success:
        return jsonify({'status': 'code_sent', 'phone': phone})
    else:
        remove_manager(f"pending_{phone}")
        return jsonify({'error': error}), 400

@app.route('/api/auth/verify', methods=['POST'])
def verify():
    code = request.json.get('code')
    password = request.json.get('password')
    phone = request.json.get('phone') # Phone must be passed back

    if not code:
        return jsonify({'error': 'Code required'}), 400
    if not phone:
        return jsonify({'error': 'Phone number required'}), 400

    # Retrieve the pending manager
    pending_key = f"pending_{phone}"
    manager = get_manager(pending_key)

    success, error = manager.sign_in(code, password)

    if success:
        # User authenticated with Telegram.
        # Create or Get User in DB
        user = User.query.filter_by(phone=phone).first()
        if not user:
            user = User(phone=phone)
            db.session.add(user)
            db.session.commit()

        # Migrate the session file from pending to user_id

        # 1. Close pending manager
        remove_manager(pending_key)
        try:
            manager.client.loop.run_until_complete(manager.client.disconnect())
        except:
            pass

        # 2. Rename session file
        old_session = os.path.join('sessions', f"user_pending_{phone}.session")
        new_session = os.path.join('sessions', f"user_{user.id}.session")

        if os.path.exists(old_session):
            if os.path.exists(new_session):
                os.remove(new_session)
            os.rename(old_session, new_session)

        # 3. Generate Token
        token = generate_token(user.id)

        return jsonify({'status': 'authenticated', 'token': token})

    elif error == 'PASSWORD_REQUIRED':
        return jsonify({'status': 'password_required'}), 401
    else:
        return jsonify({'error': error}), 400

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    manager = get_current_manager()
    user_id = get_current_user_id()
    if manager:
        try:
            manager.logout()
            remove_manager(user_id)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return jsonify({'status': 'logged_out'})

# --- File Routes ---
@app.route('/api/files')
@token_required
def list_files():
    user_id = get_current_user_id()
    parent_id = request.args.get('parent_id')
    if parent_id == 'null' or parent_id == '':
        parent_id = None

    folders = Folder.query.filter_by(parent_id=parent_id, user_id=user_id).all()
    files = File.query.filter_by(parent_id=parent_id, user_id=user_id).all()

    result = [f.to_dict() for f in folders] + [f.to_dict() for f in files]
    return jsonify(result)

@app.route('/api/upload', methods=['POST'])
@token_required
def upload_file():
    user_id = get_current_user_id()
    manager = get_current_manager()

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    parent_id = request.form.get('parent_id')
    if parent_id == 'null' or parent_id == '':
        parent_id = None

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    codeword = generate_codeword()
    temp_path = os.path.join('tmp', codeword)
    os.makedirs('tmp', exist_ok=True)
    file.save(temp_path)

    try:
        new_file = File(
            id=codeword,
            name=file.filename,
            parent_id=parent_id,
            user_id=user_id,
            size=os.path.getsize(temp_path),
            mime_type=file.content_type
        )
        db.session.add(new_file)

        message_ids = manager.upload_file(temp_path, codeword, file_name=file.filename)
        new_file.message_ids = message_ids
        db.session.commit()

        return jsonify(new_file.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/api/download/<file_id>')
@token_required
def download_file(file_id):
    user_id = get_current_user_id()
    file = File.query.filter_by(id=file_id, user_id=user_id).first_or_404()

    manager = get_current_manager()

    temp_path = os.path.join('tmp', f"download_{file_id}")
    os.makedirs('tmp', exist_ok=True)

    try:
        manager.download_file(file.message_ids, temp_path)
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=file.name,
            mimetype=file.mime_type
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/folders', methods=['POST'])
@token_required
def create_folder():
    user_id = get_current_user_id()
    data = request.json
    name = data.get('name')
    parent_id = data.get('parent_id')
    if parent_id == 'null': parent_id = None

    if not name:
        return jsonify({'error': 'Name required'}), 400

    new_folder = Folder(name=name, parent_id=parent_id, user_id=user_id)
    db.session.add(new_folder)
    db.session.commit()

    return jsonify(new_folder.to_dict()), 201

@app.route('/api/move', methods=['POST'])
@token_required
def move_item():
    user_id = get_current_user_id()
    data = request.json
    items = data.get('items')
    new_parent_id = data.get('new_parent_id')

    if new_parent_id == 'null':
        new_parent_id = None

    if not items:
        item_id = data.get('id')
        item_type = data.get('type')
        if item_id and item_type:
            items = [{'id': item_id, 'type': item_type}]
        else:
            return jsonify({'error': 'No items specified'}), 400

    try:
        for item_data in items:
            item_id = item_data.get('id')
            item_type = item_data.get('type')

            # Prevent moving folder into itself or its children
            if item_type == 'folder':
                if item_id == new_parent_id:
                    return jsonify({'error': 'Cannot move folder into itself'}), 400

                # Check if new_parent_id is a child of item_id
                # Only check folders belonging to user
                current = Folder.query.filter_by(id=new_parent_id, user_id=user_id).first()
                while current:
                    if current.id == item_id:
                        return jsonify({'error': 'Cannot move folder into its own subfolder'}), 400
                    current = Folder.query.filter_by(id=current.parent_id, user_id=user_id).first() if current.parent_id else None

            if item_type == 'folder':
                item = Folder.query.filter_by(id=item_id, user_id=user_id).first_or_404()
            else:
                item = File.query.filter_by(id=item_id, user_id=user_id).first_or_404()

            item.parent_id = new_parent_id

        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def copy_recursive(item, new_parent_id, user_id, manager):
    if isinstance(item, File):
        new_codeword = generate_codeword()

        # Copy Telegram messages
        try:
            new_message_ids = manager.copy_file(item.message_ids, new_codeword)

            new_file = File(
                id=new_codeword,
                name=item.name,
                parent_id=new_parent_id,
                user_id=user_id,
                size=item.size,
                mime_type=item.mime_type
            )
            new_file.message_ids = new_message_ids
            db.session.add(new_file)
        except Exception as e:
            print(f"Error copying file {item.name}: {e}")
            raise e

    elif isinstance(item, Folder):
        new_folder = Folder(
            name=item.name,
            parent_id=new_parent_id,
            user_id=user_id
        )
        db.session.add(new_folder)
        db.session.flush()

        # Copy children
        children_files = File.query.filter_by(parent_id=item.id, user_id=user_id).all()
        for child in children_files:
            copy_recursive(child, new_folder.id, user_id, manager)

        children_folders = Folder.query.filter_by(parent_id=item.id, user_id=user_id).all()
        for child in children_folders:
            copy_recursive(child, new_folder.id, user_id, manager)

@app.route('/api/copy', methods=['POST'])
@token_required
def copy_item():
    user_id = get_current_user_id()
    manager = get_current_manager()

    data = request.json
    items = data.get('items')
    new_parent_id = data.get('new_parent_id')

    if new_parent_id == 'null':
        new_parent_id = None

    if not items:
        item_id = data.get('id')
        item_type = data.get('type')
        if item_id and item_type:
            items = [{'id': item_id, 'type': item_type}]
        else:
            return jsonify({'error': 'No items specified'}), 400

    try:
        for item_data in items:
            item_id = item_data.get('id')
            item_type = item_data.get('type')

            if item_type == 'folder':
                item = Folder.query.filter_by(id=item_id, user_id=user_id).first_or_404()
            else:
                item = File.query.filter_by(id=item_id, user_id=user_id).first_or_404()

            copy_recursive(item, new_parent_id, user_id, manager)

        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/rename', methods=['POST'])
@token_required
def rename_item():
    user_id = get_current_user_id()
    data = request.json
    item_id = data.get('id')
    item_type = data.get('type')
    new_name = data.get('name')

    if not new_name:
        return jsonify({'error': 'New name required'}), 400

    if item_type == 'folder':
        item = Folder.query.filter_by(id=item_id, user_id=user_id).first_or_404()
    else:
        item = File.query.filter_by(id=item_id, user_id=user_id).first_or_404()

    item.name = new_name
    db.session.commit()
    return jsonify({'status': 'success'})

def delete_folder_recursive(folder_id, user_id, manager):
    # 1. Delete all files in this folder
    files = File.query.filter_by(parent_id=folder_id, user_id=user_id).all()
    for file in files:
        try:
            manager.delete_file(file.message_ids)
        except Exception as e:
            print(f"Error deleting file from Telegram: {e}")
        db.session.delete(file)

    # 2. Delete all subfolders recursively
    subfolders = Folder.query.filter_by(parent_id=folder_id, user_id=user_id).all()
    for subfolder in subfolders:
        delete_folder_recursive(subfolder.id, user_id, manager)

    # 3. Delete the folder itself
    folder = Folder.query.filter_by(id=folder_id, user_id=user_id).first()
    if folder:
        db.session.delete(folder)

@app.route('/api/delete', methods=['POST'])
@token_required
def delete_item():
    user_id = get_current_user_id()
    manager = get_current_manager()

    data = request.json
    items = data.get('items')

    # Backward compatibility or single item delete
    if not items:
        item_id = data.get('id')
        item_type = data.get('type')
        if item_id and item_type:
            items = [{'id': item_id, 'type': item_type}]
        else:
            return jsonify({'error': 'No items specified'}), 400

    try:
        for item in items:
            item_id = item.get('id')
            item_type = item.get('type')

            if item_type == 'folder':
                delete_folder_recursive(item_id, user_id, manager)
            else:
                file = File.query.filter_by(id=item_id, user_id=user_id).first()
                if file:
                    try:
                        manager.delete_file(file.message_ids)
                    except:
                        pass
                    db.session.delete(file)

        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
