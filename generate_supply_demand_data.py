"""
Generate supply.csv (40k rows) and demand.csv (100k rows) for transplant
supply/demand simulation. No duplicate IDs. Distributions as specified.
"""
import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

import numpy as np

# Constants
N_SUPPLY = 40_000
N_DEMAND = 100_000
N_CENTERS = 4
N_DR = 20
N_UA = 20
N_BLOOD_TYPES = 4

# Date ranges (inclusive)
OFFER_DATE_START = date(2020, 1, 1)
OFFER_DATE_END = date(2024, 12, 31)
WL_START_DATE_START = date(2018, 1, 1)
WL_START_DATE_END = date(2024, 12, 31)
WL_END_MAX = date(2025, 6, 1)
WL_DAYS_MIN = 1
WL_DAYS_MAX = 800

# Blood type weights (moderate skew): types 1-4
BLOOD_TYPE_WEIGHTS = np.array([0.35, 0.25, 0.22, 0.18])

# Supply CSV headers (use "DR#1"/"DR#2" for clarity)
SUPPLY_HEADERS = [
    "Supplier_ID",
    "Transplant_Center",
    "Offer_date",
    "DR#1",
    "DR#2",
    "Blood_type",
]
DEMAND_HEADERS = [
    "Consumer_ID",
    "Transplant_Center",
    "WL_start_date",
    "WL_end_date",
    "DR#1",
    "DR#2",
    "UA",
    "Blood_type",
]


def build_center_weights_supply():
    """Center 1-4, slight bias toward higher numbers."""
    c = np.arange(1, N_CENTERS + 1, dtype=float)
    w = c ** 0.15
    return w / w.sum()


def build_center_weights_demand():
    """Center 1-4, lower centers more common."""
    c = np.arange(1, N_CENTERS + 1, dtype=float)
    w = (N_CENTERS + 1 - c) ** 1.2
    return w / w.sum()


def build_dr_weights(rng):
    """Single probability vector for DR#1 and DR#2 (1-20), moderate distribution."""
    w = rng.beta(2, 2, N_DR)
    return w / w.sum()


def build_ua_weights(rng):
    """UA 1-20: 90% UA=1, 10% distributed over 2-20 (moderate skew)."""
    ua_probs = np.zeros(N_UA)
    ua_probs[0] = 0.9  # UA=1
    remainder = rng.beta(2, 2, N_UA - 1)  # UA 2-20
    ua_probs[1:] = 0.1 * (remainder / remainder.sum())
    return ua_probs


def random_date_in_range(rng, start: date, end: date, skew_later: bool = False):
    """Random date between start and end. If skew_later, later dates slightly more likely."""
    days = (end - start).days + 1
    if days <= 0:
        raise ValueError("Invalid date range")
    if skew_later:
        # Weight by position: later positions get slightly higher weight
        t = np.linspace(0, 1, days)
        weights = 0.7 + 0.3 * t
        weights /= weights.sum()
        idx = rng.choice(days, p=weights)
    else:
        idx = rng.integers(0, days)
    return start + timedelta(days=int(idx))


def generate_supply(rng, center_probs, dr_probs):
    """Generate supply rows (no duplicate Supplier_ID by construction)."""
    centers = rng.choice(
        np.arange(1, N_CENTERS + 1), size=N_SUPPLY, p=center_probs
    )
    # Supplier IDs: unique 1..N_SUPPLY (shuffle for no ordering assumption)
    supplier_ids = rng.permutation(N_SUPPLY) + 1
    offer_dates = [
        random_date_in_range(rng, OFFER_DATE_START, OFFER_DATE_END, skew_later=True)
        for _ in range(N_SUPPLY)
    ]
    dr1 = rng.choice(np.arange(1, N_DR + 1), size=N_SUPPLY, p=dr_probs)
    dr2 = rng.choice(np.arange(1, N_DR + 1), size=N_SUPPLY, p=dr_probs)
    blood = rng.choice(
        np.arange(1, N_BLOOD_TYPES + 1), size=N_SUPPLY, p=BLOOD_TYPE_WEIGHTS
    )
    rows = []
    for i in range(N_SUPPLY):
        rows.append(
            [
                supplier_ids[i],
                int(centers[i]),
                offer_dates[i].isoformat(),
                int(dr1[i]),
                int(dr2[i]),
                int(blood[i]),
            ]
        )
    return rows


def generate_demand(rng, center_probs, dr_probs, ua_probs):
    """Generate demand rows (no duplicate Consumer_ID by construction)."""
    centers = rng.choice(
        np.arange(1, N_CENTERS + 1), size=N_DEMAND, p=center_probs
    )
    consumer_ids = rng.permutation(N_DEMAND) + 1
    wl_starts = [
        random_date_in_range(rng, WL_START_DATE_START, WL_START_DATE_END, skew_later=False)
        for _ in range(N_DEMAND)
    ]
    gap_days = rng.integers(WL_DAYS_MIN, WL_DAYS_MAX + 1, size=N_DEMAND)
    wl_ends = []
    for i in range(N_DEMAND):
        end = wl_starts[i] + timedelta(days=int(gap_days[i]))
        if end > WL_END_MAX:
            end = WL_END_MAX
        wl_ends.append(end)
    dr1 = rng.choice(np.arange(1, N_DR + 1), size=N_DEMAND, p=dr_probs)
    dr2 = rng.choice(np.arange(1, N_DR + 1), size=N_DEMAND, p=dr_probs)
    ua = rng.choice(np.arange(1, N_UA + 1), size=N_DEMAND, p=ua_probs)
    blood = rng.choice(
        np.arange(1, N_BLOOD_TYPES + 1), size=N_DEMAND, p=BLOOD_TYPE_WEIGHTS
    )
    rows = []
    for i in range(N_DEMAND):
        rows.append(
            [
                consumer_ids[i],
                int(centers[i]),
                wl_starts[i].isoformat(),
                wl_ends[i].isoformat(),
                int(dr1[i]),
                int(dr2[i]),
                int(ua[i]),
                int(blood[i]),
            ]
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description="Generate supply and demand CSVs.")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default=".",
        help="Directory to write supply.csv and demand.csv (default: current directory).",
    )
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    center_supply = build_center_weights_supply()
    center_demand = build_center_weights_demand()
    dr_probs = build_dr_weights(rng)
    ua_probs = build_ua_weights(rng)

    supply_rows = generate_supply(rng, center_supply, dr_probs)
    demand_rows = generate_demand(rng, center_demand, dr_probs, ua_probs)

    out = Path(args.outdir)
    supply_path = out / "supply.csv"
    demand_path = out / "demand.csv"

    with open(supply_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(SUPPLY_HEADERS)
        writer.writerows(supply_rows)

    with open(demand_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(DEMAND_HEADERS)
        writer.writerows(demand_rows)

    print(f"Wrote {len(supply_rows)} rows to {supply_path}")
    print(f"Wrote {len(demand_rows)} rows to {demand_path}")


if __name__ == "__main__":
    main()
