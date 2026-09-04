"""A deterministic browser-only app used to exercise authenticated journeys safely."""

from __future__ import annotations

import json
from dataclasses import dataclass

from playwright.sync_api import Page, Route

from ai_qa_engineering.auth import LoginForm
from ai_qa_engineering.navigation import navigate_or_incomplete
from ai_qa_engineering.secrets import ResolvedCredentials

SANDBOX_ACCOUNTS = {
    "member@example.test": {"password": "member-pass", "role": "member", "locked": False},
    "admin@example.test": {"password": "admin-pass", "role": "admin", "locked": False},
    "locked@example.test": {"password": "locked-pass", "role": "member", "locked": True},
}


def _document(body: str, script: str) -> str:
    accounts = json.dumps(SANDBOX_ACCOUNTS)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Controlled Auth Sandbox</title>
  <style>
    body {{ font: 16px Arial, sans-serif; max-width: 680px; margin: 48px auto; padding: 20px; }}
    form {{ display: grid; gap: 12px; max-width: 360px; }}
    label {{ display: grid; gap: 5px; }}
    input, button {{ font: inherit; padding: 10px; }}
    [role="alert"] {{ color: #9c2e20; font-weight: 700; }}
  </style>
</head>
<body><main>{body}</main>
<script>
const accounts = {accounts};
const readSession = () => {{
  try {{ return JSON.parse(localStorage.getItem('auth-session')); }} catch {{ return null; }}
}};
const activeSession = () => {{
  const session = readSession();
  return session && session.expiresAt > Date.now() ? session : null;
}};
{script}
</script></body></html>"""


def _login_page() -> str:
    body = """
      <h1>Sign in</h1>
      <p id="notice" role="alert"></p>
      <form id="login-form">
        <label>Email <input id="username" autocomplete="username"></label>
        <label>
          Password
          <input id="password" type="password" autocomplete="current-password">
        </label>
        <button id="sign-in" type="submit">Sign in</button>
      </form>
      <a href="/recover" id="recover-link">Forgot password?</a>
    """
    script = """
      const reason = new URLSearchParams(location.search).get('reason');
      if (reason === 'expired') document.querySelector('#notice').textContent = 'Session expired';
      if (reason === 'logout') document.querySelector('#notice').textContent = 'Signed out';
      document.querySelector('#login-form').addEventListener('submit', event => {
        event.preventDefault();
        const username = document.querySelector('#username').value;
        const password = document.querySelector('#password').value;
        const account = accounts[username];
        if (!account || account.password !== password) {
          document.querySelector('#notice').textContent = 'Invalid credentials';
          return;
        }
        if (account.locked) {
          document.querySelector('#notice').textContent = 'Account locked';
          return;
        }
        localStorage.setItem('auth-session', JSON.stringify({
          email: username, role: account.role, expiresAt: Date.now() + 3600000
        }));
        location.href = '/dashboard';
      });
    """
    return _document(body, script)


def _dashboard_page() -> str:
    body = """
      <section id="dashboard" hidden>
        <h1>Account dashboard</h1>
        <p>Signed in as <span id="identity"></span></p>
        <p>Role: <strong id="role"></strong></p>
        <a href="/admin" id="admin-link">Admin area</a>
        <button id="expire-session">Expire session</button>
        <button id="logout">Sign out</button>
      </section>
    """
    script = """
      const session = activeSession();
      if (!session) {
        localStorage.removeItem('auth-session');
        location.replace('/login?reason=expired');
      } else {
        document.querySelector('#identity').textContent = session.email;
        document.querySelector('#role').textContent = session.role;
        document.querySelector('#dashboard').hidden = false;
        document.querySelector('#logout').addEventListener('click', () => {
          localStorage.removeItem('auth-session');
          location.href = '/login?reason=logout';
        });
        document.querySelector('#expire-session').addEventListener('click', () => {
          session.expiresAt = 0;
          localStorage.setItem('auth-session', JSON.stringify(session));
          location.href = '/dashboard';
        });
      }
    """
    return _document(body, script)


def _admin_page() -> str:
    body = '<section id="admin-result"></section>'
    script = """
      const session = activeSession();
      const result = document.querySelector('#admin-result');
      if (!session) {
        location.replace('/login?reason=expired');
      } else if (session.role !== 'admin') {
        result.innerHTML = '<h1>Access denied</h1><p>Administrator role required</p>';
      } else {
        result.innerHTML = '<h1>Admin area</h1><p>Authorized administrator</p>';
      }
    """
    return _document(body, script)


def _recovery_page() -> str:
    body = """
      <h1>Recover access</h1>
      <form id="recovery-form">
        <label>Email <input id="recovery-email"></label>
        <button type="submit">Request recovery</button>
      </form>
      <p id="recovery-result" role="status"></p>
      <a href="/login">Return to sign in</a>
    """
    script = """
      document.querySelector('#recovery-form').addEventListener('submit', event => {
        event.preventDefault();
        document.querySelector('#recovery-result').textContent =
          'If the account exists, recovery instructions will be sent.';
      });
    """
    return _document(body, script)


@dataclass
class AuthSandboxApp:
    page: Page
    base_url: str

    @property
    def origin(self) -> str:
        return self.base_url.rstrip("/")

    def install(self) -> None:
        self.page.route(f"{self.origin}/**", self._route)

    def _route(self, route: Route) -> None:
        path = route.request.url.removeprefix(self.origin).split("?", maxsplit=1)[0]
        pages = {
            "": _login_page,
            "/": _login_page,
            "/login": _login_page,
            "/dashboard": _dashboard_page,
            "/admin": _admin_page,
            "/recover": _recovery_page,
        }
        renderer = pages.get(path)
        if renderer is None:
            route.fulfill(status=404, content_type="text/html", body="<h1>Not found</h1>")
            return
        route.fulfill(status=200, content_type="text/html", body=renderer())

    def open(self, path: str) -> None:
        navigate_or_incomplete(self.page, f"{self.origin}{path}")

    def open_login(self) -> None:
        self.open("/login")

    def login(self, credentials: ResolvedCredentials) -> None:
        LoginForm(self.page, "#username", "#password", "#sign-in").submit(credentials)

    def login_values(self, username: str, password: str) -> None:
        self.page.locator("#username").fill(username)
        self.page.locator("#password").fill(password)
        self.page.locator("#sign-in").click()

    def open_dashboard(self) -> None:
        self.open("/dashboard")

    def open_admin(self) -> None:
        self.open("/admin")

    def logout(self) -> None:
        self.page.locator("#logout").click()

    def expire_session(self) -> None:
        self.page.locator("#expire-session").click()

    def request_recovery(self, email: str) -> str:
        self.open("/recover")
        self.page.locator("#recovery-email").fill(email)
        self.page.get_by_role("button", name="Request recovery").click()
        return self.page.locator("#recovery-result").inner_text()
