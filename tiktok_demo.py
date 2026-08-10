import hashlib
import os
import secrets
import urllib.parse

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, request, session, jsonify

load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
REDIRECT_URI = os.getenv(
    "TIKTOK_REDIRECT_URI",
    "https://backtoschoolai.onrender.com/callback"
)

VIDEO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video01-final.mp4")

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"

CREATOR_INFO_URL = (
    "https://open.tiktokapis.com/v2/post/publish/"
    "creator_info/query/"
)

VIDEO_INIT_URL = (
    "https://open.tiktokapis.com/v2/post/publish/"
    "video/init/"
)

STATUS_URL = (
    "https://open.tiktokapis.com/v2/post/publish/"
    "status/fetch/"
)


def create_pkce():
    verifier = secrets.token_urlsafe(64)

    challenge = hashlib.sha256(
        verifier.encode("utf-8")
    ).hexdigest()

    return verifier, challenge


def auth_headers(access_token):
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8"
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

                <h2>âœ“ TikTok Connected</h2>

                <p>
                    TikTok account:
                    <strong>{display_name or "Connected account"}</strong>
                </p>

                <p>Video ready:</p>

                <p>
                    <strong>video01-final.mp4</strong>
                </p>

                <br>

                <a href="/creator-info">
                    <button>
                        Prepare TikTok Post
                    </button>
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
        return "TIKTOK_CLIENT_KEY is missing from .env", 500

    verifier, challenge = create_pkce()
    state = secrets.token_urlsafe(32)

    session["pkce_verifier"] = verifier
    session["state"] = state

    params = {
    "client_key": CLIENT_KEY,
    "response_type": "code",
    "scope": "user.info.basic",
    "redirect_uri": REDIRECT_URI,
    "state": state,
}

    authorization_url = (
        AUTH_URL + "?" + urllib.parse.urlencode(params)
    )

    return redirect(authorization_url)


@app.route("/callback/tiktokBBCFkc0iuTj8Tw2ddA3R7njDYtHxZgsI.txt")
def tiktok_verification():
    return "tiktok-developers-site-verification=BBCFkc0iuTj8Tw2ddA3R7njDYtHxZgsI"

@app.route("/callback")
def callback():

    error = request.args.get("error")

    if error:
        return jsonify({
            "status": "authorization_error",
            "error": error,
            "description": request.args.get(
                "error_description"
            )
        }), 400

    code = request.args.get("code")

    if not code:
        return jsonify({
            "status": "error",
            "message": "No authorization code returned."
        }), 400

    returned_state = request.args.get("state")

    if returned_state != session.get("state"):
        return jsonify({
            "status": "error",
            "message": "OAuth state validation failed."
        }), 400

    verifier = session.get("pkce_verifier")

    if not verifier:
        return jsonify({
            "status": "error",
            "message": "PKCE verifier was not found."
        }), 400

    token_data = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }

    response = requests.post(
        TOKEN_URL,
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded"
        },
        data=token_data,
        timeout=30
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
            "response": token_response
        }), 400

    access_token = token_response.get("access_token")

    if not access_token:
        return jsonify({
            "status": "error",
            "message":
                "TikTok did not return an access token.",
            "response": token_response
        }), 400

    session["access_token"] = access_token

    user_response = requests.get(
        USER_INFO_URL,
        headers={
            "Authorization":
                f"Bearer {access_token}"
        },
        params={
            "fields":
                "open_id,display_name,avatar_url"
        },
        timeout=30
    )

    try:
        user_data = user_response.json()
    except Exception:
        user_data = {}

    user = (
        user_data
        .get("data", {})
        .get("user", {})
    )

    session["open_id"] = user.get("open_id")
    session["display_name"] = user.get(
        "display_name",
        "TikTok account"
    )

    return redirect("/")


@app.route("/creator-info")
def creator_info():

    access_token = session.get("access_token")

    if not access_token:
        return redirect("/")

    response = requests.post(
        CREATOR_INFO_URL,
        headers=auth_headers(access_token),
        json={},
        timeout=30
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
            "response": data
        }), 400

    if data.get("error", {}).get("code") != "ok":
        return jsonify({
            "status": "creator_info_error",
            "response": data
        }), 400

    creator = data.get("data", {})

    privacy_options = creator.get(
        "privacy_level_options",
        []
    )

    session["privacy_options"] = privacy_options

    return jsonify({
        "status": "creator_info_success",
        "creator": {
            "username":
                creator.get("creator_username"),
            "nickname":
                creator.get("creator_nickname"),
        },
        "privacy_level_options":
            privacy_options,
        "max_video_duration":
            creator.get(
                "max_video_post_duration_sec"
            ),
        "next_step":
            "/post-video"
    })


@app.route("/post-video")
def post_video():

    access_token = session.get("access_token")

    if not access_token:
        return redirect("/")

    if not os.path.exists(VIDEO_PATH):
        return jsonify({
            "status": "error",
            "message": "Video file not found.",
            "path": VIDEO_PATH
        }), 404

    privacy_options = session.get(
        "privacy_options",
        []
    )

    if not privacy_options:
        return jsonify({
            "status": "error",
            "message":
                "Creator information must be queried first."
        }), 400

    preferred = "SELF_ONLY"

    if preferred in privacy_options:
        privacy_level = preferred
    else:
        privacy_level = privacy_options[0]

    video_size = os.path.getsize(VIDEO_PATH)

    post_data = {
        "post_info": {
            "title":
                "BackToSchoolAI #BackToSchool #AI",
            "privacy_level":
                privacy_level,
            "disable_duet":
                False,
            "disable_comment":
                False,
            "disable_stitch":
                False,
            "video_cover_timestamp_ms":
                1000
        },
        "source_info": {
            "source":
                "FILE_UPLOAD",
            "video_size":
                video_size,
            "chunk_size":
                video_size,
            "total_chunk_count":
                1
        }
    }

    response = requests.post(
        VIDEO_INIT_URL,
        headers=auth_headers(access_token),
        json=post_data,
        timeout=30
    )

    try:
        init_data = response.json()
    except Exception:
        init_data = {
            "raw_response": response.text
        }

    if response.status_code != 200:
        return jsonify({
            "status": "video_init_error",
            "http_status": response.status_code,
            "response": init_data
        }), 400

    if init_data.get("error", {}).get("code") != "ok":
        return jsonify({
            "status": "video_init_error",
            "response": init_data
        }), 400

    publish_data = init_data.get(
        "data",
        {}
    )

    publish_id = publish_data.get(
        "publish_id"
    )

    upload_url = publish_data.get(
        "upload_url"
    )

    if not publish_id or not upload_url:
        return jsonify({
            "status": "error",
            "message":
                "TikTok did not return an upload URL.",
            "response":
                init_data
        }), 400

    with open(VIDEO_PATH, "rb") as video_file:
        video_bytes = video_file.read()

    upload_response = requests.put(
        upload_url,
        headers={
            "Content-Type": "video/mp4",
            "Content-Length":
                str(video_size),
            "Content-Range":
                f"bytes 0-{video_size - 1}/{video_size}"
        },
        data=video_bytes,
        timeout=120
    )

    if upload_response.status_code not in (
        200,
        201,
        206
    ):
        return jsonify({
            "status": "upload_error",
            "http_status":
                upload_response.status_code,
            "response":
                upload_response.text
        }), 400

    session["publish_id"] = publish_id

    return jsonify({
        "status":
            "video_uploaded_to_tiktok",
        "publish_id":
            publish_id,
        "privacy_level":
            privacy_level,
        "next_step":
            "/status"
    })


@app.route("/status")
def status():

    access_token = session.get("access_token")
    publish_id = session.get("publish_id")

    if not access_token or not publish_id:
        return jsonify({
            "status": "error",
            "message":
                "No active TikTok post."
        }), 400

    response = requests.post(
        STATUS_URL,
        headers=auth_headers(access_token),
        json={
            "publish_id":
                publish_id
        },
        timeout=30
    )

    try:
        data = response.json()
    except Exception:
        data = {
            "raw_response": response.text
        }

    return jsonify(data)


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
        debug=False
    )

