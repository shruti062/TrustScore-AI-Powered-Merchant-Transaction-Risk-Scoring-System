import random
import csv
from datetime import datetime, timedelta

random.seed(42)  

NUM_TRANSACTIONS = 4000
MERCHANT_IDS = [f"M{100 + i}" for i in range(40)] 

CITIES = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
          "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Bhubaneswar"]

DEVICE_TYPES = ["mobile", "desktop", "tablet"]


def random_timestamp():
    start = datetime.now() - timedelta(days=30)
    random_seconds = random.randint(0, 30 * 24 * 60 * 60)
    return start + timedelta(seconds=random_seconds)


def build_transaction(txn_id):
    merchant_id = random.choice(MERCHANT_IDS)
    timestamp = random_timestamp()
    hour = timestamp.hour
    is_odd_hour = 1 if hour < 6 or hour > 23 else 0

    amount = round(random.expovariate(1 / 1500), 2)
    amount = min(amount, 250000)  # cap at 2.5 lakh

    billing_city = random.choice(CITIES)
    shipping_city = random.choice(CITIES)
    location_mismatch = 1 if billing_city != shipping_city else 0

    device = random.choice(DEVICE_TYPES)
    velocity_last_hour = random.choices(
        [1, 2, 3, 4, 5, 8],
        weights=[70, 15, 8, 4, 2, 1]
    )[0]

    new_device_flag = random.choices([0, 1], weights=[85, 15])[0]
    risk_signal = (
        is_odd_hour * 0.25
        + location_mismatch * 0.20
        + new_device_flag * 0.20
        + min(velocity_last_hour / 8, 1) * 0.25
        + min(amount / 250000, 1) * 0.10
    )
    risk_signal += random.uniform(-0.15, 0.15)  # noise

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
        "is_fraud": is_fraud,
    }


def main():
    rows = [build_transaction(i) for i in range(NUM_TRANSACTIONS)]

    out_path = "transactions.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    fraud_count = sum(r["is_fraud"] for r in rows)
    print(f"Generated {len(rows)} transactions -> {out_path}")
    print(f"Fraudulent: {fraud_count} ({fraud_count / len(rows):.1%})")


if __name__ == "__main__":
    main()
