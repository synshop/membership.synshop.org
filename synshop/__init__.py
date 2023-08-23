import stripe, time
from crypto import SettingsUtil, CryptoUtil

# Load Configuration Variables
try:
    import config
except Exception as e:
    print('ERROR', 'Missing "config.py" file. See https://github.com/synshop/membership.synshop.org for info')
    quit()

# Load Encrypted Configuration Variables
try:
    RUN_MODE = 'development'
    ENCRYPTION_KEY = SettingsUtil.EncryptionKey.get(RUN_MODE == 'development')
    stripe.api_key = CryptoUtil.decrypt(config.ENCRYPTED_STRIPE_TOKEN, ENCRYPTION_KEY)
except Exception as e:
    print('ERROR', 'Failed to decrypt "ENCRYPTED_" config variables in "config.py".  Error was:', e)
    quit()

STRIPE_VERSION = "2023-08-16"
stripe.api_version=STRIPE_VERSION

def get_stripe_products():
    products = stripe.Product.list().data
    for p in products:
        if p['active'] == True: 
            print(p['name'])
            