import re

with open('static/js/app.js', 'r') as f:
    content = f.read()

# Helper to inject headers
fetch_regex = r"fetch\(`?(/[a-zA-Z0-9_/?&=]+)`?(?:,\s*\{([^}]*)\})?\)"

def replacer(match):
    url = match.group(1)
    opts = match.group(2)

    # Keep original url mapping, but inject token logic
    if opts is None:
        opts = "headers: { 'Authorization': `Bearer ${localStorage.getItem('jwt_token')}` }"
    else:
        # Check if headers exist
        if "headers:" in opts:
            opts = re.sub(r"headers:\s*\{", "headers: { 'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`, ", opts)
        else:
            opts = opts.strip() + ", headers: { 'Authorization': `Bearer ${localStorage.getItem('jwt_token')}` }"

    # For file uploads, we use XMLHttpRequest, not fetch
    return f"fetch(`{url}`, {{{opts}}})"

# Using re.sub with function is tricky for template literals.
# Instead, I'll just write a JS wrapper function and replace all fetch calls.
