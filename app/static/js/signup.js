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

class SignupForm {
    constructor() {
        this.form = document.getElementById('signupForm');
        this.currentStep = 1;
        this.totalSteps = 4;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupPasswordValidation();
        this.updateProgress();
    }

    setupEventListeners() {
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        
        const inputs = this.form.querySelectorAll('input, select');
        inputs.forEach(input => {
            input.addEventListener('blur', () => this.validateField(input));
            input.addEventListener('input', () => this.clearError(input));
            
            // Add Enter key navigation
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.handleEnterKey(input);
                }
            });
        });

        const password = document.getElementById('password');
        const confirmPassword = document.getElementById('confirmPassword');
        
        password.addEventListener('input', () => {
            this.validatePassword();
            if (confirmPassword.value) {
                this.validateConfirmPassword();
            }
        });
        
        confirmPassword.addEventListener('input', () => this.validateConfirmPassword());

        // Navigation buttons
        document.getElementById('nextBtn1').addEventListener('click', () => this.nextStep(1));
        document.getElementById('nextBtn2').addEventListener('click', () => this.nextStep(2));
        document.getElementById('nextBtn3').addEventListener('click', () => this.nextStep(3));
        
        document.getElementById('prevBtn2').addEventListener('click', () => this.prevStep());
        document.getElementById('prevBtn3').addEventListener('click', () => this.prevStep());
        document.getElementById('prevBtn4').addEventListener('click', () => this.prevStep());
    }

    handleEnterKey(input) {
        const step = this.currentStep;
        if (step < this.totalSteps) {
            this.nextStep(step);
        } else if (step === this.totalSteps) {
            this.form.dispatchEvent(new Event('submit'));
        }
    }

    setupPasswordValidation() {
        const passwordInput = document.getElementById('password');
        passwordInput.addEventListener('input', () => this.updatePasswordRequirements());
    }

    updatePasswordRequirements() {
        const password = document.getElementById('password').value;
        
        const requirements = {
            'req-length': password.length >= 8,
            'req-uppercase': /[A-Z]/.test(password),
            'req-lowercase': /[a-z]/.test(password),
            'req-number': /[0-9]/.test(password),
            'req-special': /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)
        };

        Object.entries(requirements).forEach(([id, isValid]) => {
            const element = document.getElementById(id);
            element.classList.toggle('valid', isValid);
        });
    }

    validateStepFields(step) {
        let fieldsToValidate = [];
        
        switch(step) {
            case 1:
                fieldsToValidate = ['firstName', 'lastName', 'gender'];
                break;
            case 2:
                fieldsToValidate = ['email', 'phone'];
                break;
            case 3:
                fieldsToValidate = ['studentId', 'emergencyContact'];
                break;
            case 4:
                fieldsToValidate = ['password', 'confirmPassword'];
                break;
        }

        let isValid = true;
        fieldsToValidate.forEach(fieldName => {
            const field = document.getElementById(fieldName);
            if (field && (field.hasAttribute('required') || field.value)) {
                if (!this.validateField(field)) {
                    isValid = false;
                }
            }
        });

        return isValid;
    }

    nextStep(currentStep) {
        if (!this.validateStepFields(currentStep)) {
            return;
        }

        if (this.currentStep < this.totalSteps) {
            this.currentStep++;
            this.updateStepDisplay();
            this.updateProgress();
        }
    }

    prevStep() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.updateStepDisplay();
            this.updateProgress();
        }
    }

    updateStepDisplay() {
        document.querySelectorAll('.form-step').forEach(step => {
            step.classList.remove('active');
        });
        document.querySelector(`.form-step[data-step="${this.currentStep}"]`).classList.add('active');

        document.querySelectorAll('.step-indicator').forEach((indicator, index) => {
            indicator.classList.remove('active', 'completed');
            if (index + 1 === this.currentStep) {
                indicator.classList.add('active');
            } else if (index + 1 < this.currentStep) {
                indicator.classList.add('completed');
            }
        });
    }

    updateProgress() {
        const progress = (this.currentStep / this.totalSteps) * 100;
        document.getElementById('progressFill').style.width = progress + '%';
    }

    validateField(field) {
        const value = field.value.trim();
        const fieldName = field.name;

        switch (fieldName) {
            case 'firstName':
            case 'lastName':
                return this.validateName(field, value);
            case 'email':
                return this.validateEmail(field, value);
            case 'phone':
                return this.validatePhone(field, value);
            case 'studentId':
                return this.validateStudentId(field, value);
            case 'emergencyContact':
                return this.validateEmergencyContact(field, value);
            case 'password':
                return this.validatePassword(field, value);
            case 'confirmPassword':
                return this.validateConfirmPassword(field, value);
            case 'gender':
                return this.validateGender(field, value);
        }
        return true;
    }

    validateName(field, value) {
        if (!value) {
            this.showError(field, 'This field is required');
            return false;
        }
        if (value.length < 2) {
            this.showError(field, 'Name must be at least 2 characters long');
            return false;
        }
        if (!/^[a-zA-Z\s\-']+$/.test(value)) {
            this.showError(field, 'Name can only contain letters, spaces, hyphens, and apostrophes');
            return false;
        }
        this.clearError(field);
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

    validatePhone(field, value) {
        if (value && !/^\+?[\d\s\-\(\)]{10,}$/.test(value)) {
            this.showError(field, 'Please enter a valid phone number');
            return false;
        }
        this.clearError(field);
        return true;
    }

    validateStudentId(field, value) {
        if (!value) {
            this.showError(field, 'Student ID is required');
            return false;
        }
        if (value.length < 3) {
            this.showError(field, 'Student ID must be at least 3 characters long');
            return false;
        }
        this.clearError(field);
        return true;
    }

    validateEmergencyContact(field, value) {
        if (value && !/^\+?[\d\s\-\(\)]{10,}$/.test(value)) {
            this.showError(field, 'Please enter a valid emergency contact number');
            return false;
        }
        this.clearError(field);
        return true;
    }

    validatePassword(field = null, value = null) {
        const passwordField = field || document.getElementById('password');
        const password = value || passwordField.value;

        if (!password) {
            if (field) this.showError(field, 'Password is required');
            return false;
        }

        const requirements = {
            length: password.length >= 8,
            uppercase: /[A-Z]/.test(password),
            lowercase: /[a-z]/.test(password),
            number: /[0-9]/.test(password),
            special: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)
        };

        if (!Object.values(requirements).every(req => req)) {
            if (field) this.showError(field, 'Password does not meet all requirements');
            return false;
        }

        if (field) this.clearError(field);
        return true;
    }

    validateConfirmPassword(field = null, value = null) {
        const confirmField = field || document.getElementById('confirmPassword');
        const confirmPassword = value || confirmField.value;
        const password = document.getElementById('password').value;

        if (!confirmPassword) {
            if (field) this.showError(field, 'Please confirm your password');
            return false;
        }

        if (confirmPassword !== password) {
            if (field) this.showError(field, 'Passwords do not match');
            return false;
        }

        if (field) this.clearError(field);
        return true;
    }

    validateGender(field, value) {
        if (!value) {
            this.showError(field, 'Please select your gender');
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
        
        // Validate all steps before submission
        for (let step = 1; step <= this.totalSteps; step++) {
            if (!this.validateStepFields(step)) {
                this.currentStep = step;
                this.updateStepDisplay();
                this.updateProgress();
                return;
            }
        }

        const terms = document.getElementById('terms');
        if (!terms.checked) {
            this.showError(terms, 'You must agree to the terms and conditions');
            return;
        }

        this.setLoading(true);

        try {
            const formData = this.getFormData();
            await this.submitForm(formData);
        } catch (error) {
            this.showMessage('An error occurred. Please try again.', 'error');
            console.error('Signup error:', error);
        } finally {
            this.setLoading(false);
        }
    }

    getFormData() {
        return {
            firstName: document.getElementById('firstName').value.trim(),
            lastName: document.getElementById('lastName').value.trim(),
            email: document.getElementById('email').value.trim(),
            phone: document.getElementById('phone').value.trim() || null,
            gender: document.getElementById('gender').value,
            studentId: document.getElementById('studentId').value.trim(),
            emergencyContact: document.getElementById('emergencyContact').value.trim() || null,
            password: document.getElementById('password').value,
            role: 'student'
        };
    }

    async submitForm(formData) {
        const response = await fetch('/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok) {
            this.showMessage(data.message || 'Account created successfully! Redirecting...', 'success');
            setTimeout(() => {
                window.location.href = '/login';
            }, 2000);
        } else {
            this.showMessage(data.message || 'Signup failed. Please try again.', 'error');
        }
    }

    setLoading(loading) {
        const submitBtn = document.getElementById('submitBtn');
        if (loading) {
            submitBtn.disabled = true;
            submitBtn.classList.add('loading');
        } else {
            submitBtn.disabled = false;
            submitBtn.classList.remove('loading');
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

        const activeStep = document.querySelector('.form-step.active');
        activeStep.insertBefore(messageDiv, activeStep.firstChild);

        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 5000);
    }
}
