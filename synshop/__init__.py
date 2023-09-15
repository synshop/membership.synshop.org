import stripe, time, logging
from crypto import SettingsUtil, CryptoUtil
import synshop.pricing_map as pricing

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
    is_dev = config.IS_DEV
except Exception as e:
    print('ERROR', 'Failed to decrypt "ENCRYPTED_" config variables in "config.py".  Error was:', e)
    quit()

## Stripe functions

def has_stripe_account(email=None):
    sr=stripe.Customer.search(query='email: "' + email + '"', limit=1)
    return len(sr['data'])

def is_charter_member(c=None):
    
    if c["discount"] and "coupon" in c['discount']:
        return True
    else:
        return False
    
def create_new_member(user=None):

    locker_fee = False
    donation_amount = user["donationRadio"]
    payment_freq = user["payFreqRadio"]

    if "lockerFeeChk" in user:
        locker_fee = True
    
    real_card = {
        "number": user["card-number"].replace(" ",""),
        "exp_month": user["expiry-month"],
        "exp_year": user["expiry-year"],
        "cvc": user["cvc"]
    }

    try:

        if (is_dev):
            pm = "pm_card_visa"      
        else:
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
            items = build_subscription_plan(locker_fee, donation_amount, payment_freq, False)
        )

        return True
    except Exception as e:
        log.info(e)
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
        "is_paused"             : False
    }

    c = stripe.Customer.search(query='email: "' + email + '"', limit=1)['data'][0]
    member["stripe_id"] = c['id']
    member["email"] = c['email']
    member["full_name"] = c['name']
    member['payment_method'] = c['invoice_settings']['default_payment_method']
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
    
    x = stripe.Customer.retrieve_payment_method(member["stripe_id"],member["payment_method"])
    
    member["payment_brand"] = x["card"]["brand"]
    member["exp_month"] = x["card"]["exp_month"]
    member["exp_year"] = x["card"]["exp_year"]
    member["last4"] = x["card"]["last4"]

    return member

def build_subscription_plan(locker_fee=False,donation_amount=0,payment_freq=1,is_paused=False):

    if (is_paused):
        mf = {"price": pricing.membership_fees["paused"]}
        return [mf,]

    s_list = []
    fd = pricing.freq_decode(payment_freq)
    
    # Add a membership fee product
    mf = {"price": pricing.membership_fees[fd]}
    s_list.append(mf)

    # Add a locker fee product if selected
    if locker_fee:
        lf = {"price": pricing.locker_fees[fd]}
        s_list.append(lf)
        print(s_list)
    
    # Add a donation amount product if selected
    if int(donation_amount) != 0:
        da = {"price": pricing.donation_levels[fd][donation_amount]}
        s_list.append(da)
    
    return s_list

def get_current_subscription_plan(c=None):

    subscriptions = {
        "membership_fee"    : False,
        "membership_type"   : "standard",
        "locker_fee"        : False,
        "donation_amount"   : 0,
        "payment_freq"      : 1,
        "is_paused"         : False
    }
    try: 
        stripe_subscriptions=stripe.Subscription.list(customer=c['id'], limit=100)
        p = stripe_subscriptions.data[0]["items"]["data"]
        i = stripe_subscriptions.data[0]["items"]["data"][0]["price"]["recurring"]["interval"]
        i_c = stripe_subscriptions.data[0]["items"]["data"][0]["price"]["recurring"]["interval_count"]
        payment_freq = pricing.stripe_interval_decode(i,i_c)
        d_freq = pricing.freq_decode(payment_freq)

        subscriptions["payment_freq"] = payment_freq

        for x in p:

            id = x["plan"]["id"]

            if "membership_fee" in x["price"]["metadata"]["type"]:
                subscriptions["membership_fee"] = True

                if pricing.i_membership_fees[id] == "paused":
                    subscriptions["is_paused"] = True

                if pricing.i_membership_fees[id] == "free":
                    subscriptions["membership_type"] = "free"
            
            if "locker_fee" in x["price"]["metadata"]["type"]:
                subscriptions["locker_fee"] = True

            if "donation" in x["price"]["metadata"]["type"]:
                subscriptions["donation_amount"] = pricing.reverse_map_donation_level(d_freq,id)
            
    except IndexError:
        # The member does not have an active subscription
        log.info("The member does not have an active subscription")
        pass

    return subscriptions

def cancel_current_subscription_plan(c=None):

    try:
        for s in stripe.Subscription.list(customer=c, limit=10):
            print("canceling current subscriptions...")
            stripe.Subscription.delete(s.id, prorate=True)
    except Exception as e:
        log.info(e)
        pass

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
        "page_is_dirty"             : None
    }

    member["stripe_id"] = user["stripeId"]
    member["email"] = user["email"]
    member["full_name"] = user["fullName"]
    member["discord_id"] = user["discordId"]
    member["payment_freq"] = user["payFreqRadio"]
    member["current_payment_method"] = user["currentPaymentMethod"]
    member["page_is_dirty"] = user["pageIsDirty"]

    if "pauseMembership" in user:
        member["is_paused"] = True
    
    if "lockerFee" in user:
        member["locker_fee"] = True
    
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

    if user["deleteCurrentPaymentMethod"] == "1":

        # Member adds a new card:
        #   1) create a new PaymentMethod
        #   2) attach it to the Stripe Customer
        #   3) set new PaymentMethod as Customer default
        #   4) detach the old PaymentMethod

        real_card = {
            "number": user["card-number"].replace(" ",""),
            "exp_month": user["expiry-month"],
            "exp_year": user["expiry-year"],
            "cvc": user["cvc"]
        }
        
        try:
            if (is_dev):               
                pm_visa = "pm_card_visa"
                pm_mc = "pm_card_mastercard"

                if user["card-number"].replace(" ","") == "424242424242":
                    pm = pm_visa
                else:
                    pm = pm_mc
            else:
                pm = stripe.PaymentMethod.create(type="card",card=real_card)

            x = stripe.PaymentMethod.attach(pm,customer=member["stripe_id"])

            stripe.Customer.modify(
                member["stripe_id"],
                invoice_settings = {"default_payment_method" : x}
            )

            stripe.PaymentMethod.detach(member["current_payment_method"])

        except Exception as e:
            log.info(e)

    # Update Subscriptions if necessary
    if member["page_is_dirty"] == "1":

        try:
            cancel_current_subscription_plan(member["stripe_id"])

            sp = build_subscription_plan(
                locker_fee=member["locker_fee"],
                donation_amount=member["donation_amount"],
                payment_freq=member["payment_freq"],
                is_paused=member["is_paused"]
            )

            stripe.Subscription.create(
                customer = member["stripe_id"],
                items = sp
            )

        except Exception as e:
            log.info(e)
    
def delete_membership():
    log.info("Calling delete_membership()")
    