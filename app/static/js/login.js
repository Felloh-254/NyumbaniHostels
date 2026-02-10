function createParticles() {
    for (let i = 0; i < 20; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 15 + 's';
        particle.style.animationDuration = (Math.random() * 10 + 10) + 's';
        document.body.appendChild(particle);
    }
}
createParticles();

class LoginForm {
    constructor() {
        this.form = document.getElementById('loginForm');
        this.init();
    }

    init() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        
        const inputs = this.form.querySelectorAll('input');
        inputs.forEach(input => {
            input.addEventListener('blur', () => this.validateField(input));
            input.addEventListener('input', () => this.clearError(input));
        });

        // Password visibility toggle
        document.getElementById('togglePassword').addEventListener('click', () => this.togglePasswordVisibility());
    }

    togglePasswordVisibility() {
        const passwordInput = document.getElementById('password');
        const toggleButton = document.getElementById('togglePassword');
        
        if (passwordInput.type === 'password') {
            passwordInput.type = 'text';
            toggleButton.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M17.94 17.94C16.2306 19.243 14.1491 19.9649 12 20C5 20 1 12 1 12C2.24389 9.68192 3.96914 7.65663 6.06 6.06M9.9 4.24C10.5883 4.0789 11.2931 3.99836 12 4C19 4 23 12 23 12C22.393 13.1356 21.6691 14.2048 20.84 15.19M14.12 14.12C13.8454 14.4148 13.5141 14.6512 13.1462 14.8151C12.7782 14.9791 12.3809 15.0673 11.9781 15.0744C11.5753 15.0815 11.1752 15.0074 10.8016 14.8565C10.4281 14.7056 10.0887 14.4811 9.80385 14.1962C9.51897 13.9113 9.29439 13.5719 9.14351 13.1984C8.99262 12.8249 8.91853 12.4247 8.92563 12.0219C8.93274 11.6191 9.02091 11.2219 9.18488 10.8539C9.34884 10.4859 9.58525 10.1547 9.88 9.88" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M1 1L23 23" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            `;
        } else {
            passwordInput.type = 'password';
            toggleButton.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M1 12C1 12 5 4 12 4C19 4 23 12 23 12C23 12 19 20 12 20C5 20 1 12 1 12Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            `;
        }
    }

    validateField(field) {
        const value = field.value.trim();
        const fieldName = field.name;

        switch (fieldName) {
            case 'email':
                return this.validateEmail(field, value);
            case 'password':
                return this.validatePassword(field, value);
        }
        return true;
    }

    validateEmail(field, value) {
        if (!value) {
            this.showError(field, 'Email is required');
            return false;
        }
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
            this.showError(field, 'Please enter a valid email address');
            return false;
        }
        this.clearError(field);
        return true;
    }

    validatePassword(field, value) {
        if (!value) {
            this.showError(field, 'Password is required');
            return false;
        }
        if (value.length < 6) {
            this.showError(field, 'Password must be at least 6 characters long');
            return false;
        }
        this.clearError(field);
        return true;
    }

    showError(field, message) {
        field.classList.add('error');
        const errorElement = document.getElementById(field.name + 'Error');
        if (errorElement) {
            errorElement.textContent = message;
        }
    }

    clearError(field) {
        field.classList.remove('error');
        const errorElement = document.getElementById(field.name + 'Error');
        if (errorElement) {
            errorElement.textContent = '';
        }
    }

    async handleSubmit(e) {
        e.preventDefault();
        
        // Validate all fields
        let isValid = true;
        const emailField = document.getElementById('email');
        const passwordField = document.getElementById('password');
        
        if (!this.validateField(emailField)) isValid = false;
        if (!this.validateField(passwordField)) isValid = false;
        
        if (!isValid) return;

        this.setLoading(true);

        try {
            const formData = this.getFormData();
            await this.submitForm(formData);
        } catch (error) {
            this.showMessage('An error occurred. Please try again.', 'error');
            console.error('Login error:', error);
        } finally {
            this.setLoading(false);
        }
    }

    getFormData() {
        return {
            email: document.getElementById('email').value.trim(),
            password: document.getElementById('password').value,
            remember: document.getElementById('remember').checked
        };
    }

    async submitForm(formData) {
        const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok) {
            this.showMessage('Login successful! Redirecting...', 'success');
            setTimeout(() => {
                window.location.href = data.redirect_url;
            }, 1500);
        } else {
            this.showMessage(data.message || 'Login failed. Please check your credentials.', 'error');
        }
    }

    setLoading(loading) {
        const loginBtn = document.getElementById('loginBtn');
        if (loading) {
            loginBtn.disabled = true;
            loginBtn.classList.add('loading');
        } else {
            loginBtn.disabled = false;
            loginBtn.classList.remove('loading');
        }
    }

    showMessage(message, type) {
        const existingMessage = document.querySelector('.success-message, .error-message-global');
        if (existingMessage && existingMessage.parentNode === this.form) {
            existingMessage.remove();
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = type === 'success' ? 'success-message' : 'error-message-global';
        messageDiv.textContent = message;

        this.form.insertBefore(messageDiv, this.form.firstChild);

        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 5000);
    }
}