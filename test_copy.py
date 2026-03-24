import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['SECRET_KEY'] = 'test'
os.environ['API_ID'] = '123'
os.environ['API_HASH'] = 'abc'

import unittest
from app import app, db
from models import User, Folder, File
from unittest.mock import patch, MagicMock
from io import BytesIO

class TestCopyValidation(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.app = app.test_client()
        with app.app_context():
            db.create_all()
            user = User(phone='+1234567890', session_string='test')
            db.session.add(user)
            db.session.commit()

            # Create a folder hierarchy
            # root_folder (id='root')
            #   sub_folder (id='sub')
            #     sub_sub_folder (id='subsub')

            root_folder = Folder(id='root', name='Root', user_id=user.id)
            sub_folder = Folder(id='sub', name='Sub', parent_id='root', user_id=user.id)
            sub_sub_folder = Folder(id='subsub', name='SubSub', parent_id='sub', user_id=user.id)

            db.session.add(root_folder)
            db.session.add(sub_folder)
            db.session.add(sub_sub_folder)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    @patch('app.get_current_user_id')
    @patch('app.get_current_manager')
    def test_copy_folder_to_itself(self, mock_get_manager, mock_get_user_id):
        mock_get_user_id.return_value = 1
        mock_get_manager.return_value = MagicMock()

        response = self.app.post('/api/copy', json={
            'items': [{'id': 'root', 'type': 'folder'}],
            'new_parent_id': 'root'
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('Cannot copy folder into itself', response.get_json()['error'])

    @patch('app.get_current_user_id')
    @patch('app.get_current_manager')
    def test_copy_folder_to_its_subfolder(self, mock_get_manager, mock_get_user_id):
        mock_get_user_id.return_value = 1
        mock_get_manager.return_value = MagicMock()

        response = self.app.post('/api/copy', json={
            'items': [{'id': 'root', 'type': 'folder'}],
            'new_parent_id': 'sub'
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('Cannot copy folder into its own subfolder', response.get_json()['error'])

    @patch('app.get_current_user_id')
    @patch('app.get_current_manager')
    def test_copy_folder_to_its_subsubfolder(self, mock_get_manager, mock_get_user_id):
        mock_get_user_id.return_value = 1
        mock_get_manager.return_value = MagicMock()

        response = self.app.post('/api/copy', json={
            'items': [{'id': 'root', 'type': 'folder'}],
            'new_parent_id': 'subsub'
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('Cannot copy folder into its own subfolder', response.get_json()['error'])

    @patch('app.get_current_user_id')
    @patch('app.get_current_manager')
    @patch('app.copy_recursive')
    def test_copy_folder_to_parent(self, mock_copy_recursive, mock_get_manager, mock_get_user_id):
        mock_get_user_id.return_value = 1
        mock_get_manager.return_value = MagicMock()

        response = self.app.post('/api/copy', json={
            'items': [{'id': 'sub', 'type': 'folder'}],
            'new_parent_id': 'root'
        })

        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
