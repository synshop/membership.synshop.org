import stripe, time
from crypto import SettingsUtil, CryptoUtil

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
except Exception as e:
    print('ERROR', 'Failed to decrypt "ENCRYPTED_" config variables in "config.py".  Error was:', e)
    quit()

## Stripe functions

def has_stripe_account(email=None):
    sr=stripe.Customer.search(query='email: "' + email + '"', limit=1)
    return len(sr['data'])

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
