"""
Build three lists of (supplier_id, consumer_id) pairs by k in {0, 1, 2}.

Criteria:
1. Center distance < 250 (from center_crosswalk).
2. Blood type must match (supplier Blood_type == consumer Blood_type).
3. UA(j) != DR(i)(1) and UA(j) != DR(i)(2).
4. k = 2 - num_DR_matches: 0 = both DRs match, 1 = one match, 2 = none.

Output: list_k0, list_k1, list_k2 and optional CSV files.
"""

import argparse
import csv
from pathlib import Path

import pandas as pd

# Default paths
DEFAULT_DIR = Path(__file__).resolve().parent
CENTER_CROSSWALK_XLSX = "center_crosswalk.xlsx"
CENTER_CROSSWALK_CSV = "center_crosswalk.csv"
SUPPLY_CSV = "supply.csv"
DEMAND_CSV = "demand.csv"
MAX_DISTANCE = 250


def load_center_crosswalk(data_dir: Path, save_csv: bool = True) -> pd.DataFrame:
    """Load center distances from Excel; optionally save as CSV. Return long-format DataFrame."""
    xlsx_path = data_dir / CENTER_CROSSWALK_XLSX
    csv_path = data_dir / CENTER_CROSSWALK_CSV

    if csv_path.exists():
        df = pd.read_csv(csv_path)
    else:
        df = pd.read_excel(xlsx_path, engine="openpyxl", sheet_name=0)
        # Normalize to long format: center_from, center_to, distance
        col_names = [str(c).strip().lower() for c in df.columns]
        # Map common names to standard names
        from_names = ("center_from", "from", "from_center", "center_from_id", "origin")
        to_names = ("center_to", "to", "to_center", "center_to_id", "dest", "destination")
        dist_names = ("distance", "dist", "miles", "km", "d")
        rename_map = {}
        for i, c in enumerate(df.columns):
            cn = col_names[i]
            if cn in from_names or (i == 0 and "from" in cn):
                rename_map[c] = "center_from"
            elif cn in to_names or (i == 1 and "to" in cn):
                rename_map[c] = "center_to"
            elif cn in dist_names or (i == 2 and df[c].dtype in ("int64", "float64")):
                rename_map[c] = "distance"
        if rename_map:
            df = df.rename(columns=rename_map)
        # If still missing standard names, use first three columns by position
        if "center_from" not in df.columns or "center_to" not in df.columns or "distance" not in df.columns:
            if len(df.columns) >= 3:
                df = df.iloc[:, :3].copy()
                df.columns = ["center_from", "center_to", "distance"]
            elif df.shape[0] >= 4 and df.shape[1] >= 4:
                # Matrix: rows = from, cols = to
                from_centers = (df.index + 1) if df.index.dtype in ("int64", "int32") else range(1, len(df) + 1)
                rows = []
                for i, fc in enumerate(from_centers):
                    if i >= 4:
                        break
                    for j in range(1, min(5, len(df.columns))):
                        tc = j
                        dist = df.iloc[i, j]
                        if pd.notna(dist):
                            rows.append({"center_from": int(fc), "center_to": int(tc), "distance": float(dist)})
                df = pd.DataFrame(rows)
        if save_csv:
            df.to_csv(csv_path, index=False)

    return df


def valid_center_pairs(crosswalk: pd.DataFrame, max_dist: float) -> set:
    """Set of (center_supplier, center_consumer) with distance < max_dist."""
    pairs = set()
    for _, row in crosswalk.iterrows():
        c_from = int(row["center_from"])
        c_to = int(row["center_to"])
        d = float(row["distance"])
        if d < max_dist:
            pairs.add((c_from, c_to))
    return pairs


def build_connections(
    supply: pd.DataFrame,
    demand: pd.DataFrame,
    valid_pairs: set,
    max_supply: int | None = None,
    progress_every: int = 0,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]], list[tuple[int, int]]]:
    """Build list_k0, list_k1, list_k2 of (supplier_id, consumer_id)."""
    list_k0 = []
    list_k1 = []
    list_k2 = []

    if max_supply is not None:
        supply = supply.head(max_supply)

    # Index demand by center for fast lookup
    demand_by_center = {}
    for c in demand["Transplant_Center"].unique():
        demand_by_center[c] = demand.loc[demand["Transplant_Center"] == c].copy()

    supply_id = supply["Supplier_ID"].values
    supply_center = supply["Transplant_Center"].values
    supply_dr1 = supply["DR#1"].values
    supply_dr2 = supply["DR#2"].values
    supply_blood = supply["Blood_type"].values
    n_supply = len(supply)

    for idx in range(n_supply):
        if progress_every and (idx + 1) % progress_every == 0:
            print(f"  Supply row {idx + 1}/{n_supply} ...")
        i_id = int(supply_id[idx])
        c_s = int(supply_center[idx])
        dr_i1 = supply_dr1[idx]
        dr_i2 = supply_dr2[idx]
        blood_i = supply_blood[idx]

        # Demand rows j such that (c_s, c_c) is valid
        for c_c in demand_by_center:
            if (c_s, c_c) not in valid_pairs:
                continue
            sub = demand_by_center[c_c]
            ua_j = sub["UA"].values
            dr_j1 = sub["DR#1"].values
            dr_j2 = sub["DR#2"].values
            j_ids = sub["Consumer_ID"].values
            blood_j = sub["Blood_type"].values

            # Blood type must match; UA filter: UA(j) != DR(i)(1) and UA(j) != DR(i)(2)
            blood_ok = blood_j == blood_i
            ua_ok = (ua_j != dr_i1) & (ua_j != dr_i2) & blood_ok
            if not ua_ok.any():
                continue

            j_ids_ok = j_ids[ua_ok]
            # DR matches (in either position)
            match1 = (dr_j1 == dr_i1) | (dr_j1 == dr_i2)
            match2 = (dr_j2 == dr_i1) | (dr_j2 == dr_i2)
            num_matches = (match1.astype(int) + match2.astype(int))[ua_ok]
            k_vals = 2 - num_matches

            # Vectorized: append by k
            for k in (0, 1, 2):
                mask = k_vals == k
                if mask.any():
                    j_subset = j_ids_ok[mask].astype(int)
                    i_repeat = [i_id] * len(j_subset)
                    pairs_k = list(zip(i_repeat, j_subset.tolist()))
                    if k == 0:
                        list_k0.extend(pairs_k)
                    elif k == 1:
                        list_k1.extend(pairs_k)
                    else:
                        list_k2.extend(pairs_k)

    return list_k0, list_k1, list_k2


def main():
    parser = argparse.ArgumentParser(description="Build supply-demand connection lists by k.")
    parser.add_argument(
        "--datadir",
        type=str,
        default=str(DEFAULT_DIR),
        help="Directory containing center_crosswalk, supply.csv, demand.csv",
    )
    parser.add_argument(
        "--max-distance",
        type=float,
        default=MAX_DISTANCE,
        help=f"Max center distance (default {MAX_DISTANCE})",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Do not write center_crosswalk.csv",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output directory for connection CSVs (default: same as datadir)",
    )
    parser.add_argument(
        "--single-file",
        action="store_true",
        help="Write one connections.csv with column k instead of three files",
    )
    parser.add_argument(
        "--max-supply",
        type=int,
        default=None,
        help="Limit supply rows (for testing); default all",
    )
    parser.add_argument(
        "--progress",
        type=int,
        default=0,
        metavar="N",
        help="Print progress every N supply rows (0=off)",
    )
    args = parser.parse_args()

    data_dir = Path(args.datadir)
    out_dir = Path(args.out) if args.out else data_dir

    # 1. Center crosswalk
    crosswalk = load_center_crosswalk(data_dir, save_csv=not args.no_csv)
    # Ensure required columns exist
    for col in ("center_from", "center_to", "distance"):
        if col not in crosswalk.columns:
            raise ValueError(f"Center crosswalk must have column '{col}'. Columns: {list(crosswalk.columns)}")
    valid_pairs = valid_center_pairs(crosswalk, args.max_distance)
    print(f"Loaded crosswalk: {len(crosswalk)} rows, {len(valid_pairs)} center pairs with distance < {args.max_distance}")

    # 2. Load supply and demand
    supply = pd.read_csv(data_dir / SUPPLY_CSV)
    demand = pd.read_csv(data_dir / DEMAND_CSV)
    print(f"Supply: {len(supply)} rows, Demand: {len(demand)} rows")

    # 3 & 4. Build lists
    list_k0, list_k1, list_k2 = build_connections(
        supply, demand, valid_pairs,
        max_supply=args.max_supply,
        progress_every=args.progress,
    )
    print(f"List k=0: {len(list_k0)} pairs, k=1: {len(list_k1)} pairs, k=2: {len(list_k2)} pairs")

    # 5. Output
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.single_file:
        rows = [(*p, 0) for p in list_k0] + [(*p, 1) for p in list_k1] + [(*p, 2) for p in list_k2]
        out_path = out_dir / "connections.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["supplier_id", "consumer_id", "k"])
            w.writerows(rows)
        print(f"Wrote {out_path}")
    else:
        for k, lst in enumerate([list_k0, list_k1, list_k2]):
            out_path = out_dir / f"connections_k{k}.csv"
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["supplier_id", "consumer_id"])
                w.writerows(lst)
            print(f"Wrote {out_path}")

    return {"k0": list_k0, "k1": list_k1, "k2": list_k2}


if __name__ == "__main__":
    main()
