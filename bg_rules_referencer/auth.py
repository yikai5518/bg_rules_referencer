import os
from collections.abc import Mapping
from typing import Any

import streamlit as st


def get_auth_config() -> dict[str, Any]:
    """Safely retrieves the [auth] dictionary from Streamlit secrets."""
    try:
        if "auth" in st.secrets:
            return dict(st.secrets["auth"])
    except Exception:
        pass
    return {}


def get_allowed_emails() -> set[str]:
    """Retrieves the set of authorized emails from Streamlit secrets or environment variables."""
    emails: set[str] = set()

    # 1. From st.secrets
    try:
        # Check top-level allowed_emails
        if "allowed_emails" in st.secrets:
            items = st.secrets["allowed_emails"]
            if isinstance(items, (list, tuple, set)):
                emails.update(str(e).strip().lower() for e in items if e)
            elif isinstance(items, str):
                emails.update(e.strip().lower() for e in items.split(",") if e.strip())

        # Check [auth.allowed_emails]
        auth_conf = st.secrets.get("auth", {})
        if isinstance(auth_conf, Mapping) and "allowed_emails" in auth_conf:
            items = auth_conf["allowed_emails"]
            if isinstance(items, (list, tuple, set)):
                emails.update(str(e).strip().lower() for e in items if e)
            elif isinstance(items, str):
                emails.update(e.strip().lower() for e in items.split(",") if e.strip())
    except Exception:
        pass

    # 2. From environment variables (ALLOWED_EMAILS or WHITELISTED_EMAILS)
    env_str = os.getenv("ALLOWED_EMAILS") or os.getenv("WHITELISTED_EMAILS") or ""
    if env_str:
        emails.update(e.strip().lower() for e in env_str.split(",") if e.strip())

    return emails


def is_auth_configured() -> bool:
    """Checks whether Google OAuth has been configured in Streamlit secrets."""
    auth_conf = get_auth_config()
    client_id = auth_conf.get("client_id", "")
    client_secret = auth_conf.get("client_secret", "")

    # Ensure not empty and not an unfilled placeholder
    return bool(
        client_id
        and client_secret
        and "YOUR_GOOGLE_CLIENT_ID" not in client_id
        and "YOUR_GOOGLE_CLIENT_SECRET" not in client_secret
    )


def require_auth() -> bool:
    """Enforces Google OAuth login and email whitelisting.

    Halts execution via st.stop() if:
      - Auth is not configured (shows configuration instructions)
      - User is not logged in (shows Google Sign-In prompt)
      - User is logged in but their email is not in the whitelist (shows Access Denied)

    Returns:
      True if the current user is authenticated and authorized.
    """
    if not is_auth_configured():
        _render_unconfigured_screen()
        st.stop()

    # Check login status using Streamlit native st.user
    is_logged_in = getattr(st.user, "is_logged_in", False)
    if not is_logged_in:
        _render_login_screen()
        st.stop()

    # Verify email against whitelist
    user_email = (getattr(st.user, "email", None) or "").strip().lower()
    allowed = get_allowed_emails()

    if allowed and user_email not in allowed:
        _render_access_denied_screen(user_email)
        st.stop()

    return True


def render_user_badge() -> None:
    """Renders user info and a sign-out button in the sidebar."""
    if not getattr(st.user, "is_logged_in", False):
        return

    name = getattr(st.user, "name", None) or "User"
    email = getattr(st.user, "email", None) or ""

    st.sidebar.markdown("---")
    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        st.caption(f"👤 Signed in as **{name}**\n`{email}`")
    with col2:
        if st.button(
            "🚪 Logout", key="auth_logout_btn", help="Sign out of your account"
        ):
            st.logout()


def _render_unconfigured_screen() -> None:
    """Renders a friendly setup card when OAuth secrets are missing."""
    st.markdown(
        """
        <div style="max-width: 680px; margin: 3rem auto; padding: 2rem; border-radius: 14px;
                    background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(139, 92, 246, 0.3);">
            <h2 style="margin-top: 0; color: #a855f7;">🔒 Authentication Required</h2>
            <p style="color: #cbd5e1; font-size: 0.95rem;">
                This app is protected by Google Account OAuth to safeguard your API key.
                Google OAuth credentials have not been configured yet.
            </p>
            <hr style="border: 0; border-top: 1px solid rgba(255, 255, 255, 0.1); margin: 1.5rem 0;" />
            <h4 style="color: #e2e8f0; margin-bottom: 0.5rem;">Quick Setup Steps:</h4>
            <ol style="color: #94a3b8; font-size: 0.9rem; line-height: 1.6; padding-left: 1.2rem;">
                <li>Create an OAuth 2.0 Web Client ID in the
                    <a href="https://console.cloud.google.com/apis/credentials" target="_blank" style="color: #818cf8;">
                        Google Cloud Console
                    </a>.
                </li>
                <li>Set the <b>Authorized redirect URI</b> to:
                    <br/><code style="background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; color: #fde68a;">http://localhost:8501/oauth2callback</code>
                </li>
                <li>Copy <code>.streamlit/secrets.toml.template</code> to <code>.streamlit/secrets.toml</code> and enter your credentials:</li>
            </ol>
            <pre style="background: rgba(0, 0, 0, 0.4); padding: 1rem; border-radius: 8px; font-size: 0.82rem; color: #a5f3fc; overflow-x: auto;">
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "generate_a_random_32_char_secret" # pragma: allowlist secret
client_id = "YOUR_CLIENT_ID.apps.googleusercontent.com"
client_secret = "YOUR_CLIENT_SECRET" # pragma: allowlist secret
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

allowed_emails = [
    "your.email@gmail.com",
]</pre>
            <p style="color: #94a3b8; font-size: 0.85rem; margin-top: 1rem;">
                Once saved, restart or reload Streamlit to activate Google login.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_login_screen() -> None:
    """Renders the Google Sign-in screen."""
    st.markdown(
        """
        <div style="max-width: 480px; margin: 4rem auto 2rem auto; text-align: center; padding: 2.5rem;
                    border-radius: 16px; background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08);">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">🎲</div>
            <h2 style="margin: 0; background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
                       -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                Board Game Rules Helper
            </h2>
            <p style="color: #94a3b8; font-size: 0.9rem; margin-top: 0.5rem; margin-bottom: 1.5rem;">
                This workspace is protected. Please sign in with an authorized Google account to proceed.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        if st.button(
            "🔑 Sign in with Google", type="primary", use_container_width=True
        ):
            st.login()


def _render_access_denied_screen(user_email: str) -> None:
    """Renders the Access Denied screen when a signed-in user is not whitelisted."""
    st.markdown(
        f"""
        <div style="max-width: 520px; margin: 4rem auto 2rem auto; text-align: center; padding: 2.5rem;
                    border-radius: 16px; background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.3);">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">🚫</div>
            <h2 style="color: #f87171; margin-top: 0;">Access Denied</h2>
            <p style="color: #cbd5e1; font-size: 0.95rem; line-height: 1.5;">
                The Google account <b>{user_email or "Unknown"}</b> is not authorized to use this application.
            </p>
            <p style="color: #94a3b8; font-size: 0.85rem; margin-top: 1rem;">
                Please contact the administrator to have your email address added to the whitelist,
                or sign in with an authorized account.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        if st.button("🚪 Log Out / Switch Account", use_container_width=True):
            st.logout()
