# Telegram Cloud Storage

A web-based file storage application that leverages Telegram's infrastructure as a free, unlimited backend storage provider. This project features a user interface inspired by Google Drive, allowing users to upload, organize, download, and manage files seamlessly.

## Features

*   **Google Drive-like UI:** Familiar and intuitive interface with grid and list views for easy file and folder management.
*   **Unlimited Backend Storage:** Uses Telegram's servers (via the Telethon library) to store files indefinitely.
*   **Large File Support:** Employs parallel `fast_upload` with 4 concurrent workers and 512KB chunks to handle files larger than 10MB efficiently.
*   **Folder Uploads:** Drag-and-drop or select entire folders; the application automatically reconstructs the directory structure in the cloud.
*   **File Management:** Create folders, rename, move, copy, and delete files or entire directory trees.
*   **User Authentication:** Secure login using your Telegram phone number and authentication code.
*   **Session Isolation:** Supports multiple users simultaneously, each with their own isolated Telegram session.
*   **Storage Metrics:** Calculates and displays your total storage usage.

## Architecture

*   **Backend:** Python 3, Flask, Flask-SQLAlchemy
*   **Telegram Integration:** Telethon
*   **Database:** PostgreSQL (production/Render) or SQLite (in-memory fallback for local development)
*   **Frontend:** Vanilla JavaScript, HTML5, CSS3
*   **WSGI Server:** Waitress (for production deployment)

### How it Works

When you upload a file, the backend splits it into chunks (if it exceeds Telegram's standard limits) and sends these chunks as document messages to your Telegram "Saved Messages" (`"me"` chat). The application's database stores essential metadata—such as the filename, MIME type, size, and the corresponding Telegram message IDs. When you request a download, the backend retrieves these message IDs from Telegram, reassembles the file, and serves it to your browser.

## Setup and Installation

### Prerequisites

*   Python 3.8+
*   A Telegram Developer API ID and Hash (obtainable from [my.telegram.org](https://my.telegram.org))

### Local Development

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Variables:**
    Create a `.env` file in the root directory and add the following:
    ```env
    SECRET_KEY=your_secure_random_string
    API_ID=your_telegram_api_id
    API_HASH=your_telegram_api_hash
    # Optional: Chat ID to store files (defaults to "me" / Saved Messages)
    STORAGE_CHAT_ID=me
    # Optional: Database URL. If omitted, an in-memory SQLite DB is used.
    # DATABASE_URL=postgresql://user:password@host:port/dbname
    ```

4.  **Run the application:**
    ```bash
    python3 app.py
    ```
    The application will be available at `http://localhost:5000`.

### Production Deployment (e.g., Render)

The project includes a `wsgi.py` file configured to use Waitress for production deployments.

1.  Set the environment variables listed above in your hosting provider's dashboard. Ensure `DATABASE_URL` is set to a persistent PostgreSQL instance.
2.  Use the following start command:
    ```bash
    waitress-serve --port=$PORT wsgi:app
    ```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
