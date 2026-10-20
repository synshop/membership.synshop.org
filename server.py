
from functools import wraps
import logging

from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import OAuthError

from flask import Flask, redirect, render_template, request, session, url_for, flash
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from crypto import SettingsUtil, CryptoUtil
from synshop import has_stripe_account, create_new_member, get_member_stripe_account, update_member_stripe_account, delete_membership, get_stripe_customer, get_default_payment_method, record_waiver
from synshop.waiver import WAIVER_VERSION, WAIVER_SHA256, WAIVER_TITLE, WAIVER_PARAGRAPHS, validate_waiver_form, build_waiver_metadata, has_signed_current_waiver

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
app.config['STRIPE_PK'] = config.STRIPE_PK

# Session Cookie / CSRF Protection
# SESSION_COOKIE_SECURE requires HTTPS; set it to False in config.py for plain http://localhost development
app.config['SESSION_COOKIE_SECURE'] = getattr(config, 'SESSION_COOKIE_SECURE', True)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['WTF_CSRF_TIME_LIMIT'] = None

# Behind a reverse proxy (Caddy in production), trust X-Forwarded-For from that
# many proxies so request.remote_addr is the member's IP, not the proxy's
TRUSTED_PROXY_COUNT = getattr(config, 'TRUSTED_PROXY_COUNT', 0)
if TRUSTED_PROXY_COUNT > 0:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=TRUSTED_PROXY_COUNT)

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

csrf = CSRFProtect(app)

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

def render_waiver_gate(email=None, customer=None):
    return render_template(
        "sign_waiver.html",
        email=email,
        resign='waiver_version' in customer['metadata'],
        root_server_url=app.config['ROOT_SERVER_URL'],
        waiver_version=WAIVER_VERSION,
        waiver_sha256=WAIVER_SHA256,
        waiver_title=WAIVER_TITLE,
        waiver_paragraphs=WAIVER_PARAGRAPHS)

@app.route("/")
def index():
    return render_template("index.html", root_server_url=app.config['ROOT_SERVER_URL'])

# Auth0 redirects here; the OAuth state parameter already protects this route
@app.route("/callback", methods=["GET", "POST"])
@csrf.exempt
def callback():
    try:
        token = oauth.auth0.authorize_access_token()
        session["user"] = token
        email = token['userinfo']['email']

        if has_stripe_account(email) == 1:
            app.logger.info(f'CB - {email} was found in Stripe, redirecting to /update...')
            return redirect(url_for("update_user"))
        else:
            app.logger.info(f'CB - {email} was NOT found in Stripe, redirecting to /new...')
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
        app.logger.info(f'{email} was found in Stripe, redirecting to /update...')
        return redirect(url_for("update_user"))

    if request.method == 'GET':

        if "auth0-no-stripe" in session:
            flash("Auth0, no Stripe")

        mf=app.config["NEW_USER_MEMBERSHIP_FEE"]
        lf=app.config["NEW_USER_LOCKER_FEE"]
        pk=app.config["STRIPE_PK"]
        return render_template(
            "new_user.html",
            email=email,
            mf=mf, lf=lf,
            root_server_url=app.config['ROOT_SERVER_URL'],
            stripe_pk=pk,
            waiver_version=WAIVER_VERSION,
            waiver_sha256=WAIVER_SHA256,
            waiver_title=WAIVER_TITLE,
            waiver_paragraphs=WAIVER_PARAGRAPHS)
    else:
        # Use the verified Auth0 email, not the one posted by the browser
        form = request.form.to_dict()
        form['email'] = email

        # Check the waiver before creating anything in Stripe, so nobody is
        # billed without a signed waiver
        waiver_errors = validate_waiver_form(form)
        if waiver_errors:
            app.logger.info(f'{email} POSTed to /new with an invalid waiver: {waiver_errors}')
            for e in waiver_errors:
                flash(e, "waiver")
            return redirect(url_for("new_user"))

        waiver_metadata = build_waiver_metadata(
            form,
            auth0_sub=session["user"]["userinfo"].get("sub"),
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"))

        create_new_member(form, waiver_metadata)
        app.logger.info(f'{email} signed waiver {WAIVER_VERSION} at {waiver_metadata["waiver_signed_at"]} from {waiver_metadata["waiver_signed_ip"]}')
        app.logger.info(f'{email} has been created in Stripe for /new...')
        return redirect(url_for("welcome_user"))

@app.route("/update", methods=['GET', 'POST'])
@login_required
def update_user():
    mf=app.config["NEW_USER_MEMBERSHIP_FEE"]
    lf=app.config["NEW_USER_LOCKER_FEE"]
    pk=app.config["STRIPE_PK"]

    email = session["user"]["userinfo"]["email"]
    
    if request.method == 'GET':
         customer = get_stripe_customer(email)
         if customer is not None:
            # Members must sign the current waiver before anything else on /update
            if not has_signed_current_waiver(customer['metadata']):
                app.logger.info(f'{email} has not signed waiver {WAIVER_VERSION}, showing the waiver gate')
                return render_waiver_gate(email, customer)
            app.logger.info(f'Fetching user info for {email} from Stripe for /update...')
         else:
             app.logger.info(f'{email} has an Auth0 account but was NOT found in Stripe, redirecting to /new')
             flash("new stripe user")
             return redirect(url_for('new_user', email=email, mf=mf, lf=lf, stripe_pk=pk))
             
    if request.method == 'POST':

        # Never trust the Stripe IDs posted by the browser; always act on
        # the customer that belongs to the logged-in user's email.
        customer = get_stripe_customer(email)
        if customer is None:
            app.logger.info(f'{email} POSTed to /update but was NOT found in Stripe, redirecting to /new')
            return redirect(url_for('new_user'))

        if not has_signed_current_waiver(customer['metadata']):
            app.logger.info(f'{email} POSTed to /update without signing waiver {WAIVER_VERSION}, redirecting to the waiver gate')
            return redirect(url_for('update_user'))

        form = request.form.to_dict()
        form['email'] = email
        form['stripeId'] = customer['id']
        form['currentPaymentMethod'] = get_default_payment_method(customer)

        if form.get("reallyDeleteMembership") == "1":
            app.logger.info(f'Deleting {email} from Stripe...')
            delete_membership(customer['id'])
            return redirect(url_for('delete_user'))

        app.logger.info(f'Updating info for {email} in Stripe...')
        if update_member_stripe_account(form):
            flash("Your information has been updated successfully", "success")
        else:
            app.logger.info(f'Update for {email} did not complete')
            flash("We couldn't update your membership. Please check your payment information, or contact support@synshop.org.", "error")

    member = get_member_stripe_account(email)
    return render_template(
        "update_user.html", 
        email=email, 
        mf=mf, lf=lf, 
        member=member,
        stripe_pk=pk,
        root_server_url=app.config['ROOT_SERVER_URL'])

# Existing members sign the waiver here, from the gate shown by /update
@app.route("/waiver", methods=['POST'])
@login_required
def sign_waiver():
    email = session["user"]["userinfo"]["email"]

    # Never trust the Stripe IDs posted by the browser
    customer = get_stripe_customer(email)
    if customer is None:
        app.logger.info(f'{email} POSTed to /waiver but was NOT found in Stripe, redirecting to /new')
        return redirect(url_for('new_user'))

    form = request.form.to_dict()
    waiver_errors = validate_waiver_form(form)
    if waiver_errors:
        app.logger.info(f'{email} POSTed to /waiver with an invalid waiver: {waiver_errors}')
        for e in waiver_errors:
            flash(e, "waiver")
        return redirect(url_for('update_user'))

    waiver_metadata = build_waiver_metadata(
        form,
        auth0_sub=session["user"]["userinfo"].get("sub"),
        ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"))

    if record_waiver(customer['id'], waiver_metadata):
        app.logger.info(f'{email} signed waiver {WAIVER_VERSION} at {waiver_metadata["waiver_signed_at"]} from {waiver_metadata["waiver_signed_ip"]}')
    else:
        app.logger.info(f'Recording waiver {WAIVER_VERSION} for {email} FAILED')
        flash("We couldn't save your signed waiver. Please try again, or contact support@synshop.org.", "waiver")

    return redirect(url_for('update_user'))

@app.route("/welcome", methods=['GET'])
@login_required
def welcome_user():
    return render_template("welcome.html", root_server_url=app.config['ROOT_SERVER_URL'])

@app.route("/delete")
def delete_user():
    return render_template("deleted.html", root_server_url=app.config['ROOT_SERVER_URL'])

if __name__ == "__main__":
    # Serve HTTPS locally when a dev cert is configured (see README)
    ssl_context = None
    if getattr(config, 'DEV_SSL_CERT', None) and getattr(config, 'DEV_SSL_KEY', None):
        ssl_context = (config.DEV_SSL_CERT, config.DEV_SSL_KEY)

    app.run(host="::", port=8000, debug=True, ssl_context=ssl_context)
