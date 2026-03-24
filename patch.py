with open("app.py", "r") as f:
    content = f.read()

search = """        for item_data in items:
            item_id = item_data.get('id')
            item_type = item_data.get('type')

            if item_type == 'folder':
                item = Folder.query.filter_by(id=item_id, user_id=user_id).first_or_404()
            else:
                item = File.query.filter_by(id=item_id, user_id=user_id).first_or_404()

            copy_recursive(item, new_parent_id, user_id, manager)"""

replace = """        for item_data in items:
            item_id = item_data.get('id')
            item_type = item_data.get('type')

            # Prevent copying folder into itself or its children
            if item_type == 'folder':
                if item_id == new_parent_id:
                    return jsonify({'error': 'Cannot copy folder into itself'}), 400

                # Check if new_parent_id is a child of item_id
                # Only check folders belonging to user
                current = Folder.query.filter_by(id=new_parent_id, user_id=user_id).first()
                while current:
                    if current.id == item_id:
                        return jsonify({'error': 'Cannot copy folder into its own subfolder'}), 400
                    current = Folder.query.filter_by(id=current.parent_id, user_id=user_id).first() if current.parent_id else None

            if item_type == 'folder':
                item = Folder.query.filter_by(id=item_id, user_id=user_id).first_or_404()
            else:
                item = File.query.filter_by(id=item_id, user_id=user_id).first_or_404()

            copy_recursive(item, new_parent_id, user_id, manager)"""

if search in content:
    content = content.replace(search, replace)
    with open("app.py", "w") as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Search string not found")
