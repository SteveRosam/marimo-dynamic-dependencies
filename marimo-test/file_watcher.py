#!/usr/bin/env python3
"""
File watcher service that monitors main.py for changes and commits to Quix Portal.
"""

import os
import sys
import time
import json
import logging
import urllib.request
import urllib.error
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('file_watcher')

WATCH_FILE = os.environ.get('WATCH_FILE', '/app/main.py')
PORTAL_API = os.environ.get('Quix__Portal__Api', '').replace('http://', 'https://')
WORKSPACE_ID = os.environ.get('Quix__Workspace__Id', '')
APPLICATION_ID = os.environ.get('Quix__Application__Id', '')
AUTH_PROXY_URL = 'http://127.0.0.1:8082/internal-token'


def get_user_token():
    """Get the current user token from auth proxy."""
    try:
        req = urllib.request.Request(AUTH_PROXY_URL)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('token')
    except Exception as e:
        logger.debug(f"Could not get user token from auth proxy: {e}")
        return None


def get_file_mtime(filepath):
    """Get file modification time, return None if file doesn't exist"""
    try:
        return Path(filepath).stat().st_mtime
    except FileNotFoundError:
        return None


def read_file_content(filepath):
    """Read file content as plain text"""
    try:
        with open(filepath, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return None


def commit_file(filepath):
    """Send POST request to commit the file changes"""
    if not PORTAL_API or not WORKSPACE_ID:
        logger.warning("PORTAL_API or WORKSPACE_ID not configured, skipping commit")
        return False

    content = read_file_content(filepath)
    if content is None:
        return False

    filename = Path(filepath).name
    file_path = f"{APPLICATION_ID}/{filename}"
    url = f"{PORTAL_API}/workspaces/{WORKSPACE_ID}/files/{file_path}"

    headers = {
        'Content-Type': 'text/plain',
        'X-Version': '2.0',
        'Accept': 'text/plain',
    }

    # Get user token from auth proxy
    token = get_user_token()
    if token:
        headers['Authorization'] = f'Bearer {token}'
        logger.info(f"Using user token: {token[:20]}...")
    else:
        logger.warning("No user token available, commit may fail")

    logger.info(f"Committing to URL: {url}")
    logger.info(f"Content length: {len(content)} bytes")

    try:
        data = content.encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')

        with urllib.request.urlopen(req, timeout=30) as response:
            response_body = response.read().decode('utf-8')
            logger.info(f"Commit successful: {response.status}")
            logger.info(f"Response: {response_body[:500] if response_body else '(empty)'}")
            return True

    except urllib.error.HTTPError as e:
        logger.error(f"Commit failed with HTTP {e.code}: {e.reason}")
        try:
            error_body = e.read().decode('utf-8')
            logger.error(f"Error response: {error_body}")
        except:
            pass
        return False
    except urllib.error.URLError as e:
        logger.error(f"Commit failed: {e.reason}")
        return False
    except Exception as e:
        logger.error(f"Commit failed: {e}")
        return False


def main():
    logger.info(f"Starting file watcher for: {WATCH_FILE}")
    logger.info(f"Portal API: {PORTAL_API}")
    logger.info(f"Workspace ID: {WORKSPACE_ID}")

    if not PORTAL_API or not WORKSPACE_ID:
        logger.warning("Missing configuration - will only log changes")

    last_mtime = get_file_mtime(WATCH_FILE)
    if last_mtime:
        logger.info(f"Initial file mtime: {last_mtime}")
    else:
        logger.warning(f"File not found: {WATCH_FILE}")

    while True:
        try:
            current_mtime = get_file_mtime(WATCH_FILE)

            if current_mtime is None:
                if last_mtime is not None:
                    logger.warning(f"File was deleted: {WATCH_FILE}")
                    last_mtime = None
            elif last_mtime is None:
                logger.info(f"File created: {WATCH_FILE}")
                last_mtime = current_mtime
                commit_file(WATCH_FILE)
            elif current_mtime != last_mtime:
                logger.info(f"File changed: {WATCH_FILE}")
                last_mtime = current_mtime
                commit_file(WATCH_FILE)

            time.sleep(1)  # Check every second

        except Exception as e:
            logger.error(f"Error watching file: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
