from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session, g
from functools import wraps
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from models import db, File, Folder, User, generate_codeword
from telegram_manager import get_manager, remove_manager
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config.from_object(Config)

# Initialize DB
db.init_app(app)

# Trigger new commit for GitHub sync


with app.app_context():
    # Drop everything to handle schema changes for this task
    # In production, use migrations
    db.create_all()

# Helper to get current user ID
def get_current_user_id():
    return getattr(g, 'user_id', None)
# Helper to get current manager
def get_current_manager():
    user_id = get_current_user_id()
    if user_id:
        # Fetch user to get session string
        user = User.query.get(user_id)
        if user and user.session_string:
             manager = get_manager(user_id, session_string=user.session_string)
        else:
             # Fallback or error state?
             # For now, if no session string, we can't connect, so just get a blank manager or None?
             # But get_manager creates new one.
             manager = get_manager(user_id)
        
        # Ensure connected if we have a user_id (should be authorized)
        # However, checking connection every time might be slow?
        # Let's rely on manager state
        return manager
    return None


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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    if get_current_user_id():
        return redirect(url_for('index'))
    return render_template('login.html')

# --- Auth Routes ---
@app.route('/api/auth/status')
@token_required
def auth_status():
    return jsonify({'authenticated': True})

@app.route('/api/auth/register', methods=['POST'])
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

@app.route('/api/auth/login', methods=['POST'])
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
        'exp': datetime.utcnow() + timedelta(days=7)
    }, secret, algorithm="HS256")

    user.jwt_token = token
    db.session.commit()

    return jsonify({'token': token, 'status': 'authenticated'})

@app.route('/api/auth/logout', methods=['POST'])
@token_required
def logout():
    user_id = get_current_user_id()
    user = User.query.get(user_id)
    if user:
        user.jwt_token = None
        db.session.commit()
    return jsonify({'status': 'logged_out'})

# --- File Routes ---
@app.route('/api/files')
@token_required
def list_files():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    parent_id = request.args.get('parent_id')
    if parent_id == 'null' or parent_id == '':
        parent_id = None

    folders = Folder.query.filter_by(parent_id=parent_id, user_id=user_id).all()
    files = File.query.filter_by(parent_id=parent_id, user_id=user_id).all()

    result = [f.to_dict() for f in folders] + [f.to_dict() for f in files]
    return jsonify(result)

@app.route('/api/storage')
@token_required
def get_storage_usage():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
        
    # Calculate sum of all file sizes for the user
    total_bytes = db.session.query(db.func.sum(File.size)).filter(File.user_id == user_id).scalar() or 0
    
    return jsonify({'used': total_bytes})

@app.route('/api/upload', methods=['POST'])
@token_required
def upload_file():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

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
    temp_path = os.path.join(BASE_DIR, 'tmp', codeword)
    os.makedirs(os.path.join(BASE_DIR, 'tmp'), exist_ok=True)
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
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    file = File.query.filter_by(id=file_id, user_id=user_id).first_or_404()

    manager = get_current_manager()

    temp_path = os.path.join(BASE_DIR, 'tmp', f"download_{file_id}")
    os.makedirs(os.path.join(BASE_DIR, 'tmp'), exist_ok=True)

    try:
        manager.download_file(file.message_ids, temp_path)
        response = send_file(
            temp_path,
            as_attachment=True,
            download_name=file.name,
            mimetype=file.mime_type
        )

        @response.call_on_close
        def cleanup():
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    print(f"Error deleting temp file: {e}")
        
        return response

    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        return jsonify({'error': str(e)}), 500

@app.route('/api/folders', methods=['POST'])
@token_required
def create_folder():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

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
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

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
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

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
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

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
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

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
    app.run(debug=True, port=5000,host='0.0.0.0')
