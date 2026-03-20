import re

with open('static/js/app.js', 'r') as f:
    content = f.read()

# Add a fetch wrapper at the top
wrapper = """
const originalFetch = window.fetch;
window.fetch = async function() {
    let [resource, config] = arguments;
    if (!config) {
        config = {};
    }
    if (!config.headers) {
        config.headers = {};
    }
    const token = localStorage.getItem('jwt_token');
    if (token) {
        config.headers['Authorization'] = `Bearer ${token}`;
    }
    return originalFetch(resource, config);
};
"""

content = wrapper + content

# Fix download link appending token
content = content.replace("window.location.href = `/api/download/${contextMenuItem.id}`;", "window.location.href = `/api/download/${contextMenuItem.id}?token=${localStorage.getItem('jwt_token')}`;")

# Fix XHR upload headers
xhr_open = "xhr.open('POST', '/api/upload');"
xhr_header = "xhr.open('POST', '/api/upload');\n    const token = localStorage.getItem('jwt_token');\n    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);"
content = content.replace(xhr_open, xhr_header)

with open('static/js/app.js', 'w') as f:
    f.write(content)
