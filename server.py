
from functools import wraps
import logging

from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import OAuthError

from flask import Flask, redirect, render_template, request, session, url_for, flash
from crypto import SettingsUtil, CryptoUtil
from synshop import has_stripe_account, create_new_member, get_member_stripe_account, update_member_stripe_account, delete_membership

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
app.config['ROOT_SERVER_URL'] = config.ROOT_SERVER_URL
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
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(message)s'))
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
            return redirect(url_for("index"))
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
    return render_template("index.html", root_server_url=app.config['ROOT_SERVER_URL'])

@app.route("/callback", methods=["GET", "POST"])
def callback():
    try:
        token = oauth.auth0.authorize_access_token()
        session["user"] = token
        email = token['userinfo']['email']

        if has_stripe_account(email) == 1:
            app.logger.info("CB - This email address was found in Stripe, redirecting to /update...")
            return redirect(url_for("update_user"))
        else:
            app.logger.info("CB - This email address was not found in Stripe, redirecting to /new...")
            session["auth0-no-stripe"] = True
            return redirect(url_for("new_user"))

    except OAuthError as e:
        app.logger.info(e)
        return render_template("validate.html")

@app.route("/login")
def login():
    redirect_uri=url_for("callback", _external=True)
    return oauth.auth0.authorize_redirect(redirect_uri)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(app.config['LOGOUT_REDIRECT_URL'])

@app.route("/signup")
def signup():
    redirect_uri=url_for("callback", _external=True)
    return oauth.auth0.authorize_redirect(redirect_uri,screen_hint='signup')

@app.route("/new", methods=['GET', 'POST'])
@login_required
def new_user():

    email = session["user"]["userinfo"]["email"]

    if has_stripe_account(email) == 1:
        app.logger.info("This email address ("+ email +") was found in Stripe, redirecting to /update...")
        return redirect(url_for("update_user"))

    if request.method == 'GET':

        if "auth0-no-stripe" in session:
            flash("Auth0, no Stripe")

        mf=app.config["NEW_USER_MEMBERSHIP_FEE"]
        lf=app.config["NEW_USER_LOCKER_FEE"]
        return render_template("new_user.html", email=email, mf=mf, lf=lf, root_server_url=app.config['ROOT_SERVER_URL'])
    else:
        create_new_member(request.form.to_dict())
        app.logger.info("New user ("+ email +") has been created in Stripe for /new...")
        return redirect(url_for("welcome_user"))

@app.route("/update", methods=['GET', 'POST'])
@login_required
def update_user():
    mf=app.config["NEW_USER_MEMBERSHIP_FEE"]
    lf=app.config["NEW_USER_LOCKER_FEE"]

    email = session["user"]["userinfo"]["email"]
    
    if request.method == 'GET':
         if has_stripe_account(email) == 1:
            app.logger.info("Fetching user info for ("+ email +") from Stripe for /update...")
         else:
             app.logger.info("User ("+ email +") has a Auth0 account but was not found in Stripe, redirecting to /new")
             flash("new stripe user")
             return redirect(url_for('new_user', email=email, mf=mf, lf=lf))
             
    if request.method == 'POST':
        
        if "reallyDeleteMembership" in request.form:
            if request.form["reallyDeleteMembership"] == "1":
                stripe_id = request.form['stripeId']
                delete_membership(stripe_id)
                app.logger.info("Deleting user ("+ email +") from Stripe...")
                return redirect(url_for('delete_user'))

        app.logger.info("Updating user ("+ email +") info in Stripe...")
        update_member_stripe_account(request.form.to_dict())
        flash("Your information has been updated successfully")

    member = get_member_stripe_account(email)
    return render_template(
        "update_user.html", 
        email=email, 
        mf=mf, lf=lf, 
        member=member,
        root_server_url=app.config['ROOT_SERVER_URL'])

@app.route("/welcome", methods=['GET'])
@login_required
def welcome_user():
    return render_template("welcome.html", root_server_url=app.config['ROOT_SERVER_URL'])

@app.route("/delete")
def delete_user():
    return render_template("deleted.html", root_server_url=app.config['ROOT_SERVER_URL'])

if __name__ == "__main__":
    app.run(host="::", port=8000, debug=True)
