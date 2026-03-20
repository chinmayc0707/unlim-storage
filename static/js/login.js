function showRegister() {
    document.getElementById('step-login').style.display = 'none';
    document.getElementById('step-register').style.display = 'block';
    document.getElementById('login-error').textContent = '';
}

function showLogin() {
    document.getElementById('step-register').style.display = 'none';
    document.getElementById('step-login').style.display = 'block';
    document.getElementById('login-error').textContent = '';
}

async function loginUser() {
    const phone = document.getElementById('phone-input').value;
    const password = document.getElementById('password-input').value;
    const errorDiv = document.getElementById('login-error');
    const btn = document.querySelector('#step-login button');

    if (!phone || !password) {
        errorDiv.textContent = 'Please enter phone and password';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Logging in...';
    errorDiv.textContent = '';

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, password })
        });

        const data = await response.json();
        if (response.ok && data.token) {
            localStorage.setItem('jwt_token', data.token);
            window.location.href = '/';
        } else {
            errorDiv.textContent = data.error || 'Login failed';
        }
    } catch (error) {
        errorDiv.textContent = 'Network error. Please check your connection.';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Login';
    }
}

async function registerUser() {
    const phone = document.getElementById('reg-phone-input').value;
    const password = document.getElementById('reg-password-input').value;
    const errorDiv = document.getElementById('login-error');
    const btn = document.querySelector('#step-register button');

    if (!phone || !password) {
        errorDiv.textContent = 'Please enter phone and password';
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Registering...';
    errorDiv.textContent = '';

    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, password })
        });

        const data = await response.json();
        if (response.ok) {
            showLogin();
            document.getElementById('phone-input').value = phone;
            document.getElementById('password-input').value = '';
            errorDiv.textContent = 'Registration successful. Please login.';
            errorDiv.style.color = 'green';
        } else {
            errorDiv.textContent = data.error || 'Registration failed';
            errorDiv.style.color = 'red';
        }
    } catch (error) {
        errorDiv.textContent = 'Network error. Please check your connection.';
    } finally {
        btn.disabled = false;
        btn.textContent = 'Register';
    }
}

document.getElementById('password-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') loginUser();
});
document.getElementById('reg-password-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') registerUser();
});
