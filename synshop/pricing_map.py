
# Stripe product / price id lookups

membership_fees = {
    "paused"        : "price_0NnAEQhX2MNi0jZxhFu8Pk6T",
    "free"          : "price_0NiSdIhX2MNi0jZx8fE7Tidx",
    "monthly"       : "price_0NiSX0hX2MNi0jZxqe9RIqqZ",
    "quarterly"     : "price_0NiSX0hX2MNi0jZxa3wJ4f2O",
    "semiannually"  : "price_0NiSaKhX2MNi0jZxZdsKmHdZ",
    "yearly"        : "price_0NiScBhX2MNi0jZxnJ0zhPup"
}

locker_fees = {
    "monthly"       : "price_0NbbTGhX2MNi0jZxa76MmUU1",
    "quarterly"     : "price_0NiS5uhX2MNi0jZxHGqqWXiT",
    "semiannually"  : "price_0NiS6LhX2MNi0jZxLKYQTHWJ",
    "yearly"        : "price_0NiS6bhX2MNi0jZx5U7S8G75",
}

donation_levels = {
    "monthly": {
        "10" : "price_0NiSeshX2MNi0jZx32KGNHOA",
        "20" : "price_0NiSgnhX2MNi0jZxNCCAFmV2",
        "30" : "price_0NiSgnhX2MNi0jZxoo6B4mSw",
        "40" : "price_0NiSgnhX2MNi0jZxNWdD6Bw2",
        "50" : "price_0NiSgnhX2MNi0jZx5CX8H2l6"
    },
    "quarterly": {
        "10" : "price_0NiShwhX2MNi0jZxQoR7I4RG",
        "20" : "price_0NiShwhX2MNi0jZx5qNfwDrW",
        "30" : "price_0NiShwhX2MNi0jZxzYW1wT5b",
        "40" : "price_0NiShwhX2MNi0jZxjQxUD2uJ",
        "50" : "price_0NiTLlhX2MNi0jZxmDPur7kt"
    },
    "semiannually" : {
        "10" : "price_0NiTNghX2MNi0jZxKRuqaYKx",
        "20" : "price_0NiTNghX2MNi0jZxvLEPKNjz",
        "30" : "price_0NiTNghX2MNi0jZxYPWATk3A",
        "40" : "price_0NiTNghX2MNi0jZxyMoHzeT4",
        "50" : "price_0NiTNghX2MNi0jZxFTk3HmvK"
    },
    "yearly" : {
        "10" : "price_0NiTR1hX2MNi0jZxEvODSszv",
        "20" : "price_0NiTR1hX2MNi0jZxbQPImHDm",
        "30" : "price_0NiTR1hX2MNi0jZx7yllYFUv",
        "40" : "price_0NiTR1hX2MNi0jZxUjA8rSIj",
        "50" : "price_0NiTR1hX2MNi0jZxXfKAwYay"
    }
}

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

# Invert the membership_fees dictionary
i_membership_fees = {v: k for k, v in membership_fees.items()}

# Invert the locker_fees dictionary
i_locker_fees = {v: k for k, v in locker_fees.items()}

# Invert the donation_level dictionary after plucking the
# given "month" sub-dict
def reverse_map_donation_level(payment_freq=None, price_id=None):
    plucked_donation_levels = dict(donation_levels[payment_freq])
    i_donation_levels = {v: k for k, v in plucked_donation_levels.items()}
    
    return i_donation_levels[price_id]
