# -*- coding: utf-8 -*-
"""v2_spec_combos.py -- full grid of balance-concentration specifications (the ends of a
range should not come only from varying one choice at a time).

5 populations x 3 address types x 2 units = 30 combinations; HHI and Gini for each token.
  population:   all positive balances / transfer-active (cleaned) /
                transfer-active (airdrop kept) / dust floor / value floor
  address type: all / excluding burn / excluding burn and issuer
  unit:         address / entity (labels merged)
Also reports the largest effect of varying each factor alone (factor_effects),
which supports the three-way conclusion of Section 4.2.
Output: results/spec_combos.json.
"""
import itertools
import json

import pandas as pd

import common as cm
import config as C


FACTORS = {  # factor -> (column, levels); the other two columns held fixed, max effect over the grid
    "activity": ("population", ("all", "active", "active_airdrop_kept")),
    "floor": ("population", ("all", "dust_floor", "value_floor")),
    "address_type": ("address_type", ("all", "excl_burn", "excl_burn_issuer")),
    "entity": ("unit", ("address", "entity")),
}


def factor_effects(df):
    """Largest HHI ratio and largest Gini change when one factor varies and the
    other two are fixed. Address type and entity resolution are compared on the
    three populations without a floor, as in the "eighteen cells" of the paper."""
    out = {}
    for f, (col, levels) in FACTORS.items():
        others = [c for c in ("population", "address_type", "unit") if c != col]
        sub = df[df[col].isin(levels) & ~df["population"].str.endswith("floor")] if col != "population" \
            else df[df[col].isin(levels)]
        g = sub.groupby(others)
        out[f] = {"hhi_ratio_max": round(float((g["hhi"].max() / g["hhi"].min()).max()), 3),
                  "gini_change_max": round(float((g["gini"].max() - g["gini"].min()).max()), 4)}
    base = df.set_index(["address_type", "unit"])
    fl = df[df["population"].str.endswith("floor")].set_index(["address_type", "unit"])
    out["floor"]["hhi_change_max"] = round(float(
        (fl["hhi"] / base.loc[base["population"] == "all", "hhi"].reindex(fl.index) - 1).abs().max()), 4)
    return out


def main():
    lm = cm.load_labels()
    out = {}
    for t in C.TOKENS:
        bal = cm.load_balances(t)
        raw = cm.load_transfers_raw(t)
        act = cm.active_addresses(cm.load_transfers(t))
        act_air = cm.active_addresses(cm.clean_transfers(raw, airdrop=False)[0])
        price = json.load(open(C.PRICES))[t]["price_usd"]
        pops = {"all": bal,
                "active": bal[bal["address"].isin(act)],
                "active_airdrop_kept": bal[bal["address"].isin(act_air)],
                "dust_floor": bal[bal["balance"] >= C.DUST_FLOOR],
                "value_floor": bal[bal["balance"] >= C.VALUE_FLOOR_USD / price]}
        iss = set(C.ISSUER_RESERVES.get(t, ()))
        types = {"all": set(), "excl_burn": set(C.BURN_ADDRS), "excl_burn_issuer": set(C.BURN_ADDRS) | iss}
        emap = cm.build_entity_map(t, lm, verbose=False)
        rows = []
        for (pn, p), (tn, ex), unit in itertools.product(pops.items(), types.items(), ("address", "entity")):
            d = p[~p["address"].isin(ex)]
            v = (d["balance"].values if unit == "address"
                 else d.groupby(cm.entity_key(d["address"], emap))["balance"].sum().values)
            rows.append({"population": pn, "address_type": tn, "unit": unit, "n": int(len(v)),
                         "hhi": round(cm.hhi(v), 1), "gini": round(cm.gini(v), 4)})
        df = pd.DataFrame(rows)
        nf = df[~df["population"].str.endswith("floor")]
        out[t] = {"rows": rows, "factors": factor_effects(df),
                  "nofloor_gini_min": float(nf["gini"].min()), "nofloor_gini_max": float(nf["gini"].max()),
                  "hhi_min": float(df["hhi"].min()), "hhi_max": float(df["hhi"].max()),
                  "gini_min": float(df["gini"].min()), "gini_max": float(df["gini"].max()),
                  "argmin": df.loc[df["hhi"].idxmin(), ["population", "address_type", "unit"]].to_dict(),
                  "argmax": df.loc[df["hhi"].idxmax(), ["population", "address_type", "unit"]].to_dict()}
        print(t, {k: v for k, v in out[t].items() if k != "rows"})
    cm.save_json(out, "spec_combos.json")


if __name__ == "__main__":
    main()
