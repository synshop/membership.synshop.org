import stripe, csv, sys

sys.path.insert(0, '../crypto')
sys.path.insert(1, '../.')

from crypto import SettingsUtil, CryptoUtil

USERS_FILE = "/home/ubuntu/unified_customers.csv"

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

    with open(USERS_FILE, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        line_count = 0
        for row in csv_reader:
            if row["Status"] == "" and row["Plan"] == "":
                id = row["id"]
                try:
                    print(f'Removing {row}')
                    # stripe.Customer.delete(id)
                    line_count += 1
                except stripe.error.InvalidRequestError:
                    continue
                
        print(f'Processed {line_count} accounts...')

if __name__ == "__main__":
    main()
