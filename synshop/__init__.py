import stripe, logging, yaml, os
from crypto import SettingsUtil, CryptoUtil

log = logging.getLogger('server.app')

# Load Configuration Variables
try:
    import config
except Exception as e:
    print('ERROR', 'Missing "config.py" file. See https://github.com/synshop/membership.synshop.org for info')
    quit()

# Load Configuration Variables
try:
    ENCRYPTION_KEY = SettingsUtil.EncryptionKey.get()
    stripe.api_key = CryptoUtil.decrypt(config.ENCRYPTED_STRIPE_TOKEN, ENCRYPTION_KEY)
    stripe.api_version = config.STRIPE_VERSION
except Exception as e:
    print('ERROR', 'Failed to decrypt "ENCRYPTED_" config variables in "config.py".  Error was:', e)
    quit()

def load_pricing_map(m=None):
    basedir = os.path.abspath(os.path.dirname(__file__))
    pm_file = basedir + "/" + m

    with open(pm_file,"r") as file:
        x = yaml.safe_load(file)
        
    return x

def freq_decode(f):
    x = {
        "0"     : "free",
        "1"     : "monthly",
        "3"     : "quarterly",
        "6"     : "semiannually",
        "12"    : "yearly"
    }

    return x[str(f)]

def stripe_interval_decode(i=None,i_c=None):
    if i == "month": return i_c
    if i == "year" : return "12"

# Invert a given price_map dictionary
def i_price_map(d=None):
    return {v: k for k, v in d.items()}

# Invert the donation_level dictionary after plucking the
# given "month" sub-dict
def reverse_map_donation_level(d=None, id=None):
    plucked_donation_levels = {v: k for k, v in d.items()}
    return plucked_donation_levels[id]

## Stripe functions

# Raised when the first payment on a new subscription needs the member to
# authenticate (3D Secure); `url` is the Stripe-hosted invoice page where they can
class PaymentActionRequired(Exception):
    def __init__(self, url=None):
        super().__init__(url)
        self.url = url

def create_setup_intent(email=None, customer_id=None):
    # New members don't have a Customer yet, so their SetupIntent has none;
    # the confirmed card is attached when the Customer is created
    try:
        return stripe.SetupIntent.create(
            customer = customer_id,
            payment_method_types = ["card"],
            usage = "off_session",
            metadata = {"email": email}
        )
    except stripe.error.StripeError as e:
        log.info("Unable to create SetupIntent for " + str(email) + ". Error is: " + str(e))
        return None

# Return the card from a SetupIntent the browser confirmed, after checking it
# belongs to this member; the SetupIntent ID comes from the browser, so never trust it
def get_setup_intent_payment_method(setup_intent_id=None, email=None, customer_id=None):
    if not setup_intent_id:
        return None

    try:
        si = stripe.SetupIntent.retrieve(setup_intent_id)
    except stripe.error.StripeError as e:
        log.info("Unable to retrieve SetupIntent " + str(setup_intent_id) + ". Error is: " + str(e))
        return None

    if si.status != "succeeded" or si.metadata.get("email") != email or si.customer != customer_id:
        log.info("SetupIntent " + si.id + " is not usable for " + str(email) + " (status " + si.status + ")")
        return None

    return si.payment_method

# Create a subscription and attempt its first payment right away. Returns the
# subscription, or None if the card was declined (the incomplete subscription
# is deleted so it doesn't linger)
def start_subscription(customer_id=None, items=None):
    s = stripe.Subscription.create(
        customer = customer_id,
        items = items,
        proration_behavior = 'none',
        payment_behavior = 'allow_incomplete',
        expand = ['latest_invoice.payment_intent']
    )

    if s.status != "incomplete" or payment_action_url(s):
        return s

    log.info("First payment failed for " + customer_id + ", deleting incomplete subscription " + s.id)
    stripe.Subscription.delete(s.id)
    return None

# The hosted invoice URL when the subscription's first payment is waiting on 3D Secure
def payment_action_url(s=None):
    pi = s.latest_invoice.payment_intent if s.latest_invoice else None
    if s.status == "incomplete" and pi and pi.status == "requires_action":
        return s.latest_invoice.hosted_invoice_url
    return None

def has_stripe_account(email=None):
    sr=stripe.Customer.search(query='email: "' + email + '"', limit=1)
    return len(sr['data'])

def get_stripe_customer(email=None):
    sr=stripe.Customer.search(query='email: "' + email + '"', limit=1)
    if len(sr['data']) == 0:
        return None
    return sr['data'][0]

def get_default_payment_method(c=None):
    if c['invoice_settings']['default_payment_method'] == None:
        return c['default_source']
    return c['invoice_settings']['default_payment_method']

def is_charter_member(c=None):
    
    if c["discount"] and "coupon" in c['discount']:
        return True
    else:
        return False

def get_member_stripe_account(email=None):

    member = {
        "stripe_id"             : None,
        "email"                 : None,
        "full_name"             : None,
        "discord_id"            : None,
        "payment_method"        : None,
        "payment_brand"         : None,
        "exp_month"             : 0,
        "exp_year"              : 0,
        "last4"                 : 0,
        "membership_fee"        : False,
        "membership_type"       : "standard",
        "locker_fee"            : False,
        "donation_amount"       : 0,
        "payment_freq"          : 0,
        "charter_member"        : False,
        "has_subscription"      : False,
        "subscription_status"   : None,
        "has_payment_method"    : False
    }

    c = get_stripe_customer(email)
    member["stripe_id"] = c['id']
    member["email"] = c['email']
    member["full_name"] = c['name']
    member['payment_method'] = get_default_payment_method(c)

    member["charter_member"] = is_charter_member(c)
    
    if "discord_id" in c['metadata']:
        member["discord_id"] = c['metadata']['discord_id']

    subs = get_current_subscription_plan(c)

    member["membership_fee"] = subs["membership_fee"]
    member["membership_type"] = subs["membership_type"]
    member["locker_fee"] = subs["locker_fee"]
    member["donation_amount"] = subs["donation_amount"]
    member["payment_freq"] = subs["payment_freq"]
    member["has_subscription"] = subs["has_subscription"]
    member["subscription_status"] = subs["subscription_status"]

    # A customer without a subscription may not have a card on file either
    if member["payment_method"] is None:
        return member

    try:
        paymentMethod = stripe.Customer.retrieve_payment_method(member["stripe_id"],member["payment_method"])
        if paymentMethod["type"] == "card":
            member["payment_brand"] = paymentMethod["card"]["brand"]
            member["exp_month"] = paymentMethod["card"]["exp_month"]
            member["exp_year"] = paymentMethod["card"]["exp_year"]
            member["last4"] = paymentMethod["card"]["last4"]
            member["has_payment_method"] = True
    except stripe.error.StripeError as e:
        log.info("Unable to retrieve payment method for " + member["full_name"] + " Stripe ID: " + member["stripe_id"] + ". Error is: " + str(e))

    if not member["has_payment_method"]:
        member["payment_method"] = None

    return member

def create_new_member(user=None):

    locker_fee = False
    donation_amount = user["donationRadio"]
    payment_freq = user["payFreqRadio"]
    
    if user["membershipRadio"] == "m+l":
        locker_fee = True

    pm = get_setup_intent_payment_method(user.get("setupIntentId"), user["email"])
    if pm is None:
        return False

    try:

        sc = stripe.Customer.create(
            email = user["email"],
            name = user["fullName"],
            metadata = {
                'discord_id': user["discordId"],
            },
            payment_method = pm,
            invoice_settings = {
                'default_payment_method': pm
            }
        )
        
        log.info("Creating new member account " + sc.id)

        # A declined card leaves the Customer without a subscription; the
        # member can add a new card from /update
        s = start_subscription(sc.id, build_subscription_plan(locker_fee, donation_amount, payment_freq))
        if s is None:
            return False

        url = payment_action_url(s)
        if url:
            raise PaymentActionRequired(url)

        return True
    except PaymentActionRequired:
        raise
    except Exception as e:
        log.info(e)
        return False

def update_member_stripe_account(user=None):

    member = {
        "stripe_id"                 : None,
        "email"                     : None,
        "full_name"                 : None,
        "discord_id"                : None,
        "current_payment_method"    : None,
        "locker_fee"                : False,
        "donation_amount"           : 0,
        "payment_freq"              : 0,
        "card_number"               : None,
        "exp_month"                 : 0,
        "exp_year"                  : 0,
        "page_is_dirty"             : None,
        "membership_fees"           : None
    }

    member["stripe_id"] = user["stripeId"]
    member["email"] = user["email"]
    member["full_name"] = user["fullName"]
    member["discord_id"] = user["discordId"]
    member["current_payment_method"] = user["currentPaymentMethod"]
    member["page_is_dirty"] = user["pageIsDirty"]
    member["membership_fees"] = user.get("membershipRadio")

    if member["membership_fees"] == "m+l":
        member["locker_fee"] = True

    if "payFreqRadio" in user:
        member["payment_freq"] = user["payFreqRadio"]

    if "donationRadio" in user:
        if user["donationRadio"] != "0":
            member["donation_amount"] = user["donationRadio"]
    
    # Always update customer metadata (Full Name, DiscordID)
    # regardless of what the status of is_page_dirty is
    try:
        stripe.Customer.modify(
            member["stripe_id"],
            name = member["full_name"],
            metadata = {'discord_id': member["discord_id"]}
        )
    except Exception as e:
        log.info(e)

    has_payment_method = bool(member["current_payment_method"])

    if user["deleteCurrentPaymentMethod"] == "1" and not user.get("setupIntentId"):

        # Canceled members may remove their card without replacing it
        if member["membership_fees"] != "c":
            log.info("Member " + member["full_name"] + " Stripe ID: " + member["stripe_id"] + " tried to remove their card without canceling")
            return False

        try:
            if member["current_payment_method"]:
                stripe.PaymentMethod.detach(member["current_payment_method"])
            has_payment_method = False
            log.info("Removed payment method for member account  " + member["full_name"] + " Stripe ID: " + member["stripe_id"] )
        except Exception as e:
            log.info(e)
            return False

    elif user["deleteCurrentPaymentMethod"] == "1":

        # Member adds a new card. The browser already confirmed a SetupIntent
        # (running 3D Secure if the bank asked), which attached the card, so:
        #   1) get the new PaymentMethod from the SetupIntent
        #   2) set new PaymentMethod as Customer default
        #   3) detach the old PaymentMethod, if there was one

        pm = get_setup_intent_payment_method(user.get("setupIntentId"), member["email"], member["stripe_id"])
        if pm is None:
            return False

        try:
            stripe.Customer.modify(
                member["stripe_id"],
                invoice_settings = {"default_payment_method" : pm}
            )
            has_payment_method = True

            if member["current_payment_method"]:
                stripe.PaymentMethod.detach(member["current_payment_method"])

        except Exception as e:
            log.info(e)
            return False

    # Update Subscriptions if necessary
    if member["page_is_dirty"] == "1":

        try:
            # Canceled members keep their Stripe customer, just no subscription
            if member["membership_fees"] == "c":
                cancel_current_subscription_plan(member["stripe_id"])
                log.info("Canceled subscription for member account  " + member["full_name"] + " Stripe ID: " + member["stripe_id"])
                return True

            if member["membership_fees"] not in ("m", "m+l"):
                log.info("Member account " + member["stripe_id"] + " sent an invalid membership plan: " + str(member["membership_fees"]))
                return False

            # Paid plans need a card; check before touching the current
            # subscription so a failed change doesn't leave the member without one
            if not has_payment_method:
                log.info("Member  " + member["full_name"] + " Stripe ID: " + member["stripe_id"] + " has no payment method, not creating a subscription")
                return False

            # Free memberships are granted by the board, never selected from the form
            if str(member["payment_freq"]) not in ("1", "3", "6", "12"):
                log.info("Member account  " + member["full_name"] + " Stripe ID: " + member["stripe_id"] + " sent an invalid payment frequency: " + str(member["payment_freq"]))
                return False

            sp = build_subscription_plan(
                locker_fee=member["locker_fee"],
                donation_amount=member["donation_amount"],
                payment_freq=member["payment_freq"]
            )

            # Start the new subscription before canceling the old one, so a
            # declined card leaves the member on their current plan
            s = start_subscription(member["stripe_id"], sp)
            if s is None:
                return False

            cancel_current_subscription_plan(member["stripe_id"], keep=s.id)

            log.info("Updating Stripe information for member account " + member["stripe_id"])

            url = payment_action_url(s)
            if url:
                raise PaymentActionRequired(url)
        except PaymentActionRequired:
            raise
        except Exception as e:
            log.info(e)
            return False

    return True

def delete_membership(id):
    try:
        log.info("Deleting member account " + id)
        stripe.Customer.delete(id)
        log.info("Member account deleted successfully")
        return True
    except:
        return False
    
def build_subscription_plan(locker_fee=False,donation_amount=0,payment_freq=1):

    pricing_map = load_pricing_map(config.PRICING_MAP)

    s_list = []
    fd = freq_decode(payment_freq)
    
    # Add a membership fee product
    mf = {"price": pricing_map["membership_fees"][fd]}
    s_list.append(mf)

    # Add a locker fee product if selected
    if locker_fee:
        lf = {"price": pricing_map["locker_fees"][fd]}
        s_list.append(lf)
    
    # Add a donation amount product if selected
    if int(donation_amount) != 0:
        da = {"price": pricing_map["donation_levels"][fd][donation_amount]}
        s_list.append(da)
    
    return s_list

def get_current_subscription_plan(c=None):

    subscriptions = {
        "membership_fee"    : False,
        "membership_type"   : "standard",
        "locker_fee"        : False,
        "donation_amount"   : 0,
        "payment_freq"      : 1,
        "has_subscription"  : False,
        "subscription_status" : None
    }
    try:
        # Subscription.list omits canceled subscriptions by default
        stripe_subscriptions=stripe.Subscription.list(customer=c['id'], limit=100)

        if len(stripe_subscriptions.data) == 0:
            log.info("The member " + c['id'] + " does not have an active subscription")
            return subscriptions

        subscriptions["has_subscription"] = True
        subscriptions["subscription_status"] = stripe_subscriptions.data[0]["status"]

        p = stripe_subscriptions.data[0]["items"]["data"]
        i = stripe_subscriptions.data[0]["items"]["data"][0]["price"]["recurring"]["interval"]
        i_c = stripe_subscriptions.data[0]["items"]["data"][0]["price"]["recurring"]["interval_count"]
        payment_freq = stripe_interval_decode(i,i_c)
        d_freq = freq_decode(payment_freq)

        subscriptions["payment_freq"] = payment_freq

        pricing_map = load_pricing_map(config.PRICING_MAP)

        for x in p:

            id = x["plan"]["id"]

            if "membership_fee" in x["price"]["metadata"]["type"]:
                subscriptions["membership_fee"] = True

                if i_price_map(pricing_map["membership_fees"])[id] == "free":
                    subscriptions["membership_type"] = "free"
            
            if "locker_fee" in x["price"]["metadata"]["type"]:
                subscriptions["locker_fee"] = True

            if "donation" in x["price"]["metadata"]["type"]:
                subscriptions["donation_amount"] = reverse_map_donation_level(pricing_map["donation_levels"][d_freq],id)
            
    except (IndexError, KeyError, TypeError, stripe.error.StripeError) as e:
        # Prices missing from the pricing map, or without a metadata "type",
        # shouldn't take down the update page
        log.info("Unable to decode subscription for member " + c['id'] + ": " + repr(e))

    return subscriptions

def cancel_current_subscription_plan(c=None, keep=None):

    try:
        for s in stripe.Subscription.list(customer=c, limit=10):
            if s.id == keep:
                continue
            print("canceling current subscriptions...")
            stripe.Subscription.delete(s.id, prorate=False)
    except Exception as e:
        log.info(e)
        pass
 