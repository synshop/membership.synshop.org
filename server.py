"""Python Flask WebApp Auth0 integration example
"""

import json
from os import environ as env
from urllib.parse import quote_plus, urlencode

from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import OAuthError

from flask import Flask, redirect, render_template, session, url_for
from crypto import SettingsUtil, CryptoUtil

try:
    import config
except Exception as e:
    print('ERROR', 'Missing "config.py" file. See https://github.com/synshop/membership.synshop.org for info')
    quit()

RUN_MODE = 'development'

ENCRYPTION_KEY = SettingsUtil.EncryptionKey.get(RUN_MODE == 'development')

app = Flask(__name__)

# Decrypt Configuration Variables
try:
    app.secret_key = CryptoUtil.decrypt(config.ENCRYPTED_SESSION_KEY, ENCRYPTION_KEY)
    app.config['AUTH0_CLIENT_SECRET'] = CryptoUtil.decrypt(config.ENCRYPTED_AUTH0_CLIENT_SECRET, ENCRYPTION_KEY)
except Exception as e:
    print('ERROR', 'Failed to decrypt "ENCRYPTED_" config variables in "config.py".  Error was:', e)
    quit()

# Load Plaintext Configuration Variables
app.config['AUTH0_CLIENT_ID'] = config.AUTH0_CLIENT_ID
app.config['AUTH0_DOMAIN'] = config.AUTH0_DOMAIN

oauth = OAuth(app)

oauth.register(
    "auth0",
    client_id=app.config['AUTH0_CLIENT_ID'],
    client_secret=app.config['AUTH0_CLIENT_SECRET'],
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{app.config["AUTH0_DOMAIN"]}/.well-known/openid-configuration',
)


# Controllers API
@app.route("/")
def home():
    return render_template(
        "home.html",
        session=session.get("user"),
        pretty=json.dumps(session.get("user"), indent=4),
    )


@app.route("/callback", methods=["GET", "POST"])
def callback():
    try:
        token = oauth.auth0.authorize_access_token()
        session["user"] = token
        return redirect("/")
    except OAuthError:
        return render_template("validate.html")



@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://"
        + app.config['AUTH0_DOMAIN']
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("home", _external=True),
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=env.get("PORT", 8000))
