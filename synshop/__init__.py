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
        "99"    : "paused",
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
        "is_paused"             : False,
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
    member["is_paused"] = subs["is_paused"]
    member["has_subscription"] = subs["has_subscription"]
    member["subscription_status"] = subs["subscription_status"]

    # A customer without a subscription may not have a card on file either
    if member["payment_method"] is None:
        return member

    try:
        x = stripe.Customer.retrieve_payment_method(member["stripe_id"],member["payment_method"])
        if x["type"] == "card":
            member["payment_brand"] = x["card"]["brand"]
            member["exp_month"] = x["card"]["exp_month"]
            member["exp_year"] = x["card"]["exp_year"]
            member["last4"] = x["card"]["last4"]
            member["has_payment_method"] = True
    except stripe.error.StripeError as e:
        log.info("Unable to retrieve payment method for " + member["stripe_id"] + ": " + str(e))

    if not member["has_payment_method"]:
        member["payment_method"] = None

    return member

def create_new_member(user=None):

    locker_fee = False
    is_paused = False
    donation_amount = user["donationRadio"]
    payment_freq = user["payFreqRadio"]
    
    if user["membershipRadio"] == "m+l":
        locker_fee = True

    real_card = {"token" : user["stripeToken"]}

    try:

        pm = stripe.PaymentMethod.create(type="card",card=real_card)
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
        
        stripe.Subscription.create(
            customer = sc.id,
            items = build_subscription_plan(locker_fee, donation_amount, payment_freq, is_paused),
            proration_behavior = 'none'
        )

        log.info("Creating new member account " + sc.id)
        return True
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
        "is_paused"                 : False,
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
    member["membership_fees"] = user["membershipRadio"]

    if member["membership_fees"] == "p":
        member["is_paused"] = True
    
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

    if user["deleteCurrentPaymentMethod"] == "1" and not user.get("stripeToken"):

        # Canceled members may remove their card without replacing it
        if member["membership_fees"] != "c":
            log.info("Member account " + member["stripe_id"] + " tried to remove their card without canceling")
            return False

        try:
            if member["current_payment_method"]:
                stripe.PaymentMethod.detach(member["current_payment_method"])
            has_payment_method = False
            log.info("Removed payment method for member account " + member["stripe_id"])
        except Exception as e:
            log.info(e)
            return False

    elif user["deleteCurrentPaymentMethod"] == "1":

        # Member adds a new card:
        #   1) create a new PaymentMethod
        #   2) attach it to the Stripe Customer
        #   3) set new PaymentMethod as Customer default
        #   4) detach the old PaymentMethod, if there was one

        try:
            real_card = {"token" : user["stripeToken"]}
            pm = stripe.PaymentMethod.create(type="card",card=real_card)
            x = stripe.PaymentMethod.attach(pm,customer=member["stripe_id"])

            stripe.Customer.modify(
                member["stripe_id"],
                invoice_settings = {"default_payment_method" : x}
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
                log.info("Canceled subscription for member account " + member["stripe_id"])
                return True

            # Paid plans need a card; check before touching the current
            # subscription so a failed change doesn't leave the member without one
            if not member["is_paused"] and not has_payment_method:
                log.info("Member account " + member["stripe_id"] + " has no payment method, not creating a subscription")
                return False

            # Free memberships are granted by the board, never selected from the form
            if not member["is_paused"] and str(member["payment_freq"]) not in ("1", "3", "6", "12"):
                log.info("Member account " + member["stripe_id"] + " sent an invalid payment frequency: " + str(member["payment_freq"]))
                return False

            sp = build_subscription_plan(
                locker_fee=member["locker_fee"],
                donation_amount=member["donation_amount"],
                payment_freq=member["payment_freq"],
                is_paused=member["is_paused"]
            )

            cancel_current_subscription_plan(member["stripe_id"])

            stripe.Subscription.create(
                customer = member["stripe_id"],
                items = sp,
                proration_behavior = 'none'
            )

            log.info("Updating Stripe information for member account " + member["stripe_id"])
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
    
def build_subscription_plan(locker_fee=False,donation_amount=0,payment_freq=1,is_paused=False):

    pricing_map = load_pricing_map(config.PRICING_MAP)

    if (is_paused):
        mf = {"price": pricing_map["membership_fees"]["paused"]}
        return [mf,]

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
        "is_paused"         : False,
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

                if i_price_map(pricing_map["membership_fees"])[id] == "paused":
                    subscriptions["is_paused"] = True

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

def cancel_current_subscription_plan(c=None):

    try:
        for s in stripe.Subscription.list(customer=c, limit=10):
            print("canceling current subscriptions...")
            stripe.Subscription.delete(s.id, prorate=False)
    except Exception as e:
        log.info(e)
        pass
 