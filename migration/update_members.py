import stripe, csv, sys

"""
select m.stripe_id, m.full_name, m.discord_handle, sc.stripe_email, sc.stripe_subscription_product from members m, stripe_cache sc where m.stripe_id = sc.stripe_id;
"""

sys.path.insert(0, '../crypto')
sys.path.insert(1, '../.')

from crypto import SettingsUtil, CryptoUtil

if sys.argv[1]:
    USERS_FILE = sys.argv[1]
    LOG_FILE = USERS_FILE + ".output"
else:
    exit

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
    
except Exception as e:
    print('ERROR', 'Failed to decrypt "ENCRYPTED_" config variables in "config.py".  Error was:', e)
    quit()
    
def main():

    with open(USERS_FILE, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        for row in csv_reader:
            try:

                if "#" in row["stripe_id"]:
                    continue 

                print(f'updating {row["full_name"]}')
                x = stripe.Customer.modify(
                    row["stripe_id"],
                    name = row["full_name"],
                    description = "",
                    metadata = {'discord_id': row["discord_id"]}
                )
            except Exception as e:
                print(e)
            
if __name__ == "__main__":
    main()
