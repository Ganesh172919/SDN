/**
 * auth.js - User Authentication, RBAC & Profile Management for SELF-X Mission Control
 * Supports Admin, Network Operator, Academic Auditor, and Researcher roles.
 */

(function () {
  'use strict';

  const AUTH_STORAGE_KEY = 'selfx_auth_token';

  const ROLE_CONFIG = {
    admin: { label: 'Admin', class: 'role-admin', badge: 'Chief Architect', color: '#ef4444' },
    operator: { label: 'Operator', class: 'role-operator', badge: 'NOC Lead', color: '#f59e0b' },
    researcher: { label: 'Researcher', class: 'role-researcher', badge: 'IIIT Researcher', color: '#00f2fe' },
    auditor: { label: 'Auditor', class: 'role-auditor', badge: 'Peer Auditor', color: '#a855f7' },
    guest: { label: 'Guest', class: 'role-guest', badge: 'Read Only', color: '#94a3b8' }
  };

  const Auth = {
    currentUser: null,
    token: null,

    init() {
      this.token = localStorage.getItem(AUTH_STORAGE_KEY);
      this.bindEvents();
      this.checkSession();
    },

    bindEvents() {
      // Header profile button
      const btnAuth = document.getElementById('btnUserAuth');
      if (btnAuth) {
        btnAuth.addEventListener('click', () => {
          if (this.currentUser) {
            this.showProfileDropdown();
          } else {
            this.openAuthModal('login');
          }
        });
      }

      // Modal close button
      const btnClose = document.getElementById('btnAuthModalClose');
      if (btnClose) {
        btnClose.addEventListener('click', () => this.closeAuthModal());
      }

      // Modal backdrop click
      const modal = document.getElementById('authModalOverlay');
      if (modal) {
        modal.addEventListener('click', (e) => {
          if (e.target === modal) this.closeAuthModal();
        });
      }

      // Tab switcher in auth modal
      const tabLogin = document.getElementById('authTabBtnLogin');
      const tabRegister = document.getElementById('authTabBtnRegister');
      if (tabLogin && tabRegister) {
        tabLogin.addEventListener('click', () => this.switchAuthTab('login'));
        tabRegister.addEventListener('click', () => this.switchAuthTab('register'));
      }

      // Form submissions
      const formLogin = document.getElementById('authLoginForm');
      if (formLogin) {
        formLogin.addEventListener('submit', (e) => {
          e.preventDefault();
          this.handleLoginSubmit();
        });
      }

      const formRegister = document.getElementById('authRegisterForm');
      if (formRegister) {
        formRegister.addEventListener('submit', (e) => {
          e.preventDefault();
          this.handleRegisterSubmit();
        });
      }

      // Quick demo account pills
      document.querySelectorAll('.btn-demo-login').forEach((btn) => {
        btn.addEventListener('click', (e) => {
          const role = e.currentTarget.getAttribute('data-demo-role');
          if (role) this.quickLogin(role);
        });
      });
    },

    async checkSession() {
      try {
        const headers = {};
        if (this.token) {
          headers['Authorization'] = `Bearer ${this.token}`;
        }
        const res = await fetch('/api/auth/me', { headers });
        if (res.ok) {
          const data = await res.json();
          if (data.authenticated && data.user) {
            this.setAuthenticatedUser(data.user, this.token);
            return;
          }
        }
      } catch (err) {
        console.warn('Session check failed:', err);
      }
      this.setGuestUser();
    },

    setAuthenticatedUser(user, token) {
      this.currentUser = user;
      this.token = token;
      if (token) {
        localStorage.setItem(AUTH_STORAGE_KEY, token);
      }
      this.updateUI();
    },

    setGuestUser() {
      this.currentUser = null;
      this.token = null;
      localStorage.removeItem(AUTH_STORAGE_KEY);
      this.updateUI();
    },

    updateUI() {
      const nameEl = document.getElementById('userProfileName');
      const badgeEl = document.getElementById('userRoleBadge');
      const avatarEl = document.getElementById('userAvatarCircle');

      if (!nameEl || !badgeEl) return;

      if (this.currentUser) {
        const role = (this.currentUser.role || 'researcher').toLowerCase();
        const conf = ROLE_CONFIG[role] || ROLE_CONFIG.researcher;
        nameEl.textContent = this.currentUser.display_name || this.currentUser.username;
        badgeEl.textContent = conf.badge;
        badgeEl.className = `role-badge ${conf.class}`;
        if (avatarEl) {
          avatarEl.textContent = (this.currentUser.username || 'U')[0].toUpperCase();
          avatarEl.style.borderColor = conf.color;
        }
      } else {
        nameEl.textContent = 'Sign In';
        badgeEl.textContent = 'Guest';
        badgeEl.className = 'role-badge badge-guest';
        if (avatarEl) {
          avatarEl.textContent = '👤';
          avatarEl.style.borderColor = 'var(--border-card)';
        }
      }
    },

    async handleLoginSubmit() {
      const uInput = document.getElementById('loginUsername');
      const pInput = document.getElementById('loginPassword');
      const msgEl = document.getElementById('authLoginMessage');

      const username = uInput ? uInput.value.trim() : '';
      const password = pInput ? pInput.value.trim() : '';

      if (!username || !password) {
        this.showMessage(msgEl, 'Please enter username and password.', 'error');
        return;
      }

      this.showMessage(msgEl, 'Verifying credentials...', 'info');

      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: jsonSafe({ username, password })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.setAuthenticatedUser(data.user, data.token);
          this.showMessage(msgEl, 'Login successful! Redirecting...', 'success');
          setTimeout(() => this.closeAuthModal(), 600);
        } else {
          this.showMessage(msgEl, data.error || 'Invalid credentials.', 'error');
        }
      } catch (err) {
        this.showMessage(msgEl, 'Network error while contacting authentication bridge.', 'error');
      }
    },

    async handleRegisterSubmit() {
      const uInput = document.getElementById('regUsername');
      const eInput = document.getElementById('regEmail');
      const pInput = document.getElementById('regPassword');
      const rSelect = document.getElementById('regRole');
      const msgEl = document.getElementById('authRegMessage');

      const username = uInput ? uInput.value.trim() : '';
      const email = eInput ? eInput.value.trim() : '';
      const password = pInput ? pInput.value.trim() : '';
      const role = rSelect ? rSelect.value : 'researcher';

      if (!username || !email || !password) {
        this.showMessage(msgEl, 'Please fill in all registration fields.', 'error');
        return;
      }

      this.showMessage(msgEl, 'Registering production account...', 'info');

      try {
        const res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: jsonSafe({ username, email, password, role })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          this.setAuthenticatedUser(data.user, data.token);
          this.showMessage(msgEl, 'Account created! Authenticated as ' + data.user.role, 'success');
          setTimeout(() => this.closeAuthModal(), 600);
        } else {
          this.showMessage(msgEl, data.error || 'Registration failed.', 'error');
        }
      } catch (err) {
        this.showMessage(msgEl, 'Network error during registration.', 'error');
      }
    },

    async quickLogin(role) {
      const token = `demo_token_${role}_2026`;
      try {
        const res = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          if (data.authenticated && data.user) {
            this.setAuthenticatedUser(data.user, token);
            this.closeAuthModal();
            return;
          }
        }
      } catch (err) {
        console.warn('Quick login error:', err);
      }
    },

    async logout() {
      try {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: { Authorization: `Bearer ${this.token || ''}` }
        });
      } catch (e) {}
      this.setGuestUser();
      const dropdown = document.getElementById('userProfileDropdown');
      if (dropdown) dropdown.classList.remove('open');
    },

    openAuthModal(tab = 'login') {
      const modal = document.getElementById('authModalOverlay');
      if (modal) {
        modal.classList.add('open');
        this.switchAuthTab(tab);
      }
    },

    closeAuthModal() {
      const modal = document.getElementById('authModalOverlay');
      if (modal) modal.classList.remove('open');
    },

    switchAuthTab(tab) {
      const tabLogin = document.getElementById('authTabBtnLogin');
      const tabRegister = document.getElementById('authTabBtnRegister');
      const paneLogin = document.getElementById('authPaneLogin');
      const paneRegister = document.getElementById('authPaneRegister');

      if (!tabLogin || !tabRegister || !paneLogin || !paneRegister) return;

      if (tab === 'login') {
        tabLogin.classList.add('active');
        tabRegister.classList.remove('active');
        paneLogin.style.display = 'block';
        paneRegister.style.display = 'none';
      } else {
        tabRegister.classList.add('active');
        tabLogin.classList.remove('active');
        paneRegister.style.display = 'block';
        paneLogin.style.display = 'none';
      }
    },

    showProfileDropdown() {
      let dropdown = document.getElementById('userProfileDropdown');
      if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.id = 'userProfileDropdown';
        dropdown.className = 'user-profile-dropdown';
        document.body.appendChild(dropdown);
      }

      if (dropdown.classList.contains('open')) {
        dropdown.classList.remove('open');
        return;
      }

      const u = this.currentUser || { username: 'Guest', role: 'guest' };
      const role = (u.role || 'guest').toLowerCase();
      const conf = ROLE_CONFIG[role] || ROLE_CONFIG.guest;

      dropdown.innerHTML = `
        <div class="dropdown-header">
          <div class="dropdown-user-title">${u.display_name || u.username}</div>
          <div class="dropdown-user-sub">${u.email || 'No email attached'}</div>
          <span class="role-badge ${conf.class}" style="margin-top:6px; display:inline-block;">${conf.badge}</span>
        </div>
        <div class="dropdown-body">
          <div class="dropdown-item"><strong>Permissions:</strong> ${(u.permissions || ['read_only']).join(', ')}</div>
          <div class="dropdown-item"><strong>Session Status:</strong> <span style="color:#10b981;">Active Secure Token</span></div>
        </div>
        <div class="dropdown-footer">
          <button type="button" class="btn-ctrl" id="btnSwitchAccount" style="width:100%; margin-bottom:6px;">Switch Account</button>
          <button type="button" class="btn-ctrl btn-logout" id="btnLogoutSession" style="width:100%; color:#ef4444; border-color:rgba(239,68,68,0.4);">Sign Out</button>
        </div>
      `;

      // Position relative to profile button
      const btn = document.getElementById('btnUserAuth');
      if (btn) {
        const rect = btn.getBoundingClientRect();
        dropdown.style.top = `${rect.bottom + 8}px`;
        dropdown.style.right = `${window.innerWidth - rect.right}px`;
      }

      dropdown.classList.add('open');

      document.getElementById('btnLogoutSession')?.addEventListener('click', () => this.logout());
      document.getElementById('btnSwitchAccount')?.addEventListener('click', () => {
        dropdown.classList.remove('open');
        this.openAuthModal('login');
      });

      // Auto-close on click outside
      const closeHandler = (e) => {
        if (!dropdown.contains(e.target) && (!btn || !btn.contains(e.target))) {
          dropdown.classList.remove('open');
          document.removeEventListener('click', closeHandler);
        }
      };
      setTimeout(() => document.addEventListener('click', closeHandler), 10);
    },

    showMessage(el, text, type) {
      if (!el) return;
      el.textContent = text;
      el.className = `auth-message ${type}`;
      el.style.display = 'block';
    }
  };

  function jsonSafe(obj) {
    return JSON.stringify(obj);
  }

  window.Auth = Auth;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => Auth.init());
  } else {
    Auth.init();
  }
})();
