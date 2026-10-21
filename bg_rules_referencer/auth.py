from collections.abc import Mapping
import json
import os
from pathlib import Path
from typing import Any

import streamlit as st


def ensure_secrets_file_from_env() -> None:
    """If .streamlit/secrets.toml doesn't exist on disk, synthesize it from environment variables."""
    secrets_path = Path(".streamlit/secrets.toml")
    if not secrets_path.exists() and os.getenv("STREAMLIT_AUTH_CLIENT_ID"):
        try:
            secrets_path.parent.mkdir(parents=True, exist_ok=True)
            content = (
                f"[auth]\n"
                f'redirect_uri = "{os.getenv("STREAMLIT_AUTH_REDIRECT_URI", "http://localhost:8501/oauth2callback")}"\n'
                f'cookie_secret = "{os.getenv("STREAMLIT_AUTH_COOKIE_SECRET", "")}"\n'
                f'client_id = "{os.getenv("STREAMLIT_AUTH_CLIENT_ID", "")}"\n'
                f'client_secret = "{os.getenv("STREAMLIT_AUTH_CLIENT_SECRET", "")}"\n'
                f'server_metadata_url = "{os.getenv("STREAMLIT_AUTH_SERVER_METADATA_URL", "https://accounts.google.com/.well-known/openid-configuration")}"\n'
                f'admin_email = "{os.getenv("ADMIN_EMAIL", "")}"\n'
            )
            secrets_path.write_text(content, encoding="utf-8")
        except Exception:
            pass


# Ensure secrets file is present before Streamlit auth checks it
ensure_secrets_file_from_env()


def get_auth_config() -> dict[str, Any]:
    """Safely retrieves the [auth] dictionary from Streamlit secrets or environment variables."""
    conf: dict[str, Any] = {}
    try:
        if "auth" in st.secrets:
            conf.update(dict(st.secrets["auth"]))
    except Exception:
        pass

    # Environment variable fallbacks (useful for Docker & Cloud Run)
    for key in (
        "client_id",
        "client_secret",
        "redirect_uri",
        "cookie_secret",
        "server_metadata_url",
    ):
        env_val = os.getenv(f"STREAMLIT_AUTH_{key.upper()}") or os.getenv(
            f"AUTH_{key.upper()}"
        )
        if env_val and key not in conf:
            conf[key] = env_val

    return conf


def get_dynamic_users_file() -> Path:
    """Returns the persistent file path used for dynamic whitelist additions."""
    custom_path = os.getenv("ALLOWED_USERS_FILE")
    if custom_path:
        return Path(custom_path)

    # Cloud Run volume mount or Docker persistent data directory
    if os.path.isdir("/data") and os.access("/data", os.W_OK):
        return Path("/data/allowed_users.json")

    # Local development (.streamlit directory)
    streamlit_dir = Path(".streamlit")
    if streamlit_dir.is_dir():
        return streamlit_dir / "allowed_users.json"

    return Path("allowed_users.json")


def get_dynamic_allowed_emails() -> set[str]:
    """Reads dynamically added user emails from the persistent JSON file."""
    file_path = get_dynamic_users_file()
    if not file_path.exists():
        return set()
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(e).strip().lower() for e in data if e}
        elif isinstance(data, dict):
            items = data.get("allowed_emails", [])
            return {str(e).strip().lower() for e in items if e}
    except Exception:
        pass
    return set()


def add_allowed_email(email: str) -> bool:
    """Adds a new email to the dynamic whitelist JSON file."""
    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email:
        return False

    current = get_dynamic_allowed_emails()
    current.add(clean_email)

    file_path = get_dynamic_users_file()
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps({"allowed_emails": sorted(list(current))}, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def remove_allowed_email(email: str) -> bool:
    """Removes an email from the dynamic whitelist JSON file."""
    clean_email = email.strip().lower()
    current = get_dynamic_allowed_emails()
    if clean_email in current:
        current.remove(clean_email)
        file_path = get_dynamic_users_file()
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(
                json.dumps({"allowed_emails": sorted(list(current))}, indent=2),
                encoding="utf-8",
            )
            return True
        except Exception:
            return False
    return False


def get_admin_emails() -> set[str]:
    """Retrieves administrator emails from Streamlit secrets or environment variables."""
    admins: set[str] = set()

    # 1. From st.secrets (top-level or inside [auth])
    try:
        for key in ("admin_emails", "admin_email"):
            if key in st.secrets:
                val = st.secrets[key]
                if isinstance(val, (list, tuple, set)):
                    admins.update(str(e).strip().lower() for e in val if e)
                elif isinstance(val, str):
                    admins.update(
                        e.strip().lower() for e in val.split(",") if e.strip()
                    )

        auth_conf = st.secrets.get("auth", {})
        if isinstance(auth_conf, Mapping):
            for key in ("admin_emails", "admin_email"):
                if key in auth_conf:
                    val = auth_conf[key]
                    if isinstance(val, (list, tuple, set)):
                        admins.update(str(e).strip().lower() for e in val if e)
                    elif isinstance(val, str):
                        admins.update(
                            e.strip().lower() for e in val.split(",") if e.strip()
                        )
    except Exception:
        pass

    # 2. From environment variables
    env_admin = os.getenv("ADMIN_EMAILS") or os.getenv("ADMIN_EMAIL")
    if env_admin:
        admins.update(e.strip().lower() for e in env_admin.split(",") if e.strip())

    return admins


def is_admin_user() -> bool:
    """Returns True if the currently authenticated user is an administrator."""
    if not getattr(st.user, "is_logged_in", False):
        return False
    user_email = (getattr(st.user, "email", None) or "").strip().lower()
    return user_email in get_admin_emails()


def get_allowed_emails() -> set[str]:
    """Retrieves the complete set of authorized emails (admins, secrets, env, and dynamic)."""
    emails: set[str] = set()

    # Admins are always allowed
    emails.update(get_admin_emails())

    # 1. From st.secrets
    try:
        if "allowed_emails" in st.secrets:
            items = st.secrets["allowed_emails"]
            if isinstance(items, (list, tuple, set)):
                emails.update(str(e).strip().lower() for e in items if e)
            elif isinstance(items, str):
                emails.update(e.strip().lower() for e in items.split(",") if e.strip())

        auth_conf = st.secrets.get("auth", {})
        if isinstance(auth_conf, Mapping) and "allowed_emails" in auth_conf:
            items = auth_conf["allowed_emails"]
            if isinstance(items, (list, tuple, set)):
                emails.update(str(e).strip().lower() for e in items if e)
            elif isinstance(items, str):
                emails.update(e.strip().lower() for e in items.split(",") if e.strip())
    except Exception:
        pass

    # 2. From environment variables
    env_str = os.getenv("ALLOWED_EMAILS") or os.getenv("WHITELISTED_EMAILS") or ""
    if env_str:
        emails.update(e.strip().lower() for e in env_str.split(",") if e.strip())

    # 3. From dynamic in-app additions
    emails.update(get_dynamic_allowed_emails())

    return emails


def is_auth_configured() -> bool:
    """Checks whether Google OAuth and admin email have been configured."""
    auth_conf = get_auth_config()
    client_id = auth_conf.get("client_id", "")
    client_secret = auth_conf.get("client_secret", "")
    admins = get_admin_emails()

    has_client = bool(
        client_id
        and client_secret
        and "YOUR_GOOGLE_CLIENT_ID" not in client_id
        and "YOUR_GOOGLE_CLIENT_SECRET" not in client_secret
    )

    # Fail if OAuth credentials or admin email are not configured
    return has_client and bool(admins)


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

    is_logged_in = getattr(st.user, "is_logged_in", False)
    if not is_logged_in:
        _render_login_screen()
        st.stop()

    user_email = (getattr(st.user, "email", None) or "").strip().lower()
    allowed = get_allowed_emails()

    if allowed and user_email not in allowed:
        _render_access_denied_screen(user_email)
        st.stop()

    return True


def render_user_badge() -> None:
    """Renders user info, admin whitelist manager, and a sign-out button in the sidebar."""
    if not getattr(st.user, "is_logged_in", False):
        return

    name = getattr(st.user, "name", None) or "User"
    email = (getattr(st.user, "email", None) or "").strip().lower()
    is_admin = is_admin_user()

    st.sidebar.markdown("---")

    # In-App Admin Whitelist Management (Only visible to admins)
    if is_admin:
        with st.sidebar.expander("⚙️ Manage Whitelist", expanded=False):
            st.markdown(
                "<span style='font-size: 0.82rem; color: #94a3b8;'>Add or remove Google emails allowed to access this app.</span>",
                unsafe_allow_html=True,
            )

            # Add Email Input
            col_in, col_btn = st.columns([3, 1])
            with col_in:
                new_email = st.text_input(
                    "User Email",
                    placeholder="player@gmail.com",
                    label_visibility="collapsed",
                    key="admin_add_email_input",
                )
            with col_btn:
                if st.button(
                    "➕", help="Add email to whitelist", key="admin_add_email_btn"
                ):
                    if new_email and "@" in new_email:
                        if add_allowed_email(new_email):
                            st.toast(f"✅ Added {new_email} to whitelist")
                            st.rerun()
                        else:
                            st.error("Failed to add email.")
                    else:
                        st.warning("Enter a valid email address.")

            # List Current Whitelisted Emails
            dynamic_emails = get_dynamic_allowed_emails()
            all_emails = sorted(list(get_allowed_emails()))
            admin_emails = get_admin_emails()

            st.markdown(
                f"<div style='font-size: 0.8rem; font-weight: 600; margin-top: 0.5rem; margin-bottom: 0.25rem;'>"
                f"Active Users ({len(all_emails)})</div>",
                unsafe_allow_html=True,
            )

            for u_email in all_emails:
                u_col, b_col = st.columns([4, 1])
                with u_col:
                    if u_email in admin_emails:
                        st.markdown(
                            f"<span style='font-size: 0.78rem; color: #a855f7;'>👑 <code>{u_email}</code></span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<span style='font-size: 0.78rem; color: #cbd5e1;'>👤 <code>{u_email}</code></span>",
                            unsafe_allow_html=True,
                        )
                with b_col:
                    # Allow removing dynamically added emails (admins cannot remove admin accounts here)
                    if u_email in dynamic_emails and u_email not in admin_emails:
                        if st.button(
                            "🗑️",
                            key=f"del_user_{u_email}",
                            help=f"Revoke access for {u_email}",
                        ):
                            if remove_allowed_email(u_email):
                                st.toast(f"🗑️ Removed {u_email}")
                                st.rerun()

    # User Profile & Logout
    col1, col2 = st.sidebar.columns([3, 1.2])
    with col1:
        admin_badge = " *(Admin)*" if is_admin else ""
        st.caption(f"👤 **{name}**{admin_badge}\n`{email}`")
    with col2:
        if st.button(
            "🚪 Sign out", key="auth_logout_btn", help="Sign out of your account"
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
client_id = "YOUR_CLIENT_ID.apps.googleusercontent.com" # pragma: allowlist secret
client_secret = "YOUR_CLIENT_SECRET" # pragma: allowlist secret
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
admin_email = "your.email@gmail.com"</pre>
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
