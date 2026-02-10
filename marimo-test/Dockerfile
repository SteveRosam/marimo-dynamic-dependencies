FROM ghcr.io/marimo-team/marimo:latest

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    MARIMO_USER_CONFIG_PATH=/app/state \
    MARIMO_MODE="browser" \
    MARIMO_NOTEBOOK="main.py"

# Set working directory
WORKDIR /app

# Install nginx and supervisor
USER root
RUN apt-get update && apt-get install -y nginx supervisor git && rm -rf /var/lib/apt/lists/*

# Install quixportal for token validation (with dependencies) and fastapi for auth proxy
RUN pip install --no-cache-dir fsspec>=2024.6.0 httpx>=0.28.1 pydantic>=2.0.0 fastapi uvicorn && \
    pip install --no-cache-dir --no-deps \
    -i https://pkgs.dev.azure.com/quix-analytics/53f7fe95-59fe-4307-b479-2473b96de6d1/_packaging/public/pypi/simple/ \
    quixportal

# Copy infrastructure files
COPY auth_proxy.py /app/
COPY file_watcher.py /app/
COPY nginx.conf /etc/nginx/nginx.conf

# Copy application files
COPY main.py /app/main.py
COPY icon.png /app/icon.gif
COPY requirements.txt /app/

# Create a venv template at build time with all requirements installed
# This gets copied to state directory at runtime for fast startup
RUN python -m venv /app/venv-template && \
    /app/venv-template/bin/pip install --no-cache-dir -r /app/requirements.txt

# Expose port
EXPOSE 8080

# Create default marimo config with dark theme
RUN mkdir -p /app/state && \
    cat <<EOF > /app/.marimo.toml
[display]
theme = "dark"
code_editor_font_size = 14

[completion]
activate_on_typing = true
copilot = false

[formatting]
line_length = 79

[runtime]
auto_instantiate = true

[save]
autosave = "off"
format_on_save = false

[keymap]
preset = "default"

[ai.models]
chat_model = "anthropic/claude-sonnet-4-20250514"
edit_model = "anthropic/claude-sonnet-4-20250514"

[ai.anthropic]
api_key = "${ANTHROPIC_API_KEY}"
EOF

# Create supervisor config
RUN printf '[supervisord]\n\
nodaemon=true\n\
logfile=/dev/stdout\n\
logfile_maxbytes=0\n\
\n\
[program:nginx]\n\
command=nginx -g "daemon off;"\n\
autostart=true\n\
autorestart=true\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
\n\
[program:auth_proxy]\n\
command=python /app/auth_proxy.py\n\
autostart=true\n\
autorestart=true\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
\n\
[program:marimo]\n\
command=/app/start_marimo.sh\n\
autostart=true\n\
autorestart=true\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
\n\
[program:file_watcher]\n\
command=python /app/file_watcher.py\n\
autostart=true\n\
autorestart=true\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
' > /etc/supervisor/conf.d/supervisord.conf

# Create marimo startup script (handles browser mode + venv persistence)
RUN printf '#!/bin/bash\n\
set -e\n\
\n\
VENV_DIR="/app/state/venv"\n\
VENV_TEMPLATE="/app/venv-template"\n\
\n\
# Copy venv template to state directory if not exists (fast startup)\n\
# Runtime-installed packages persist in the state venv\n\
if [ ! -d "$VENV_DIR" ]; then\n\
    echo "Copying venv template to $VENV_DIR..."\n\
    cp -r "$VENV_TEMPLATE" "$VENV_DIR"\n\
fi\n\
\n\
echo "Activating virtual environment from $VENV_DIR"\n\
source "$VENV_DIR/bin/activate"\n\
\n\
# Run marimo with CORS enabled for embedding\n\
if [ "$MARIMO_MODE" = "browser" ]; then\n\
    exec marimo edit /app --host 127.0.0.1 -p 8081 --no-token --allow-origins "*"\n\
else\n\
    exec marimo "$MARIMO_MODE" "$MARIMO_NOTEBOOK" --host 127.0.0.1 -p 8081 --no-token --allow-origins "*"\n\
fi\n\
' > /app/start_marimo.sh && chmod +x /app/start_marimo.sh

# Create startup script - always use nginx + auth proxy for Quix PAT authentication
RUN printf '#!/bin/bash\n\
# Always use supervisord with nginx + auth proxy\n\
# Authentication works via Quix PAT tokens:\n\
# - Plugin mode (iframe): token received via postMessage from parent\n\
# - Standalone mode: user enters PAT token in login form\n\
exec supervisord -c /etc/supervisor/conf.d/supervisord.conf\n\
' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]
