with open('static/js/login.js', 'r') as f:
    content = f.read()

# Fix login function because the form isn't getting correctly submitted or the button click isn't doing the right thing. Wait!
# Is it `window.location.href = '/'`? Let me see why `page.url` was `http://localhost:5000/login#`.
# The `Create Account` link was `<a href="#" onclick="showRegister()">` which added `#` to the URL.
# Let's fix login.js or test script
pass
