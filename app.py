from flask import Flask, render_template, jsonify
from config import Config
import os

app = Flask(__name__)
app.config.from_object(Config)

# Placeholder for Database setup
# db = SQLAlchemy(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files')
def list_files():
    # Placeholder for file listing logic
    return jsonify([
        {'id': 1, 'name': 'Example File.txt', 'type': 'file', 'size': '12KB'},
        {'id': 2, 'name': 'Photos', 'type': 'folder', 'size': '-'}
    ])

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=port)

