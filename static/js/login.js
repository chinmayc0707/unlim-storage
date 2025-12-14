async function sendCode() {
    const phone = document.getElementById('phone-input').value;
    const errorDiv = document.getElementById('login-error');
    const btn = document.querySelector('#step-phone button');

    if (!phone) {
        errorDiv.textContent = 'Please enter a phone number';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Sending...';
    errorDiv.textContent = '';

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone })
        });

        const data = await response.json();
        if (response.ok) {
            document.getElementById('step-phone').style.display = 'none';
            document.getElementById('step-code').style.display = 'block';
            document.getElementById('code-input').focus();
        } else {
            errorDiv.textContent = data.error || 'Failed to send code';
        }
    } catch (error) {
        errorDiv.textContent = 'Network error. Please check your connection.';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Send Code';
    }
}

async function verifyCode() {
    const code = document.getElementById('code-input').value;
    const errorDiv = document.getElementById('login-error');
    const btn = document.querySelector('#step-code button');

    if (!code) {
        errorDiv.textContent = 'Please enter the code';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Verifying...';
    errorDiv.textContent = '';

    try {
        const response = await fetch('/api/auth/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code })
        });

        const data = await response.json();
        if (response.ok) {
            window.location.href = '/';
        } else if (response.status === 401 && data.status === 'password_required') {
            document.getElementById('step-code').style.display = 'none';
            document.getElementById('step-password').style.display = 'block';
            document.getElementById('password-input').focus();
        } else {
            errorDiv.textContent = data.error || 'Invalid code';
        }
    } catch (error) {
        errorDiv.textContent = 'Network error';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Verify';
    }
}

async function verifyPassword() {
    const code = document.getElementById('code-input').value;
    const password = document.getElementById('password-input').value;
    const errorDiv = document.getElementById('login-error');
    const btn = document.querySelector('#step-password button');

    btn.disabled = true;
    btn.textContent = 'Logging in...';
    errorDiv.textContent = '';

    try {
        const response = await fetch('/api/auth/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, password })
        });

        const data = await response.json();
        if (response.ok) {
            window.location.href = '/';
        } else {
            errorDiv.textContent = data.error || 'Invalid password';
        }
    } catch (error) {
        errorDiv.textContent = 'Network error';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Login';
    }
}

// Enter key support
document.getElementById('phone-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendCode();
});
document.getElementById('code-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') verifyCode();
});
document.getElementById('password-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') verifyPassword();
});
