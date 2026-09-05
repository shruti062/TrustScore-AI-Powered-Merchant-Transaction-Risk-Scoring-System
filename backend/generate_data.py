import random
import csv
from datetime import datetime, timedelta

random.seed(42)

NUM_TRANSACTIONS = 8000
MERCHANT_IDS = [f"M{100 + i}" for i in range(40)]

CITIES = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
          "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Bhubaneswar"]

DEVICE_TYPES = ["mobile", "desktop", "tablet"]

# Give every merchant its own "normal" baseline so fraud detection
# has to learn per-merchant deviation, not one global rule.
MERCHANT_PROFILES = {
    mid: {
        "typical_amount": random.choice([500, 1500, 3000, 8000, 20000]),
        "typical_hour_range": random.choice([(9, 21), (0, 23), (10, 18)]),
    }
    for mid in MERCHANT_IDS
}


def random_timestamp():
    start = datetime.now() - timedelta(days=45)
    random_seconds = random.randint(0, 45 * 24 * 60 * 60)
    return start + timedelta(seconds=random_seconds)


def build_transaction(txn_id):
    merchant_id = random.choice(MERCHANT_IDS)
    profile = MERCHANT_PROFILES[merchant_id]

    timestamp = random_timestamp()
    hour = timestamp.hour

    low, high = profile["typical_hour_range"]
    is_odd_hour = 1 if not (low <= hour <= high) else 0

    # amount is generated AROUND the merchant's typical amount,
    # occasionally spiking far above it (a common fraud signal)
    base = profile["typical_amount"]
    amount = round(max(50, random.gauss(base, base * 0.4)), 2)
    if random.random() < 0.05:  # 5% chance of an unusual spike
        amount = round(amount * random.uniform(3, 12), 2)
    amount = min(amount, 300000)

    billing_city = random.choice(CITIES)
    shipping_city = random.choice(CITIES)
    location_mismatch = 1 if billing_city != shipping_city else 0

    device = random.choice(DEVICE_TYPES)

    velocity_last_hour = random.choices(
        [1, 2, 3, 4, 5, 8],
        weights=[70, 15, 8, 4, 2, 1]
    )[0]

    new_device_flag = random.choices([0, 1], weights=[85, 15])[0]

    # how far this amount deviates from the merchant's normal amount
    amount_deviation_ratio = round(amount / base, 2)

    risk_signal = (
        is_odd_hour * 0.20
        + location_mismatch * 0.18
        + new_device_flag * 0.18
        + min(velocity_last_hour / 8, 1) * 0.22
        + min(amount_deviation_ratio / 6, 1) * 0.22
    )
    risk_signal += random.uniform(-0.15, 0.15)

    is_fraud = 1 if risk_signal > 0.55 else 0

    return {
        "txn_id": f"T{10000 + txn_id}",
        "merchant_id": merchant_id,
        "timestamp": timestamp.isoformat(),
        "amount": amount,
        "hour_of_day": hour,
        "is_odd_hour": is_odd_hour,
        "billing_city": billing_city,
        "shipping_city": shipping_city,
        "location_mismatch": location_mismatch,
        "device_type": device,
        "new_device_flag": new_device_flag,
        "velocity_last_hour": velocity_last_hour,
        "amount_deviation_ratio": amount_deviation_ratio,
        "is_fraud": is_fraud,
    }


def main():
    rows = [build_transaction(i) for i in range(NUM_TRANSACTIONS)]

    with open("transactions.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    fraud_count = sum(r["is_fraud"] for r in rows)
    print(f"Generated {len(rows)} transactions -> transactions.csv")
    print(f"Fraudulent: {fraud_count} ({fraud_count / len(rows):.1%})")


if __name__ == "__main__":
    main()
