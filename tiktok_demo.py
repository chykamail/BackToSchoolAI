import os
import secrets
import urllib.parse

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, request, session, jsonify

load_dotenv()

app = Flask(__name__)

# Stable secret is required for Flask sessions.
# Set FLASK_SECRET_KEY in Render for production.
app.secret_key = os.getenv("FLASK_SECRET_KEY", "local-development-secret")

CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")

REDIRECT_URI = os.getenv(
    "TIKTOK_REDIRECT_URI",
    "https://backtoschoolai.onrender.com/callback",
)

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
CREATOR_INFO_URL = (
    "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
)

VIDEO_INIT_URL = (
    "https://open.tiktokapis.com/v2/post/publish/video/init/"
)

VIDEO_UPLOAD_URL = (
    "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
)

STATUS_URL = (
    "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
)


def auth_headers(access_token):
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }


@app.route("/")
def home():
    connected = bool(session.get("access_token"))
    display_name = session.get("display_name")

    if connected:
        return f"""
        <!doctype html>
        <html>
        <head>
            <title>BackToSchoolAI TikTok Production</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 700px;
                    margin: 70px auto;
                    padding: 30px;
                    text-align: center;
                }}
                .box {{
                    border: 1px solid #ddd;
                    border-radius: 12px;
                    padding: 30px;
                }}
                button {{
                    padding: 14px 24px;
                    font-size: 16px;
                    cursor: pointer;
                }}
            </style>
        </head>
        <body>
            <div class="box">
                <h1>BackToSchoolAI</h1>
                <h2>✓ TikTok Connected</h2>

                <p>
                    TikTok account:
                    <strong>{display_name or "Connected account"}</strong>
                </p>

                <p>Video ready:</p>
                <p><strong>video01-final.mp4</strong></p>

                <br>

                <a href="/creator-info">
                    <button>Prepare TikTok Post</button>
                </a>
            </div>
        </body>
        </html>
        """

    return """
    <!doctype html>
    <html>
    <head>
        <title>BackToSchoolAI TikTok Production</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 700px;
                margin: 70px auto;
                padding: 30px;
                text-align: center;
            }
            button {
                padding: 14px 24px;
                font-size: 16px;
                cursor: pointer;
            }
        </style>
    </head>

    <body>
        <h1>BackToSchoolAI</h1>
        <p>TikTok Production</p>

        <a href="/login">
            <button>Connect TikTok</button>
        </a>
    </body>
    </html>
    """


@app.route("/login")
def login():
    if not CLIENT_KEY:
        return "TIKTOK_CLIENT_KEY is missing.", 500

    if not CLIENT_SECRET:
        return "TIKTOK_CLIENT_SECRET is missing.", 500

    # Web OAuth uses state.
    # PKCE is NOT used for this Web flow.
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state

    params = {
        "client_key": CLIENT_KEY,
        "response_type": "code",
        "scope": "user.info.basic,video.upload,video.publish",
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }

    authorization_url = (
        AUTH_URL + "?" + urllib.parse.urlencode(params)
    )

    print()
    print("TIKTOK PRODUCTION WEB LOGIN")
    print("----------------------------")
    print("Client key:", CLIENT_KEY)
    print("Redirect URI:", REDIRECT_URI)
    print("PKCE: DISABLED FOR WEB")
    print()

    return redirect(authorization_url)


@app.route("/callback")
def callback():
    error = request.args.get("error")

    if error:
        return jsonify({
            "status": "authorization_error",
            "error": error,
            "description": request.args.get("error_description"),
            "log_id": request.args.get("log_id"),
        }), 400

    code = request.args.get("code")

    if not code:
        return jsonify({
            "status": "error",
            "message": "No authorization code returned.",
            "query_parameters": dict(request.args),
        }), 400

    returned_state = request.args.get("state")
    expected_state = session.get("oauth_state")

    if not expected_state or returned_state != expected_state:
        return jsonify({
            "status": "error",
            "message": "OAuth state validation failed.",
        }), 400

    token_data = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }

    print()
    print("TIKTOK TOKEN REQUEST")
    print("--------------------")
    print("Client key loaded:", bool(CLIENT_KEY))
    print("Client secret loaded:", bool(CLIENT_SECRET))
    print("Authorization code received:", bool(code))
    print("Redirect URI:", repr(REDIRECT_URI))
    print("PKCE: NOT SENT")
    print()

    response = requests.post(
        TOKEN_URL,
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        },
        data=token_data,
        timeout=30,
    )

    try:
        token_response = response.json()
    except Exception:
        token_response = {
            "raw_response": response.text
        }

    if response.status_code != 200:
        return jsonify({
            "status": "token_error",
            "http_status": response.status_code,
            "response": token_response,
        }), 400

    access_token = token_response.get("access_token")

    if not access_token:
        return jsonify({
            "status": "error",
            "message": "TikTok did not return an access token.",
            "response": token_response,
        }), 400

    session["access_token"] = access_token
    session["open_id"] = token_response.get("open_id")

    user_response = requests.get(
        USER_INFO_URL,
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        params={
            "fields": "open_id,display_name,avatar_url"
        },
        timeout=30,
    )

    try:
        user_data = user_response.json()
    except Exception:
        user_data = {
            "raw_response": user_response.text
        }

    if user_response.status_code != 200:
        return jsonify({
            "status": "user_info_error",
            "http_status": user_response.status_code,
            "response": user_data,
        }), 400

    data = user_data.get("data", {})

    session["display_name"] = data.get("user", {}).get(
        "display_name"
    )

    session["avatar_url"] = data.get("user", {}).get(
        "avatar_url"
    )

    return redirect("/")


@app.route("/creator-info")
def creator_info():
    access_token = session.get("access_token")

    if not access_token:
        return redirect("/login")

    response = requests.post(
        CREATOR_INFO_URL,
        headers=auth_headers(access_token),
        timeout=30,
    )

    try:
        data = response.json()
    except Exception:
        data = {
            "raw_response": response.text
        }

    if response.status_code != 200:
        return jsonify({
            "status": "creator_info_error",
            "http_status": response.status_code,
            "response": data,
        }), 400

    return jsonify({
        "status": "creator_info_success",
        "creator_info": data,
        "next_step": "Content Posting API is ready.",
    })


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    print()
    print("==========================================")
    print(" BackToSchoolAI TikTok Production")
    print("==========================================")
    print()
    print("Open:")
    print("http://127.0.0.1:8080")
    print()
    print("Press CTRL+C to stop.")
    print()

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        debug=False,
    )