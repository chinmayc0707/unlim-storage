import re

with open('static/js/app.js', 'r') as f:
    content = f.read()

# Fix download folder to not cause full reload in unexpected ways
# Actually `window.location.href = ...` for download does not reload the page typically because it responds with Content-Disposition: attachment
# But in `downloadFolders`, if it fails or if the headers are wrong, it might be an issue.
# Let's check app.py headers for `download_folders`
