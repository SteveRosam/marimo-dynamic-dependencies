"""
Auth proxy service for Quix plugin integration.
Handles postMessage token exchange and validates tokens against Quix API.
"""

import os
import secrets
import hashlib
import httpx
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Response, Cookie
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional

app = FastAPI()

# In-memory session store (tokens are short-lived anyway)
# Maps session_id -> {token: str, expires: datetime}
sessions: dict = {}

# Session cookie name
SESSION_COOKIE = "quix_session"
SESSION_DURATION_HOURS = 8

# Quix API configuration
PORTAL_API = os.environ.get("Quix__Portal__Api", "")
WORKSPACE_ID = os.environ.get("Quix__Workspace__Id", "")
DEPLOYMENT_ID = os.environ.get("Quix__Deployment__Id", "")


def validate_quix_token(token: str) -> bool:
    """Validate token against Quix API."""
    if not token:
        print("Token validation failed: No token provided")
        return False

    # Log environment for debugging
    print(f"Validating token against Quix API")
    print(f"PORTAL_API: {PORTAL_API}")
    print(f"WORKSPACE_ID: {WORKSPACE_ID}")

    try:
        from quixportal.auth import Auth
        auth = Auth()
        # Validate that the user has read access to this workspace
        result = auth.validate_permissions(
            token=token,
            resourceType="Workspace",
            resourceID=WORKSPACE_ID,
            permissions="Read"
        )
        print(f"Token validation result: {result}")
        return bool(result)
    except Exception as e:
        print(f"Token validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_session(token: str) -> str:
    """Create a new session for a validated token."""
    session_id = secrets.token_urlsafe(32)
    sessions[session_id] = {
        "token": token,
        "expires": datetime.utcnow() + timedelta(hours=SESSION_DURATION_HOURS)
    }
    # Clean up old sessions
    cleanup_sessions()
    return session_id


def cleanup_sessions():
    """Remove expired sessions."""
    now = datetime.utcnow()
    expired = [sid for sid, data in sessions.items() if data["expires"] < now]
    for sid in expired:
        del sessions[sid]


def is_valid_session(session_id: str) -> bool:
    """Check if session is valid and not expired."""
    if not session_id or session_id not in sessions:
        return False
    session = sessions[session_id]
    if session["expires"] < datetime.utcnow():
        del sessions[session_id]
        return False
    return True


def redeploy_with_latest(deployment_id: str, token: str) -> dict:
    """
    Set a deployment to use the latest version of the code and re-deploy it.

    Args:
        deployment_id: The ID of the deployment to update
        token: Bearer token for API authentication

    Returns:
        dict: Response from the redeploy API call
    """
    if not PORTAL_API:
        raise ValueError("Quix__Portal__Api environment variable is not set")
    if not WORKSPACE_ID:
        raise ValueError("Quix__Workspace__Id environment variable is not set")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    base_url = f"{PORTAL_API}/{WORKSPACE_ID}"

    with httpx.Client() as client:
        # Get the current deployment configuration
        get_url = f"{base_url}/deployments/{deployment_id}"
        response = client.get(get_url, headers=headers)
        response.raise_for_status()
        deployment = response.json()

        # Update to use latest version
        deployment["versionTag"] = "latest"

        # Update the deployment
        update_url = f"{base_url}/deployments/{deployment_id}"
        response = client.put(update_url, headers=headers, json=deployment)
        response.raise_for_status()

        # Trigger redeploy
        redeploy_url = f"{base_url}/deployments/{deployment_id}/redeploy"
        response = client.post(redeploy_url, headers=headers)
        response.raise_for_status()

        return response.json()

# HTML page that handles postMessage token exchange OR manual PAT token login
AUTH_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Authenticating...</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: #1a1a2e;
            color: #eee;
        }
        .container {
            text-align: center;
            max-width: 400px;
            padding: 20px;
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid #333;
            border-top-color: #6366f1;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .error {
            color: #f87171;
            display: none;
            margin-top: 10px;
        }
        .login-form {
            display: none;
            text-align: left;
        }
        .login-form h2 {
            text-align: center;
            margin-bottom: 20px;
            color: #fff;
        }
        .login-form label {
            display: block;
            margin-bottom: 5px;
            color: #aaa;
            font-size: 14px;
        }
        .login-form input {
            width: 100%;
            padding: 12px;
            border: 1px solid #333;
            border-radius: 6px;
            background: #2a2a3e;
            color: #fff;
            font-size: 14px;
            box-sizing: border-box;
            margin-bottom: 15px;
        }
        .login-form input:focus {
            outline: none;
            border-color: #6366f1;
        }
        .login-form button {
            width: 100%;
            padding: 12px;
            background: #6366f1;
            border: none;
            border-radius: 6px;
            color: #fff;
            font-size: 16px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .login-form button:hover {
            background: #5558e3;
        }
        .login-form button:disabled {
            background: #444;
            cursor: not-allowed;
        }
        .help-text {
            font-size: 12px;
            color: #888;
            margin-top: 15px;
            text-align: center;
        }
        .help-text a {
            color: #6366f1;
        }
    </style>
</head>
<body>
    <div class="container">
        <div id="loading">
            <div class="spinner"></div>
            <p id="status">Authenticating with Quix...</p>
        </div>
        <div id="login-form" class="login-form">
            <h2>Marimo Notebook</h2>
            <form onsubmit="submitToken(event)">
                <label for="token">Quix Personal Access Token</label>
                <input type="password" id="token" name="token" placeholder="Enter your PAT token" required>
                <button type="submit" id="submit-btn">Sign In</button>
            </form>
            <p class="help-text">
                Create a token in <a href="https://portal.platform.quix.io/settings/personal-access-tokens" target="_blank">Quix Settings</a>
            </p>
        </div>
        <p id="error" class="error"></p>
    </div>
    <script>
        let tokenReceived = false;
        const isInIframe = window.parent !== window;

        // Listen for auth token from parent (plugin mode)
        window.addEventListener('message', async function(event) {
            if (event.data && event.data.type === 'AUTH_TOKEN' && event.data.token) {
                tokenReceived = true;
                document.getElementById('status').textContent = 'Validating token...';
                await validateToken(event.data.token);
            }
        });

        async function validateToken(token) {
            try {
                const response = await fetch('/validate-token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ token: token })
                });

                if (response.ok) {
                    window.location.href = '/';
                } else {
                    const data = await response.json();
                    showError(data.detail || 'Token validation failed');
                }
            } catch (e) {
                showError('Failed to validate token: ' + e.message);
            }
        }

        async function submitToken(event) {
            event.preventDefault();
            const token = document.getElementById('token').value;
            const btn = document.getElementById('submit-btn');
            btn.disabled = true;
            btn.textContent = 'Validating...';
            hideError();

            await validateToken(token);

            btn.disabled = false;
            btn.textContent = 'Sign In';
        }

        function showError(msg) {
            document.getElementById('error').textContent = msg;
            document.getElementById('error').style.display = 'block';
        }

        function hideError() {
            document.getElementById('error').style.display = 'none';
        }

        function showLoginForm() {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('login-form').style.display = 'block';
        }

        if (isInIframe) {
            // Plugin mode: request token from parent
            window.parent.postMessage({ type: 'REQUEST_AUTH_TOKEN' }, '*');

            // Timeout - show login form if no token received
            setTimeout(function() {
                if (!tokenReceived) {
                    showLoginForm();
                }
            }, 3000);
        } else {
            // Standalone mode: show login form immediately
            showLoginForm();
        }
    </script>
</body>
</html>
"""


@app.get("/auth", response_class=HTMLResponse)
async def auth_page():
    """Serve the authentication page that handles postMessage token exchange."""
    return AUTH_PAGE_HTML


@app.post("/validate-token")
async def validate_token(request: Request, response: Response):
    """Validate a Quix token and create a session."""
    try:
        data = await request.json()
        token = data.get("token")

        if not token:
            return JSONResponse({"detail": "No token provided"}, status_code=400)

        if validate_quix_token(token):
            session_id = create_session(token)
            response = JSONResponse({"status": "ok"})
            response.set_cookie(
                key=SESSION_COOKIE,
                value=session_id,
                httponly=True,
                secure=True,
                samesite="none",  # Required for iframe
                max_age=SESSION_DURATION_HOURS * 3600
            )
            return response
        else:
            return JSONResponse({"detail": "Invalid token"}, status_code=401)
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)


@app.get("/internal-auth")
async def internal_auth(request: Request, quix_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE)):
    """Internal endpoint for nginx auth_request - returns 200 if authenticated, 401 if not."""
    if is_valid_session(quix_session):
        return Response(status_code=200)
    # Return 401 - nginx will redirect to /auth
    return Response(status_code=401)


@app.get("/internal-token")
async def internal_token():
    """Internal endpoint for services to get the current user token.
    Returns the most recently validated token for API calls.
    Only accessible from localhost (internal services)."""
    # Get the most recent valid session's token
    now = datetime.utcnow()
    for session_id, data in sessions.items():
        if data["expires"] > now and data.get("token"):
            return JSONResponse({"token": data["token"]})
    return JSONResponse({"token": None}, status_code=404)


@app.post("/redeploy")
async def trigger_redeploy(request: Request, quix_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE)):
    """Trigger a redeploy of this service to pick up newly installed packages."""
    if not is_valid_session(quix_session):
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)

    if not DEPLOYMENT_ID:
        return JSONResponse({"detail": "Deployment ID not configured"}, status_code=500)

    # Get the user's token from their session
    session = sessions.get(quix_session)
    if not session or not session.get("token"):
        return JSONResponse({"detail": "No valid token in session"}, status_code=401)

    try:
        result = redeploy_with_latest(DEPLOYMENT_ID, session["token"])
        return JSONResponse({"status": "redeploying", "result": result})
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8082)
