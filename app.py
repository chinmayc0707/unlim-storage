from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for
from config import Config
from models import db, File, Folder, generate_codeword
from telegram_manager import tg_manager
import os
import shutil

app = Flask(__name__)
app.config.from_object(Config)

# Initialize DB
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if not tg_manager.is_connected:
        # Try to connect if session exists
        if not tg_manager.connect():
            return redirect(url_for('login_page'))
    return render_template('index.html')

@app.route('/login')
def login_page():
    if tg_manager.is_connected:
        return redirect(url_for('index'))
    return render_template('login.html')

# --- Auth Routes ---
@app.route('/api/auth/status')
def auth_status():
    is_connected = tg_manager.connect()
    return jsonify({'authenticated': is_connected})

@app.route('/api/auth/login', methods=['POST'])
def login():
    phone = request.json.get('phone')
    if not phone:
        return jsonify({'error': 'Phone number required'}), 400
    
    success, error = tg_manager.send_code(phone)
    if success:
        return jsonify({'status': 'code_sent'})
    else:
        return jsonify({'error': error}), 400

@app.route('/api/auth/verify', methods=['POST'])
def verify():
    code = request.json.get('code')
    password = request.json.get('password')
    
    if not code:
        return jsonify({'error': 'Code required'}), 400
        
    success, error = tg_manager.sign_in(code, password)
    if success:
        return jsonify({'status': 'authenticated'})
    elif error == 'PASSWORD_REQUIRED':
        return jsonify({'status': 'password_required'}), 401
    else:
        return jsonify({'error': error}), 400

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    try:
        tg_manager.logout()
        return jsonify({'status': 'logged_out'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- File Routes ---
@app.route('/api/files')
def list_files():
    if not tg_manager.is_connected:
        return jsonify({'error': 'Not authenticated'}), 401

    parent_id = request.args.get('parent_id')
    if parent_id == 'null' or parent_id == '':
        parent_id = None
        
    folders = Folder.query.filter_by(parent_id=parent_id).all()
    files = File.query.filter_by(parent_id=parent_id).all()
    
    result = [f.to_dict() for f in folders] + [f.to_dict() for f in files]
    return jsonify(result)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if not tg_manager.is_connected:
        return jsonify({'error': 'Not authenticated'}), 401

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
            size=os.path.getsize(temp_path),
            mime_type=file.content_type
        )
        db.session.add(new_file)
        
        message_ids = tg_manager.upload_file(temp_path, codeword, file_name=file.filename)
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
    if not tg_manager.is_connected:
        return jsonify({'error': 'Not authenticated'}), 401

    file = File.query.get_or_404(file_id)
    
    temp_path = os.path.join('tmp', f"download_{file_id}")
    os.makedirs('tmp', exist_ok=True)
    
    try:
        tg_manager.download_file(file.message_ids, temp_path)
        return send_file(
            temp_path, 
            as_attachment=True, 
            download_name=file.name, 
            mimetype=file.mime_type
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/folders', methods=['POST'])
def create_folder():
    if not tg_manager.is_connected:
        return jsonify({'error': 'Not authenticated'}), 401
        
    data = request.json
    name = data.get('name')
    parent_id = data.get('parent_id')
    if parent_id == 'null': parent_id = None
    
    if not name:
        return jsonify({'error': 'Name required'}), 400
        
    new_folder = Folder(name=name, parent_id=parent_id)
    db.session.add(new_folder)
    db.session.commit()
    
    return jsonify(new_folder.to_dict()), 201

@app.route('/api/move', methods=['POST'])
def move_item():
    if not tg_manager.is_connected:
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
                current = Folder.query.get(new_parent_id)
                while current:
                    if current.id == item_id:
                        return jsonify({'error': 'Cannot move folder into its own subfolder'}), 400
                    current = Folder.query.get(current.parent_id) if current.parent_id else None

            if item_type == 'folder':
                item = Folder.query.get_or_404(item_id)
            else:
                item = File.query.get_or_404(item_id)
                
            item.parent_id = new_parent_id
            
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def copy_recursive(item, new_parent_id):
    if isinstance(item, File):
        new_codeword = generate_codeword()
        
        # Copy Telegram messages
        try:
            new_message_ids = tg_manager.copy_file(item.message_ids, new_codeword)
            
            new_file = File(
                id=new_codeword,
                name=item.name, # Keep original name
                parent_id=new_parent_id,
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
            parent_id=new_parent_id
        )
        db.session.add(new_folder)
        db.session.flush() # Flush to get the new ID
        
        # Copy children
        children_files = File.query.filter_by(parent_id=item.id).all()
        for child in children_files:
            copy_recursive(child, new_folder.id)
            
        children_folders = Folder.query.filter_by(parent_id=item.id).all()
        for child in children_folders:
            copy_recursive(child, new_folder.id)

@app.route('/api/copy', methods=['POST'])
def copy_item():
    if not tg_manager.is_connected:
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
            
            if item_type == 'folder':
                item = Folder.query.get_or_404(item_id)
            else:
                item = File.query.get_or_404(item_id)
                
            copy_recursive(item, new_parent_id)
            
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/rename', methods=['POST'])
def rename_item():
    if not tg_manager.is_connected:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.json
    item_id = data.get('id')
    item_type = data.get('type')
    new_name = data.get('name')
    
    if not new_name:
        return jsonify({'error': 'New name required'}), 400
    
    if item_type == 'folder':
        item = Folder.query.get_or_404(item_id)
    else:
        item = File.query.get_or_404(item_id)
        
    item.name = new_name
    db.session.commit()
    return jsonify({'status': 'success'})

def delete_folder_recursive(folder_id):
    # 1. Delete all files in this folder
    files = File.query.filter_by(parent_id=folder_id).all()
    for file in files:
        try:
            tg_manager.delete_file(file.message_ids)
        except Exception as e:
            print(f"Error deleting file from Telegram: {e}")
        db.session.delete(file)
    
    # 2. Delete all subfolders recursively
    subfolders = Folder.query.filter_by(parent_id=folder_id).all()
    for subfolder in subfolders:
        delete_folder_recursive(subfolder.id)
        
    # 3. Delete the folder itself
    folder = Folder.query.get(folder_id)
    if folder:
        db.session.delete(folder)

@app.route('/api/delete', methods=['POST'])
def delete_item():
    if not tg_manager.is_connected:
        return jsonify({'error': 'Not authenticated'}), 401

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
                delete_folder_recursive(item_id)
            else:
                file = File.query.get(item_id)
                if file:
                    try:
                        tg_manager.delete_file(file.message_ids)
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
