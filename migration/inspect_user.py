import stripe, csv, sys

sys.path.insert(0, '../crypto')
sys.path.insert(1, '../.')

from crypto import SettingsUtil, CryptoUtil

# Load Configuration Variables
try:
    import config
except Exception as e:
    print('ERROR', 'Missing "config.py" file. See https://github.com/synshop/membership.synshop.org for info')
    quit()

# Load Encrypted Configuration Variables
try:
    is_dev = config.IS_DEV
    ENCRYPTION_KEY = SettingsUtil.EncryptionKey.get()

    is_dev = False

    if is_dev:
        stripe.api_key = CryptoUtil.decrypt(config.ENCRYPTED_STRIPE_TOKEN_DEVO, ENCRYPTION_KEY)
    else:
        stripe.api_key = CryptoUtil.decrypt(config.ENCRYPTED_STRIPE_TOKEN_PROD, ENCRYPTION_KEY)

    stripe.api_version = config.STRIPE_VERSION
    auth0_client_secret = CryptoUtil.decrypt(config.ENCRYPTED_AUTH0_CLIENT_SECRET, ENCRYPTION_KEY)
    auth0_client_id = config.AUTH0_CLIENT_ID
    auth0_domain = config.AUTH0_DOMAIN
    is_dev = config.IS_DEV
except Exception as e:
    print('ERROR', 'Failed to decrypt "ENCRYPTED_" config variables in "config.py".  Error was:', e)
    quit()
    
def main():
    # email = ""
    c = stripe.Customer.search(query='email: "' + email + '"', limit=1)['data'][0]

    print(c)
    
if __name__ == "__main__":
    main()
