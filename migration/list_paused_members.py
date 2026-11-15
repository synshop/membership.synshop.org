import stripe, csv, sys, os, datetime, argparse

# List every Stripe customer with a paused subscription, as CSV on stdout.
# With --delete, cancel (delete) the subscriptions listed in a CSV from a
# previous dry run.
#
# A subscription counts as paused if any of these are true:
#   - it includes the old "paused" membership price (removed from the pricing maps in 6a5832f)
#   - Stripe's pause_collection is set on it
#   - its status is "paused"
#
# Usage (from the repo root):
#   ENCRYPTION_KEY=... python migration/list_paused_members.py > paused.csv
#   (review / trim paused.csv by hand)
#   ENCRYPTION_KEY=... python migration/list_paused_members.py --delete paused.csv > deleted.csv
#   ENCRYPTION_KEY=... python migration/list_paused_members.py --delete paused.csv --limit 1 > deleted.csv
#
# Without --delete nothing is changed. With --delete, only subscription ids in
# the given CSV are touched, each one is re-fetched and skipped unless it is
# still paused, and you have to type the count to confirm before anything runs.
# The "action" column shows what happened (or would happen) to each subscription.
#
# The Stripe account is whichever one config.ENCRYPTED_STRIPE_TOKEN points at,
# and the paused price is picked to match config.PRICING_MAP.

basedir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(basedir, '..'))

from crypto import SettingsUtil, CryptoUtil

PAUSED_PRICES = {
    "pricing_map_prod.yml" : "price_0Ntw5YhX2MNi0jZxBhNnreLl",
    "pricing_map_devo.yml" : "price_0NnAEQhX2MNi0jZxhFu8Pk6T"
}

# Load Configuration Variables
try:
    import config
except Exception as e:
    print('ERROR', 'Missing "config.py" file. See https://github.com/synshop/membership.synshop.org for info', file=sys.stderr)
    quit()

# Load Encrypted Configuration Variables
try:
    ENCRYPTION_KEY = SettingsUtil.EncryptionKey.get()
    stripe.api_key = CryptoUtil.decrypt(config.ENCRYPTED_STRIPE_TOKEN, ENCRYPTION_KEY)
    stripe.api_version = config.STRIPE_VERSION
except Exception as e:
    print('ERROR', 'Failed to decrypt "ENCRYPTED_" config variables in "config.py".  Error was:', e, file=sys.stderr)
    quit()

def pause_reasons(s, paused_price):
    reasons = []

    if any(item["price"]["id"] == paused_price for item in s["items"]["data"]):
        reasons.append("paused_price")

    if s.get("pause_collection"):
        reasons.append("pause_collection:" + s["pause_collection"]["behavior"])

    if s["status"] == "paused":
        reasons.append("status_paused")

    return reasons

def find_paused(paused_price):
    paused = []
    subs = stripe.Subscription.list(status="all", limit=100, expand=["data.customer"])

    for s in subs.auto_paging_iter():
        if s["status"] in ("canceled", "incomplete_expired"):
            continue

        reasons = pause_reasons(s, paused_price)
        if not reasons:
            continue

        if s["customer"].get("deleted"):
            continue

        paused.append((s, reasons))

    return paused

def load_reviewed(path, paused_price, limit):
    with open(path, newline="") as f:
        ids = [row["subscription_id"].strip() for row in csv.DictReader(f) if row.get("subscription_id", "").strip()]

    # Drop duplicates, keep order
    ids = list(dict.fromkeys(ids))
    if limit is not None:
        ids = ids[:limit]

    paused = []
    for sub_id in ids:
        s = stripe.Subscription.retrieve(sub_id, expand=["customer"])
        reasons = [] if s["status"] in ("canceled", "incomplete_expired") else pause_reasons(s, paused_price)
        paused.append((s, reasons))

    return paused

def confirm(mode, count):
    # stdout is the CSV, so prompt on stderr and read the answer from the terminal
    print("About to cancel " + str(count) + " subscription(s) in " + mode + " Stripe.", file=sys.stderr)
    print("Type " + str(count) + " to continue: ", end="", file=sys.stderr, flush=True)

    try:
        with open("/dev/tty") as tty:
            answer = tty.readline().strip()
    except OSError as e:
        print("\nERROR unable to read confirmation from terminal (" + str(e) + "), aborting", file=sys.stderr)
        return False

    return answer == str(count)

def main():
    parser = argparse.ArgumentParser(description="List (and optionally cancel) paused Stripe subscriptions")
    parser.add_argument("--delete", metavar="CSV", help="cancel the subscriptions listed in this reviewed dry-run CSV")
    parser.add_argument("--limit", type=int, help="with --delete, only process the first N subscriptions in the CSV")
    args = parser.parse_args()

    paused_price = PAUSED_PRICES[config.PRICING_MAP]
    mode = "LIVE" if stripe.api_key.startswith(("sk_live", "rk_live")) else "TEST"
    print("Stripe mode: " + mode + ", paused price: " + paused_price, file=sys.stderr)

    if args.delete:
        paused = load_reviewed(args.delete, paused_price, args.limit)
        to_delete = sum(1 for s, reasons in paused if reasons)
        print(str(len(paused)) + " subscription(s) in " + args.delete + ", " + str(to_delete) + " still paused", file=sys.stderr)

        if to_delete == 0:
            print("Nothing to do", file=sys.stderr)
            return

        if not confirm(mode, to_delete):
            print("Aborted, nothing was changed", file=sys.stderr)
            return
    else:
        paused = find_paused(paused_price)
        print(str(len(paused)) + " paused subscription(s) found", file=sys.stderr)

    writer = csv.writer(sys.stdout)
    writer.writerow(["customer_id", "name", "email", "discord_id", "subscription_id", "status", "reasons", "started", "action"])

    deleted = 0
    failed = 0

    for s, reasons in paused:
        c = s["customer"]

        if not args.delete:
            action = "dry_run"
        elif not reasons:
            action = "skipped: not paused"
            print("Skipping " + s["id"] + ": not paused (status " + s["status"] + ")", file=sys.stderr)
        else:
            try:
                stripe.Subscription.delete(s["id"], prorate=False)
                action = "deleted"
                deleted += 1
            except Exception as e:
                action = "error: " + str(e)
                failed += 1
                print("ERROR deleting " + s["id"] + ": " + str(e), file=sys.stderr)

        writer.writerow([
            c["id"],
            c.get("name") or "",
            c.get("email") or "",
            (c.get("metadata") or {}).get("discord_id", ""),
            s["id"],
            s["status"],
            ";".join(reasons),
            datetime.datetime.fromtimestamp(s["start_date"], datetime.timezone.utc).date().isoformat(),
            action
        ])

    if args.delete:
        print(str(deleted) + " subscription(s) deleted, " + str(failed) + " failed", file=sys.stderr)

if __name__ == "__main__":
    main()
