
from functools import wraps
import json, logging

from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import OAuthError

from flask import Flask, redirect, render_template, request, session, url_for
from crypto import SettingsUtil, CryptoUtil
from synshop import get_subscriptions_for_member

app = Flask(__name__) 

# Load Configuration Variables
try:
    import config
except Exception as e:
    print('ERROR', 'Missing "config.py" file. See https://github.com/synshop/membership.synshop.org for info')
    quit()

# Load Plaintext Configuration Variables
app.config['AUTH0_CLIENT_ID'] = config.AUTH0_CLIENT_ID
app.config['AUTH0_DOMAIN'] = config.AUTH0_DOMAIN
app.config['LOG_FILE'] = config.LOG_FILE
app.config['LOGOUT_REDIRECT_URL'] = config.LOGOUT_REDIRECT_URL
app.config['NEW_USER_MEMBERSHIP_FEE'] = config.NEW_USER_MEMBERSHIP_FEE
app.config['NEW_USER_LOCKER_FEE'] = config.NEW_USER_LOCKER_FEE

# Load Encrypted Configuration Variables
try:
    ENCRYPTION_KEY = SettingsUtil.EncryptionKey.get()
    app.secret_key = CryptoUtil.decrypt(config.ENCRYPTED_SESSION_KEY, ENCRYPTION_KEY)
    app.config['AUTH0_CLIENT_SECRET'] = CryptoUtil.decrypt(config.ENCRYPTED_AUTH0_CLIENT_SECRET, ENCRYPTION_KEY)
except Exception as e:
    print('ERROR', 'Failed to decrypt "ENCRYPTED_" config variables in "config.py".  Error was:', e)
    quit()

# Logging
file_handler = logging.FileHandler(app.config['LOG_FILE'])
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
file_handler.setLevel(logging.INFO)
app.logger.setLevel(logging.INFO)
app.logger.addHandler(file_handler)

app.logger.info("-------------------------------------")
app.logger.info("SYN Shop Membership System Started...")
app.logger.info("-------------------------------------")

# Decorator for Required Auth
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user') is None:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function

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

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/callback", methods=["GET", "POST"])
def callback():
    try:
        token = oauth.auth0.authorize_access_token()
        session["user"] = token
        action = request.args.get('s')

        if action == "new":
            return redirect(url_for("new_user"))
        else:
            return redirect(url_for("update_user"))

    except OAuthError:
        return render_template("validate.html")

@app.route("/login")
def login():
    redirect_uri=url_for("callback", s="existing", _external=True)
    return oauth.auth0.authorize_redirect(redirect_uri)

@app.route("/signup")
def signup():
    redirect_uri=url_for("callback", s="new", _external=True)
    return oauth.auth0.authorize_redirect(redirect_uri,screen_hint='signup')

@app.route("/logout")
def logout():
    session.clear()
    return redirect(app.config['LOGOUT_REDIRECT_URL'])

@login_required
@app.route("/new")
def new_user():
    mf=app.config["NEW_USER_MEMBERSHIP_FEE"]
    lf=app.config["NEW_USER_LOCKER_FEE"]
    return render_template("new_user.html",session=session.get("user"),mf=mf,lf=lf)

@login_required
@app.route("/update")
def update_user():
    mf=app.config["NEW_USER_MEMBERSHIP_FEE"]
    lf=app.config["NEW_USER_LOCKER_FEE"]
    return render_template("update_user.html",session=session.get("user"),mf=mf,lf=lf)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
