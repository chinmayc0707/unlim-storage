from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session
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

with app.app_context():
    # Drop everything to handle schema changes for this task
    # In production, use migrations
    db.create_all()

# Helper to get current user ID
def get_current_user_id():
    return session.get('user_id')

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

@app.route('/')
def index():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for('login_page'))

    manager = get_current_manager()
    if not manager.connect(): # verify authorization
        # Session invalid?
        session.pop('user_id', None)
        return redirect(url_for('login_page'))

    return render_template('index.html')

@app.route('/login')
def login_page():
    if get_current_user_id():
        return redirect(url_for('index'))
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
    manager = get_manager(f"pending_{phone}")

    success, error = manager.send_code(phone)
    if success:
        # Store phone in session to retrieve the correct manager in verify step
        session['pending_phone'] = phone
        return jsonify({'status': 'code_sent'})
    else:
        remove_manager(f"pending_{phone}")
        return jsonify({'error': error}), 400

@app.route('/api/auth/verify', methods=['POST'])
def verify():
    code = request.json.get('code')
    password = request.json.get('password')
    phone = session.get('pending_phone')

    if not code:
        return jsonify({'error': 'Code required'}), 400
    if not phone:
        return jsonify({'error': 'Session expired, please login again'}), 400

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
        
        # Save session string
        user.session_string = manager.get_session_string()
        db.session.commit()

        # No need to move files anymore.
        # Close pending manager
        remove_manager(pending_key)

        # 3. Set user_id in session
        session['user_id'] = user.id
        session.pop('pending_phone', None)

        return jsonify({'status': 'authenticated'})

    elif error == 'PASSWORD_REQUIRED':
        return jsonify({'status': 'password_required'}), 401
    else:
        return jsonify({'error': error}), 400

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    manager = get_current_manager()
    if manager:
        try:
            manager.logout()
        except Exception as e:
            print(f"Error during Telegram logout: {e}")

        try:
            remove_manager(get_current_user_id())
        except Exception as e:
            print(f"Error removing manager: {e}")
            
        # No file deletion needed for StringSession


    session.clear()
    return jsonify({'status': 'logged_out'})

# --- File Routes ---
@app.route('/api/files')
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
def get_storage_usage():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
        
    # Calculate sum of all file sizes for the user
    # Note: We are doing this in Python for simplicity, but could be done with db.func.sum
    files = File.query.filter_by(user_id=user_id).all()
    total_bytes = sum(f.size for f in files)
    
    return jsonify({'used': total_bytes})

@app.route('/api/upload', methods=['POST'])
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
