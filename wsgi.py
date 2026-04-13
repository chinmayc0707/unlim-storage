import os
from app import app
from waitress import serve

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting server on http://0.0.0.0:{port}")
    serve(app, host="0.0.0.0", port=port)
