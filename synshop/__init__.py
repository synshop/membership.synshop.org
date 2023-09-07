import stripe, time
from crypto import SettingsUtil, CryptoUtil
import synshop.pricing_map as pricing

# Load Configuration Variables
try:
    import config
except Exception as e:
    print('ERROR', 'Missing "config.py" file. See https://github.com/synshop/membership.synshop.org for info')
    quit()

# Load Configuration Variables
try:
    # RUN_MODE = 'development'
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
                'discordId': user["discordId"],
            },
            payment_method = pm,
            invoice_settings = {
                'default_payment_method': pm
            }
        )
        
        stripe.Subscription.create(
            customer = sc.id,
            items = build_subscription_plan(locker_fee,donation_amount,payment_freq)
        )
             
        return True
    except Exception as e:
        print(e)
        return False

def build_subscription_plan(locker_fee=False,donation_amount=0,payment_freq=1):

    s_list = []
    fd = pricing.freq_decode[payment_freq]
    
    # Add a membership fee product
    mf = {"price": pricing.membership_fees[fd]}
    s_list.append(mf)

    # Add a locker fee product if selected
    if locker_fee:
        lf = {"price": pricing.locker_fees[fd]}
        s_list.append(lf)
    
    # Add a donation amount product if selected
    if int(donation_amount) != 0:
        da = {"price": pricing.donation_levels[fd][donation_amount]}
        s_list.append(da)
        
    return s_list


""" NOT IN USE
def get_stripe_products():
    products = stripe.Product.list(active=True).data
    for p in products:
        print(p['name'])

def get_product_description(product):
    p = stripe.Product.retrieve(product)["description"]
    return p

def get_subscriptions_for_member(email="None"):
    sr=stripe.Customer.search(query='email: "' + email + '"', limit=1)
    sc=sr.data[0]
    stripe_subscriptions=stripe.Subscription.list(customer=sc.id, limit=100)
    products = stripe_subscriptions.data[0]["items"]
    for p in products:
        print(get_product_description(p["price"]["product"]))

def get_product_details(p="prod_OOOFroHauh6Jrr"):
    print(stripe.Product.retrieve(p))
    print(stripe.Price.list(product=p))

"""