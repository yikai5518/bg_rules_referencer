#!/bin/sh
set -e

# If .streamlit/secrets.toml does not exist, synthesize it from environment variables for Streamlit's auth subsystem
if [ ! -f .streamlit/secrets.toml ] && [ -n "$STREAMLIT_AUTH_CLIENT_ID" ]; then
    mkdir -p .streamlit
    cat <<EOF > .streamlit/secrets.toml
[auth]
redirect_uri = "${STREAMLIT_AUTH_REDIRECT_URI:-http://localhost:8501/oauth2callback}"
cookie_secret = "${STREAMLIT_AUTH_COOKIE_SECRET}"
client_id = "${STREAMLIT_AUTH_CLIENT_ID}"
client_secret = "${STREAMLIT_AUTH_CLIENT_SECRET}"
server_metadata_url = "${STREAMLIT_AUTH_SERVER_METADATA_URL:-https://accounts.google.com/.well-known/openid-configuration}"
admin_email = "${ADMIN_EMAIL}"
EOF
fi

exec streamlit run app.py --server.port="${PORT:-8080}" --server.address=0.0.0.0
