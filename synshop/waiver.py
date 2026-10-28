import hashlib, os
from datetime import date, datetime, timezone

# The waiver text lives in synshop/waivers/<WAIVER_VERSION>.txt and must match
# the board-approved paper waiver word for word. To publish a new version, add
# a new file and bump WAIVER_VERSION; never edit a published version in place.
WAIVER_VERSION = "member_waiver_v1"
MINIMUM_AGE = 18

# Stripe metadata values are limited to 500 characters
METADATA_VALUE_MAX = 500

_waiver_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), "waivers", WAIVER_VERSION + ".txt")

with open(_waiver_file, "rb") as file:
    _waiver_bytes = file.read()

WAIVER_SHA256 = hashlib.sha256(_waiver_bytes).hexdigest()
WAIVER_TITLE, *WAIVER_PARAGRAPHS = [p.strip() for p in _waiver_bytes.decode("utf-8").split("\n\n") if p.strip()]

def parse_dob(s=None):
    try:
        return date.fromisoformat((s or "").strip())
    except ValueError:
        return None

def age_on(dob=None, today=None):
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

# Server-side check of the waiver fields posted with /new. Returns a list of
# problems; an empty list means the waiver was signed correctly.
def validate_waiver_form(form=None, today=None):
    today = today or date.today()
    errors = []

    if form.get("waiverVersion") != WAIVER_VERSION or form.get("waiverSha256") != WAIVER_SHA256:
        errors.append("The waiver has been updated since this page was loaded. Please review the current waiver and sign again.")

    if form.get("waiverConsent") != "1":
        errors.append("You must consent to signing electronically.")

    if form.get("waiverAgree") != "1":
        errors.append("You must agree to the liability waiver.")

    if not form.get("waiverSignature", "").strip():
        errors.append("You must type your full legal name as your signature.")

    dob = parse_dob(form.get("waiverDob"))
    if dob is None or dob > today or age_on(dob, today) > 120:
        errors.append("Please enter a valid date of birth.")
    elif age_on(dob, today) < MINIMUM_AGE:
        errors.append("Members under 18 can't sign online. Please bring the paper waiver, signed by a parent or guardian, to the shop.")

    return errors

# Build the Stripe Customer metadata that records who signed which waiver, and when
def build_waiver_metadata(form=None, auth0_sub=None, ip=None, user_agent=None, signed_at=None):
    signed_at = signed_at or datetime.now(timezone.utc)

    metadata = {
        'waiver_version': WAIVER_VERSION,
        'waiver_sha256': WAIVER_SHA256,
        'waiver_signed_at': signed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        'waiver_signed_name': form["waiverSignature"].strip(),
        'waiver_dob': parse_dob(form["waiverDob"]).isoformat(),
        'waiver_esign_consent': 'true',
        'waiver_auth0_sub': auth0_sub or '',
        'waiver_signed_ip': ip or '',
        'waiver_user_agent': user_agent or '',
    }

    return {k: v[:METADATA_VALUE_MAX] for k, v in metadata.items()}

# True if the Customer metadata shows the member signed the waiver that is
# current now. Publishing a new waiver version asks every member to sign again.
def has_signed_current_waiver(metadata=None):
    metadata = metadata or {}
    return metadata.get('waiver_version') == WAIVER_VERSION and metadata.get('waiver_sha256') == WAIVER_SHA256
