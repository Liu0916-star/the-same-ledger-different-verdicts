# -*- coding: utf-8 -*-
"""make_numbers.py -- writes paper/numbers.tex from results/ (the only source of the paper's numbers).

The manuscript refers to these values as \\V{key}. Every key carries its source
file and field, so numbers.tex is itself a ledger of the numbers; paper_audit.py
checks that every \\V{key} in the text is defined and no \\tbd is left.
Every qualitative statement in the text that rests on numbers is also written
here as an assertion; if the numbers change and the text does not, the script
fails instead of letting the paper go silently wrong.

Usage: python make_numbers.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import config as C

R = C.ROOT / "results"
SPEC = {s: C.ROOT / f"results_spec_{s}" for s in ("keep_zero", "keep_airdrop", "raw")}
V1 = C.ROOT / "results_v1"
OUT = C.ROOT.parent / "paper" / "numbers.tex"
ROWS: list[tuple[str, str, str]] = []


def j(path: Path):
    return json.load(open(path))


def fmt_int(x) -> str:
    return f"{int(round(x)):,}".replace(",", "{,}")


def fmt(x, nd=0) -> str:
    if nd == 0:
        return fmt_int(x)
    s = f"{x:,.{nd}f}"
    return s.replace(",", "{,}")


def pct(x, nd=1) -> str:
    return f"{x * 100:.{nd}f}\\%"


def sgn(x, nd=3) -> str:
    """Signed number in math mode, so that negatives get a real minus sign."""
    return f"${x:+.{nd}f}$"


def put(key: str, value: str, src: str):
    ROWS.append((key, value, src))


def main():
    # ---------------------------------------------------------------- data
    dc = j(R / "v2_data_check.json")
    put("snapshot.block", fmt_int(dc["snapshot_block"]), "v2_data_check.json:snapshot_block")
    for t in C.TOKENS:
        k = t.lower()
        d, cl = dc[t], j(R / f"cleaning_{t}.json")
        put(f"{k}.tx_raw", fmt_int(d["n_transfers"]), f"v2_data_check.json:{t}.n_transfers")
        put(f"{k}.holders", fmt_int(d["v2_holders_with_genesis"]), f"v2_data_check.json:{t}.v2_holders_with_genesis")
        put(f"{k}.mintburn", fmt_int(cl["n_mint_burn"]), f"cleaning_{t}.json:n_mint_burn")
        put(f"{k}.zero", fmt_int(cl["n_zero_value"]), f"cleaning_{t}.json:n_zero_value")
        put(f"{k}.airdrop_tx", fmt_int(cl["n_airdrop_transfers"]), f"cleaning_{t}.json:n_airdrop_transfers")
        put(f"{k}.airdrop_senders", fmt_int(cl["n_airdrop_senders"]), f"cleaning_{t}.json:n_airdrop_senders")
        put(f"{k}.active_raw", fmt_int(cl["active_raw"]), f"cleaning_{t}.json:active_raw")
        put(f"{k}.active", fmt_int(cl["active_clean"]), f"cleaning_{t}.json:active_clean")
        put(f"{k}.nh.active", fmt_int(j(R / f"concentration_{t}.json")["grid"]["active|all"]["n"]),
            f"concentration_{t}.json:grid[active|all].n (holders)")
        put(f"{k}.nh.active_noair", fmt_int(j(SPEC["keep_airdrop"] / f"concentration_{t}.json")["grid"]["active|all"]["n"]),
            f"results_spec_keep_airdrop/concentration_{t}.json:grid[active|all].n")
        put(f"{k}.active_noair", fmt_int(cl["active_without_airdrop_rule"]),
            f"cleaning_{t}.json:active_without_airdrop_rule")
        drop = 1 - cl["active_clean"] / cl["active_without_airdrop_rule"]
        put(f"{k}.active_drop_pct", pct(drop, 0), f"1 - active_clean/active_without_airdrop_rule ({t})")
    gc = dc["LINK"]["genesis_check"]
    assert len(gc) == 1 and gc[0]["match_after_alloc"], gc
    put("link.genesis_balance", f"{int(gc[0]['onchain_balance']) / 1e18:.2f}",
        "v2_data_check.json:LINK.genesis_check[0].onchain_balance")

    # ---------------------------------------------------------------- graphs
    for t, sc in (("LINK", "1w"), ("LINK", "5w"), ("LINK", "full"), ("UNI", "1w")):
        c1 = j(R / f"c1_{t}_{sc}.json")
        put(f"{t.lower()}.nodes.{sc}", fmt_int(c1["n_nodes"]), f"c1_{t}_{sc}.json:n_nodes")
        put(f"{t.lower()}.anchors.{sc}", fmt_int(c1["n_anchors"]), f"c1_{t}_{sc}.json:n_anchors")

    # ---------------------------------------------------------------- concentration
    for t in C.TOKENS:
        k = t.lower()
        g = j(R / f"concentration_{t}.json")
        G = g["grid"]
        rows = {
            "all": G["all_holders|all"], "excl_burn": G["all_holders|excl_burn"],
            "excl_issuer": G["all_holders|excl_burn_issuer"], "active": G["active|all"],
        }
        for nm, m in rows.items():
            put(f"{k}.hhi.{nm}", fmt(m["hhi"]), f"concentration_{t}.json:grid[{nm}].hhi")
            put(f"{k}.gini.{nm}", f"{m['gini']:.4f}", f"concentration_{t}.json:grid[{nm}].gini")
        ent = G["all_holders|entity_merged"]
        put(f"{k}.hhi.entity", fmt(ent["hhi_entity"]), f"concentration_{t}.json:grid[all_holders|entity_merged].hhi_entity")
        put(f"{k}.gini.entity", f"{ent['gini_entity']:.4f}", "…gini_entity")
        put(f"{k}.fhhi.weekly", fmt(g["flow_hhi_addr"]), f"concentration_{t}.json:flow_hhi_addr")
        put(f"{k}.fhhi.entity", fmt(g["flow_hhi_entity"]), f"concentration_{t}.json:flow_hhi_entity")
        put(f"{k}.fhhi.entity_max", fmt(g["flow_hhi_entity_max"]), f"concentration_{t}.json:flow_hhi_entity_max")
        put(f"{k}.burn_pct", pct(g["burned_pct"] / 100, 2), f"concentration_{t}.json:burned_pct")
        put(f"{k}.issuer_pct", pct(g["reserve_pct"] / 100, 1), f"concentration_{t}.json:reserve_pct")
        put(f"{k}.label_cov", pct(g["entity_coverage_outflow"], 1), f"concentration_{t}.json:entity_coverage_outflow")
        put(f"{k}.top_entity_share", pct(g["top_entity_outflow_share"], 1), f"concentration_{t}.json:top_entity_outflow_share")
        # balance floors (act on the tail of the distribution)
        for fl in ("dust", "value"):
            m = G[f"{fl}_floor|all"]
            put(f"{k}.hhi.{fl}", fmt(m["hhi"]), f"concentration_{t}.json:grid[{fl}_floor|all].hhi")
            put(f"{k}.gini.{fl}", f"{m['gini']:.4f}", "…gini")
            put(f"{k}.n.{fl}", fmt_int(m["n"]), "…n")
        put(f"{k}.vfloor", fmt(g["value_floor_tokens"], 2), f"concentration_{t}.json:value_floor_tokens")
        put(f"{k}.price", fmt(g["price_usd"], 2), f"concentration_{t}.json:price_usd (Chainlink feed)")
        put(f"{k}.gini.drop_value", f"{G['all_holders|all']['gini'] - G['value_floor|all']['gini']:.4f}",
            "gini(all) - gini(value floor)")
        put(f"{k}.hhi.change_value", pct(abs(G['value_floor|all']['hhi'] / G['all_holders|all']['hhi'] - 1), 1),
            "|hhi(value floor)/hhi(all) - 1|")
        # active population with the airdrop transfers kept (keep_airdrop spec; zero-value still removed)
        gr = j(SPEC["keep_airdrop"] / f"concentration_{t}.json")["grid"]["active|all"]
        put(f"{k}.hhi.active_noair", fmt(gr["hhi"]), f"results_spec_keep_airdrop/concentration_{t}.json:grid[active|all].hhi")
        put(f"{k}.gini.active_noair", f"{gr['gini']:.4f}", "…gini")
        # balance range (main grid + both active populations + entity resolution)
        vals = [m["hhi"] for m in rows.values()] + [ent["hhi_entity"], gr["hhi"]]
        ginis = [m["gini"] for m in rows.values()] + [ent["gini_entity"], gr["gini"]]
        put(f"{k}.hhi.min", fmt(min(vals)), "min over balance specifications")
        put(f"{k}.hhi.max", fmt(max(vals)), "max over balance specifications")
        put(f"{k}.hhi.ratio", f"{max(vals) / min(vals):.0f}", "max/min")
        put(f"{k}.gini.range", f"{max(ginis) - min(ginis):.4f}", "max-min Gini over the same specifications")
        # flows: weekly vs pooled, direction
        s = j(R / f"c2_summary_{t}.json")
        put(f"{k}.fhhi.pooled", fmt(s["pooled_out"]["hhi"]), f"c2_summary_{t}.json:pooled_out.hhi")
        put(f"{k}.fhhi.in", fmt(s["weekly_in"]["hhi"]), f"c2_summary_{t}.json:weekly_in.hhi")
        put(f"{k}.fhhi.min", fmt(s["weekly_out"]["hhi_min"]), "c2_summary:weekly_out.hhi_min")
        put(f"{k}.fhhi.max", fmt(s["weekly_out"]["hhi_max"]), "c2_summary:weekly_out.hhi_max")
        put(f"{k}.fhhi.ratio_pooled", f"{s['weekly_over_pooled']:.2f}", "c2_summary:weekly_over_pooled")
        put(f"{k}.flow.gini", f"{s['weekly_out']['gini']:.3f}", "c2_summary:weekly_out.gini")
        put(f"{k}.flow.top1", pct(s["weekly_out"]["top1"], 1), "c2_summary:weekly_out.top1")
        put(f"{k}.flow.elite", pct(s["elite_share"], 1), "c2_summary:elite_share")
        put(f"{k}.flow.retention", pct(s["retention"], 0), "c2_summary:retention")
        put(f"{k}.flow.betgini", f"{s['betweenness_gini']:.3f}", "c2_summary:betweenness_gini")
        # balance top-k
        put(f"{k}.top1", pct(rows["all"]["top1"], 1), f"concentration_{t}.json:grid[all].top1")
        put(f"{k}.top10", pct(rows["all"]["top10"], 1), f"concentration_{t}.json:grid[all].top10")
    for t in C.TOKENS:
        k = t.lower()
        put(f"{k}.hhi.v1export", fmt(dc[t]["v1_hhi"]), f"v2_data_check.json:{t}.v1_hhi")
        put(f"{k}.gini.v1export", f"{dc[t]['v1_gini']:.4f}", f"v2_data_check.json:{t}.v1_gini")
        g = j(R / f"concentration_{t}.json")["grid"]
        put(f"{k}.active_share", pct(g["active|all"]["n"] / g["all_holders|all"]["n"], 1),
            f"concentration_{t}.json: active n / all n")
        s_ = j(R / f"c2_summary_{t}.json")
        put(f"{k}.fgini.weekly", f"{s_['weekly_out']['gini']:.3f}", "c2_summary:weekly_out.gini")
        put(f"{k}.fgini.pooled", f"{s_['pooled_out']['gini']:.3f}", "c2_summary:pooled_out.gini")
        put(f"{k}.fgini.in", f"{s_['weekly_in']['gini']:.3f}", "c2_summary:weekly_in.gini")
        for sp in ("raw", "overwrite"):
            q = j(C.ROOT / f"results_spec_{sp}" / f"c2_summary_{t}.json")
            put(f"{k}.fhhi.{sp}", fmt(q["weekly_out"]["hhi"]), f"results_spec_{sp}/c2_summary_{t}.json:weekly_out.hhi")
            put(f"{k}.fgini.{sp}", f"{q['weekly_out']['gini']:.3f}", "…weekly_out.gini")
        # summed vs overwritten edge weights (saved by 01_build_graph.legacy_compare)
        e = np.load(R / f"edgeweight_compare_{t}_1w.npz", allow_pickle=True)
        a_, b_ = e["pr_new"], e["pr_old"]
        loss = 1 - float(e["value_old"][0]) / float(e["value_new"][0])
        nodes = np.array(e["nodes"], dtype=object)
        top_a, top_b = set(nodes[np.argsort(-a_)[:50]]), set(nodes[np.argsort(-b_)[:50]])
        put(f"{k}.ew.loss_1w", pct(loss, 1), f"edgeweight_compare_{t}_1w.npz: 1 - value_old/value_new")
        put(f"{k}.ew.corr_1w", f"{np.corrcoef(a_, b_)[0, 1]:.2f}", "…corr(pr_new, pr_old)")
        put(f"{k}.ew.top50_1w", str(len(top_a & top_b)), "…top-50 overlap")
    a_ = j(R / "airdrop_case.json")
    put("link.airdrop_total_link_short", fmt(a_["total_link"]), "airdrop_case.json:total_link")
    put("v1.link.nodes.64w", fmt_int(j(V1 / "c1_LINK_64w.json")["n_nodes"]), "results_v1/c1_LINK_64w.json:n_nodes")
    # reference points
    us = j(C.ROOT / "benchmarks" / "us_bank_hhi.json")
    put("bench.us_bank", fmt(us["2026"]["hhi"]), "benchmarks/us_bank_hhi.json:2026.hhi")
    ob = j(C.ROOT / "benchmarks" / "other_benchmarks.json")
    sw = ob["sweden_credit_institutions_assets_hhi"]
    yr = max(sw)
    put("bench.sweden", fmt(sw[yr]), f"benchmarks/other_benchmarks.json:sweden[{yr}]")
    put("bench.sweden_year", yr, "latest ECB observation")
    cd = ob["global_card_networks"]
    put("bench.cards", fmt(cd["hhi_lower"]), "benchmarks/other_benchmarks.json:global_card_networks.hhi_lower")
    put("bench.cards_top4", fmt(cd["hhi_top4_only"]), "…hhi_top4_only")

    # ---------------------------------------------------------------- governance
    gv = j(R / "governance_UNI.json")
    d = gv["specs"]["delegated votes (main)"]
    put("uni.gov.deleg_share", pct(d["share_of_supply"], 1), "governance_UNI.json:specs[delegated].share_of_supply")
    put("uni.gov.n_delegates", fmt_int(d["n"]), "…n")
    put("uni.gov.n_quorum", fmt_int(d["nakamoto_quorum"]), "…nakamoto_quorum")
    put("uni.gov.n_half", fmt_int(d["nakamoto_half"]), "…nakamoto_half")
    put("uni.gov.n_eligible", fmt_int(d["n_each_above_threshold"]), "…n_each_above_threshold")
    put("uni.gov.top10", pct(d["top10_share"], 1), "…top10_share")
    put("uni.gov.hhi", fmt(d["hhi"]), "…hhi")
    for nm, key in (("balance: all holders", "all"), ("balance: excl. non-voting", "nonvoting"),
                    ("balance: excl. non-voting & custodial", "custodial")):
        b = gv["specs"][nm]
        put(f"uni.gov.bal.{key}.n_quorum", fmt_int(b["nakamoto_quorum"]), f"governance_UNI.json:specs[{nm}].nakamoto_quorum")
        put(f"uni.gov.bal.{key}.n_eligible", fmt_int(b["n_each_above_threshold"]), "…n_each_above_threshold")
        put(f"uni.gov.bal.{key}.n_half", fmt_int(b["nakamoto_half"]), "…nakamoto_half")
        put(f"uni.gov.bal.{key}.share", pct(b["share_of_supply"], 1), "…share_of_supply")
    st = gv["stratification"]
    put("uni.gov.inactive", fmt_int(st["eligible_inactive"]), "governance_UNI.json:stratification.eligible_inactive")
    put("uni.gov.inactive_pct", pct(st["eligible_inactive_share"], 0), "…eligible_inactive_share")
    for N in (10, 50, 100):
        put(f"uni.gov.overlap{N}", fmt_int(st[f"top{N}"]["overlap"]), f"…top{N}.overlap")
    rv = gv["revocable_share"]
    put("uni.gov.rev_l1", pct(rv["L1_governance_direct"], 2), "governance_UNI.json:revocable_share.L1")
    put("uni.gov.rev_l2", pct(rv["L2_protocol_owned"], 2), "…L2")
    put("uni.gov.rev_l3", pct(rv["L3_unidentified"], 1), "…L3")
    # quorum members of each balance row of Table 6
    sh = lambda a: f"\\texttt{{{a[:6]}\\ldots{{}}{a[-4:]}}}"
    for nm, key in (("balance: excl. non-voting", "nonvoting"), ("balance: excl. non-voting & custodial", "custodial")):
        mem = gv["specs"][nm]["quorum_members"]
        assert len(mem) == gv["specs"][nm]["nakamoto_quorum"] and all(m_["own_votes"] == 0 for m_ in mem)
        for i, m_ in enumerate(mem):
            put(f"uni.gov.{key}.m{i + 1}", sh(m_["address"]), f"governance_UNI.json:specs[{nm}].quorum_members[{i}]")
    assert gv["specs"]["balance: excl. non-voting & custodial"]["quorum_members"][0]["address"] \
        == gv["specs"]["balance: excl. non-voting"]["quorum_members"][1]["address"]
    fb = gv["fee_burns_window"]
    put("uni.burn.window", fmt(fb["total_uni"]), "governance_UNI.json:fee_burns_window.total_uni")
    put("uni.burn.n", fmt_int(fb["n"]), "…n")
    lots = sorted((float(k_) for k_, v_ in fb["amount_counts"].items() if v_ > 1))
    assert len(lots) == 2 and sum(v_ for v_ in fb["amount_counts"].values() if v_ == 1) == 1
    for lot, lk in ((lots[0], "lo"), (lots[1], "hi")):
        L = fb["lots"][f"{lot:.1f}"]
        put(f"uni.burn.{lk}.n", fmt_int(L["n"]), f"governance_UNI.json:fee_burns_window.lots[{lot}]")
        put(f"uni.burn.{lk}.senders", str(L["senders"]), "…senders")
        put(f"uni.burn.{lk}.bridged", fmt_int(L["via_bridges"]), "…via_bridges (config.UNI_FEE_BRIDGES)")
        put(f"uni.burn.{lk}.other", fmt_int(L["n"] - L["via_bridges"]), "n - via_bridges")
    odd = [k_ for k_, v_ in fb["amount_counts"].items() if v_ == 1]
    put("uni.burn.odd", odd[0], "governance_UNI.json:fee_burns_window.amount_counts (single record)")
    fm = j(R / "fee_mechanism.json")
    assert fm["window_start"]["threshold_uni"] == fm["window_end"]["threshold_uni"] == lots[1]
    assert fm["window_start"]["owner"] == fm["window_end"]["owner"] == "0x1a9c8182c09f50c8318d769245bea52c32be35bc"
    put("uni.firepit.threshold", fmt(fm["window_end"]["threshold_uni"]), "fee_mechanism.json:window_*.threshold_uni")
    put("uni.burn.lot_lo", fmt(lots[0]), "governance_UNI.json:fee_burns_window.amount_counts")
    put("uni.burn.lot_hi", fmt(lots[1]), "…")
    # L2 releasers: listed address == TokenJar.releaser(), threshold == the 2,000-UNI lot, read at the end of the window
    assert all(r["releaser_matches_page"] and r["threshold_uni"] == lots[0] and r["read_at"] == "window_end"
               for r in fm["l2"]), fm["l2"]
    put("uni.l2.chains", ", ".join(r["chain"] for r in fm["l2"][:-1]) + " and " + fm["l2"][-1]["chain"],
        "fee_mechanism.json:l2[].chain")
    # Chainlink feeds (Appendix D)
    ps = j(R / "prices_snapshot.json")
    for t in C.TOKENS:
        a_ = ps[t]["feed"]
        put(f"{t.lower()}.feed", "\\texttt{" + "\\allowbreak{}".join(a_[i:i + 10] for i in range(0, len(a_), 10)) + "}",
            f"prices_snapshot.json:{t}.feed")
        put(f"{t.lower()}.feed_answer", f"{ps[t]['answer_raw']}", "…answer_raw (8 decimals)")
        put(f"{t.lower()}.feed_round", ps[t]["round_id"], "…round_id")

    # ---------------------------------------------------------------- balance x position
    ex = j(R / "extra_stats.json")
    for t in C.TOKENS:
        k = t.lower()
        for sub, tag in (("positive_balance", "pos"), ("all_nodes", "all")):
            for m, mk in (("balance_vs_counterparties", "cp"), ("balance_vs_betweenness", "bet")):
                d = ex[t][sub][m]
                put(f"{k}.rho.{mk}.{tag}", sgn(d['rho']), f"extra_stats.json:{t}.{sub}.{m}.rho")
                lo, hi = d["ci95_bootstrap"]
                put(f"{k}.rho.{mk}.{tag}.ci", f"[{sgn(lo)}, {sgn(hi)}]", "…ci95_bootstrap")
            put(f"{k}.rho.n.{tag}", fmt_int(ex[t][sub]["balance_vs_counterparties"]["n"]), "…n")
        put(f"{k}.core_share", pct(ex[t]["core_cluster_share_of_graph"], 1), f"extra_stats.json:{t}.core_cluster_share_of_graph")
        put(f"{k}.repeat_full_pct", pct(ex[t]["repeat_share_full"], 1), f"extra_stats.json:{t}.repeat_share_full")
        put(f"{k}.repeat_1w_pct", pct(ex[t]["repeat_share_1w"], 1), f"extra_stats.json:{t}.repeat_share_1w")

    # ---------------------------------------------------------------- airdrop case
    a = j(R / "airdrop_case.json")
    put("airdrop.week", str(a["week_index"]), "airdrop_case.json:week_index")
    put("airdrop.week_tx", fmt_int(a["week_tx_raw"]), "…week_tx_raw")
    put("airdrop.week_ratio", f"{a['week_ratio_to_median']:.1f}", "…week_ratio_to_median")
    assert a["top2_days_share"] == 1.0
    d0, d1 = (pd.Timestamp(x) for x in a["top2_days"])
    put("airdrop.days", f"{min(d0, d1):%-d} and {max(d0, d1):%-d %B %Y}", "…top2_days (share 1.0)")
    put("airdrop.recipients", fmt_int(a["n_recipients"]), "…n_recipients")
    put("airdrop.single_pct", pct(a["recipients_single_pct"], 1), "…recipients_single_pct")
    put("airdrop.total_link", fmt(a["total_link"]), "…total_link")
    put("airdrop.tx_archived", fmt_int(a["n_transfers_archived_38"]), "…n_transfers_archived_38")
    assert a["archived_per_contract_min"] == a["archived_per_contract_max"]
    put("airdrop.per_contract", fmt_int(a["archived_per_contract_min"]), "…archived_per_contract_min (= max)")
    put("airdrop.tx_others", fmt_int(a["n_transfers_other"]), "…n_transfers_other")
    put("airdrop.archived_n", str(a["n_archived_38_hit"]), "…n_archived_38_hit (= archived contracts, all hit)")
    amts = sorted(a["amount_counts"], key=float)
    assert len(amts) == 2, amts
    put("airdrop.amt_lo", amts[0], "airdrop_case.json:amount_counts")
    put("airdrop.amt_hi", amts[1], "airdrop_case.json:amount_counts")
    assert a["others_suspicious"] == a["others_checked"]
    put("airdrop.others", fmt_int(a["others_checked"]), "…others_checked")
    put("airdrop.deployers", fmt_int(a["others_deployers"]), "…others_deployers")
    w, wo = a["with_airdrop"], a["without_airdrop"]
    put("airdrop.ntx_with", fmt_int(w["n_tx"]), "…with_airdrop.n_tx")
    put("airdrop.ntx_without", fmt_int(wo["n_tx"]), "…without_airdrop.n_tx")
    put("airdrop.naddr_with", fmt_int(w["n_addr"]), "…with_airdrop.n_addr")
    put("airdrop.naddr_without", fmt_int(wo["n_addr"]), "…without_airdrop.n_addr")
    put("airdrop.addr_added", fmt_int(w["n_addr"] - wo["n_addr"]), "with - without n_addr")
    for x in ("gini_in", "gini_out"):
        put(f"airdrop.{x}_with", f"{w[x]:.4f}", f"…with_airdrop.{x}")
        put(f"airdrop.{x}_without", f"{wo[x]:.4f}", f"…without_airdrop.{x}")
    put("airdrop.hhi_out_with", fmt(w["hhi_out"], 1), "…with_airdrop.hhi_out")
    put("airdrop.hhi_out_without", fmt(wo["hhi_out"], 1), "…without_airdrop.hhi_out")

    # ---------------------------------------------------------------- representation and brokers
    def f3(x):
        return f"{x:.3f}"
    for t in C.TOKENS:
        k = t.lower()
        c = j(R / f"c1_{t}_1w.json")
        put(f"c1.{k}.cent", f3(c["is_core_centrality"]["auc"]), f"c1_{t}_1w.json:is_core_centrality.auc")
        put(f"c1.{k}.struct", f3(c["is_core_raw_struct"]["auc"]), "…is_core_raw_struct.auc")
        put(f"c1.{k}.gnn", f"{c['gnn_is_core']['mean']:.3f} $\\pm$ {c['gnn_is_core']['sd_seed']:.3f}", "…gnn_is_core mean ± sd_seed")
        put(f"c1.{k}.n2v", f"{c['node2vec_is_core']['mean']:.3f} $\\pm$ {c['node2vec_is_core']['sd_seed']:.3f}", "…node2vec_is_core")
        put(f"c1.{k}.nofeat", f"{c['gnn_nofeat_is_core']['mean']:.3f} $\\pm$ {c['gnn_nofeat_is_core']['sd_seed']:.3f}", "…gnn_nofeat_is_core")
        put(f"c1.{k}.gnn_margin", sgn(c['gnn_is_core']['mean'] - c['is_core_raw_struct']['auc']), "gnn mean - raw_struct")
        ty = j(R / f"c3_typology_{t}.json")
        hb, nc = ty["hidden_brokers"], ty["node2vec_contrast"]
        put(f"{k}.brokers", str(hb["rank_ensemble_set"]), f"c3_typology_{t}.json:hidden_brokers.rank_ensemble_set")
        put(f"{k}.brokers_vote", str(hb["vote_consensus_set"]), "…vote_consensus_set")
        put(f"{k}.brokers_both", str(hb["rank_vote_overlap"]), "…rank_vote_overlap")
        put(f"{k}.brokers_bet_overlap", str(hb["overlap_size_matched"]), "…overlap_size_matched")
        fh = hb["freq_histogram"]
        put(f"{k}.brokers_ever", str(sum(fh.values())), "…sum(freq_histogram)")
        put(f"{k}.brokers_rare", str(fh.get("1/10", 0) + fh.get("2/10", 0)), "…freq 1/10 + 2/10")
        put(f"{k}.n2v_brokers", str(nc["n_node2vec"]), f"c3_typology_{t}.json:node2vec_contrast.n_node2vec")
        put(f"{k}.n2v_overlap", str(nc["overlap"]), "…overlap")
        put(f"{k}.n2v_top1_labelled", pct(nc["top1_labeled_frac_node2vec"], 0), "…top1_labeled_frac_node2vec")
        put(f"{k}.gnn_top1_labelled", pct(nc["top1_labeled_frac_gnn"], 0), "…top1_labeled_frac_gnn")
    main_b = {t: set(pd.read_csv(R / f"hidden_brokers_{t}.csv")["address"]) for t in C.TOKENS}
    put("shared.brokers", str(len(main_b["LINK"] & main_b["UNI"])), "hidden_brokers_LINK ∩ UNI")
    for t in C.TOKENS:
        v1b = set(pd.read_csv(V1 / f"hidden_brokers_{t}.csv")["address"])
        put(f"v1.{t.lower()}.brokers", str(len(v1b)), f"results_v1/hidden_brokers_{t}.csv")
        put(f"{t.lower()}.brokers_v1_kept", str(len(v1b & main_b[t])), "v1 ∩ v2 main")
    for t in C.TOKENS:
        v1b = set(pd.read_csv(V1 / f"hidden_brokers_{t}.csv")["address"])
        rawb = set(pd.read_csv(SPEC["raw"] / f"hidden_brokers_{t}.csv")["address"])
        put(f"{t.lower()}.brokers_v1_raw", str(len(v1b & rawb)), "results_v1 ∩ results_spec_raw hidden brokers")
    v1s = set(pd.read_csv(V1 / "hidden_brokers_LINK.csv")["address"]) & set(pd.read_csv(V1 / "hidden_brokers_UNI.csv")["address"])
    put("v1.shared.brokers", str(len(v1s)), "results_v1 LINK ∩ UNI")
    for sp in ("keep_zero", "keep_airdrop", "raw", "overwrite"):
        for t in C.TOKENS:
            bs = set(pd.read_csv(C.ROOT / f"results_spec_{sp}" / f"hidden_brokers_{t}.csv")["address"])
            put(f"spec.{t.lower()}.brokers.{sp}", str(len(bs)), f"results_spec_{sp}/hidden_brokers_{t}.csv")
            put(f"spec.{t.lower()}.overlap.{sp}", str(len(bs & main_b[t])), "∩ main")
    # verified identities (v1 records + v2 blind verification) and live tags
    import importlib
    rcm = importlib.import_module("11_random_control")
    kr = rcm.known_records()
    imap = dict(zip(kr["address"], kr["verified_identity"]))
    bl = pd.read_csv(C.ROOT / "verification" / "control_blind_v2.csv")
    imap.update(dict(zip(bl["address"], bl["verified_identity"])))

    def named(v):
        t = str(v).strip().lower()
        return bool(t) and t != "nan" and not t.startswith(rcm.GENERIC) and not t.startswith(rcm.CEX_PREFIXES)
    union = main_b["LINK"] | main_b["UNI"]
    shared = main_b["LINK"] & main_b["UNI"]
    assert all(a in imap for a in union), "a broker has no verification record"
    put("brokers.union", str(len(union)), "hidden_brokers LINK ∪ UNI")
    put("brokers.union_named", str(sum(named(imap[a]) for a in union)), "verified identities (v1 records + v2 blind)")
    put("shared.brokers_named", str(sum(named(imap[a]) for a in shared)), "…")
    live_ = pd.read_csv(C.ROOT / "verification" / "broker_live_labels_2026-10-06.csv").fillna("")
    ltag = dict(zip(live_["address"], live_["etherscan_name_tag"]))
    put("shared.brokers_names", ", ".join(sorted((ltag.get(a) or imap[a]) for a in shared if named(imap[a]))),
        "shared brokers: live Etherscan tag where present, else verified identity")
    live = pd.read_csv(C.ROOT / "verification" / "broker_live_labels_2026-10-06.csv").fillna("")
    assert set(live["address"]) == union
    put("brokers.live_tagged", str(int((live["etherscan_name_tag"] != "").sum())),
        "verification/broker_live_labels_2026-10-06.csv")
    put("brokers.live_untagged", str(int((live["etherscan_name_tag"] == "").sum())), "…")

    # node-bootstrap intervals for the AUC
    ac = j(R / "auc_ci.json")
    for t in C.TOKENS:
        k = t.lower()
        for nm, dd in ac[t]["diff"].items():
            key = {"graphsage-structural": "gnn_struct", "structural-centrality": "struct_cent",
                   "centrality-centrality_overwrite": "cent_ow"}[nm]
            put(f"aci.{k}.{key}", sgn(dd["diff"]), f"auc_ci.json:{t}.diff[{nm}].diff")
            put(f"aci.{k}.{key}.ci", f"[{sgn(dd['ci95'][0])}, {sgn(dd['ci95'][1])}]", "…ci95")

        # pooled out-of-fold AUC ("pooled" in Tables 3 and 4); single-seed GraphSAGE - structural
        a_, ss = ac[t]["auc"], ac[t]["single_seed"]
        for nm, key in (("centrality", "cent"), ("structural", "struct"), ("graphsage", "gnn_ens"),
                        ("centrality_overwrite", "cent_ow")):
            put(f"aci.{k}.pool.{key}", f"{a_[nm]['auc']:.3f}", f"auc_ci.json:{t}.auc.{nm}.auc (pooled out-of-fold)")
        put(f"aci.{k}.pool.gnn_single", f"{ss['auc_median']:.3f}", f"auc_ci.json:{t}.single_seed.auc_median")
        put(f"aci.{k}.single.diff", sgn(ss["diff_median"]), "…single_seed.diff_median")
        put(f"aci.{k}.single.range", f"{sgn(ss['diff_min'])} to {sgn(ss['diff_max'])}", "…diff_min, diff_max")
        put(f"aci.{k}.single.nexcl", str(ss["n_ci_excludes_zero"]), "…n_ci_excludes_zero")
        # the fold-averaged AUC must reproduce Table 4 (02_c1.py), or comparing the two is meaningless
        c1 = j(R / f"c1_{t}_1w.json")
        assert abs(ac[t]["fold_mean_auc"]["centrality"] - c1["is_core_centrality"]["auc"]) < 6e-4
        assert abs(ac[t]["fold_mean_auc"]["structural"] - c1["is_core_raw_struct"]["auc"]) < 6e-4
        assert abs(ac[t]["fold_mean_auc"]["graphsage_single_mean"] - c1["gnn_is_core"]["mean"]) < 6e-4

    # sensitivity of the broker criterion to its balance condition
    bs = j(R / "broker_balance_sens.json")
    for t in C.TOKENS:
        k = t.lower()
        b_ = bs[t]
        mb = b_["median_balance"]
        if mb == 0:
            put(f"{k}.med_bal", "0", "broker_balance_sens.json:median_balance")
        else:
            e = int(np.floor(np.log10(mb)))
            put(f"{k}.med_bal", f"${mb / 10 ** e:.1f}\\times10^{{{e}}}$", "broker_balance_sens.json:median_balance")
        put(f"{k}.zero_share", pct(b_["zero_share"], 0), "…zero_share")
        put(f"{k}.brokers_zero_bal", str(b_["main_brokers_zero_balance"]), "…main_brokers_zero_balance")
        for rule in ("zero", "dust"):
            put(f"bsens.{k}.{rule}.size", str(b_[rule]["size"]), f"…{rule}.size")
            put(f"bsens.{k}.{rule}.overlap", str(b_[rule]["overlap_main"]), f"…{rule}.overlap_main")
            put(f"bsens.{k}.{rule}.new", str(b_[rule]["size"] - b_[rule]["overlap_main"]), "size - overlap_main")

    dp = j(R / "broker_deploy.json")
    put("deploy.n_contracts", str(dp["n_contracts"]), "broker_deploy.json:n_contracts")
    put("deploy.n_after", str(dp["n_after"]), "broker_deploy.json:n_after (deployed after 2023-06-18)")
    put("deploy.n_eoa", str(dp["n"] - dp["n_contracts"]), "n - n_contracts")

    # control experiment
    rc = j(R / "random_control.json")["results"]["LINK"]
    ci = rc["ci95_clopper_pearson"]

    def ci_s(x):
        return f"[{x[0] * 100:.0f}\\%, {x[1] * 100:.0f}\\%]"
    put("ctl.broker_k", str(rc["broker_all"][0]), "random_control.json:LINK.broker_all")
    put("ctl.broker_pct", pct(rc["broker_all"][0] / rc["broker_all"][1], 0), "…")
    put("ctl.broker_ci", ci_s(ci["broker_all"]), "…ci95_clopper_pearson.broker_all")
    put("ctl.matched_k", str(rc["matched"][0]), "…matched")
    put("ctl.matched_pct", pct(rc["matched"][0] / rc["matched"][1], 0), "…")
    put("ctl.matched_ci", ci_s(ci["matched"]), "…")
    put("ctl.uniform_k", str(rc["uniform"][0]), "…uniform")
    put("ctl.uniform_pct", pct(rc["uniform"][0] / rc["uniform"][1], 0), "…")
    put("ctl.uniform_ci", ci_s(ci["uniform"]), "…")
    put("ctl.anchor_pct", pct(rc["broker_anchor_blind"][0] / rc["broker_anchor_blind"][1], 0), "…broker_anchor_blind")
    put("ctl.anchor_agree", f"{rc['anchor_agreement'][0]} of {rc['anchor_agreement'][1]}", "…anchor_agreement")
    put("ctl.p", f"{rc['p_value']:.2f}", "…p_value (one-sided Fisher)")
    put("ctl.p_mu", f"{rc['p_matched_gt_uniform']:.2f}", "…p_matched_gt_uniform")
    d0, d1 = rc["diff_ci95_newcombe"]
    put("ctl.diff_ci", f"[{sgn(d0 * 100, 0)}, {sgn(d1 * 100, 0)}]", "…diff_ci95_newcombe")
    rcx = j(R / "random_control_cex_as_named.json")["results"]["LINK"]
    put("ctl.uniform_k_cex", str(rcx["uniform"][0]), "random_control_cex_as_named.json:LINK.uniform")
    put("ctl.mdd", f"{rc['min_detectable_diff_80pct_power'] * 100:.0f}", "random_control.json:LINK.min_detectable_diff_80pct_power")
    put("ctl.pool_med_cp", fmt_int(rc["design"]["pool_median_cp"]), "random_control.json:LINK.design.pool_median_cp")
    put("ctl.broker_med_cp", fmt_int(rc["design"]["broker_median_cp"]), "…design.broker_median_cp")

    # ---------------------------------------------------------------- appendix
    for t in C.TOKENS:
        k = t.lower()
        cl_ = j(R / f"cleaning_{t}.json")
        for r in cl_["sensitivity"]:
            tag = f"n{r['N']}" if r["max_amt"] == C.AIRDROP_MAX_AMT else f"amt{r['max_amt']}"
            put(f"{k}.clean.{tag}.senders", fmt_int(r["senders"]), f"cleaning_{t}.json:sensitivity")
            put(f"{k}.clean.{tag}.tx", fmt_int(r["transfers"]), "…")
            put(f"{k}.clean.{tag}.active", fmt_int(r["active_clean"]), "…")
    for t, sc in (("LINK", "5w"), ("LINK", "full")):
        c = j(R / f"c1_{t}_{sc}.json")
        k = f"c1.{t.lower()}.{sc}"
        put(f"{k}.cent", f"{c['is_core_centrality']['auc']:.3f}", f"c1_{t}_{sc}.json")
        put(f"{k}.struct", f"{c['is_core_raw_struct']['auc']:.3f}", "…")
        put(f"{k}.gnn", f"{c['gnn_is_core']['mean']:.3f} $\\pm$ {c['gnn_is_core']['sd_seed']:.3f}", "…")
        put(f"{k}.base", f"{c['random_baseline_purity']:.5f}", "…random_baseline_purity")
    for t, sc in (("LINK", "1w"), ("LINK", "5w"), ("LINK", "full"), ("UNI", "1w")):
        c = j(R / f"c1_{t}_{sc}.json")
        k = f"c1.{t.lower()}.{sc}"
        put(f"{k}.pur.cent", f"{c['purity_centrality']:.4f}", f"c1_{t}_{sc}.json:purity_centrality")
        put(f"{k}.pur.struct", f"{c['purity_raw_struct']:.4f}", "…purity_raw_struct")
        put(f"{k}.pur.gnn", f"{c['purity']['mean']:.4f}", "…purity.mean")
        put(f"{k}.pur.ratio", f"{c['purity']['mean'] / c['purity_raw_struct']:.2f}", "gnn / struct purity")
        put(f"{k}.bal.cent", f"{c['balance_top5pct_centrality']['auc']:.3f}", "…balance_top5pct_centrality")
        put(f"{k}.bal.struct", f"{c['balance_top5pct_raw_struct']['auc']:.3f}", "…balance_top5pct_raw_struct")
        put(f"{k}.bal.gnn", f"{c['gnn_balance']['mean']:.3f}", "…gnn_balance.mean")
    # body of the cluster table: 8 clusters per token, by core rate, side by side
    ty = {t: sorted(j(R / f"c3_typology_{t}.json")["typology"].values(),
                    key=lambda c: (-c["core_rate"], -c["size"])) for t in C.TOKENS}
    rows_ = []
    for a_, b_ in zip(ty["LINK"], ty["UNI"]):
        cells = []
        for c in (a_, b_):
            cells += [fmt_int(c["size"]), f"{c['core_rate'] * 100:.2f}\\%",
                      fmt_int(c["med_counterparties"]), fmt(c["med_balance"], 2)]
        rows_.append(" & ".join(cells[:4]) + " & & " + " & ".join(cells[4:]) + " \\\\")
    put("tab.typology", " ".join(rows_), "c3_typology_{LINK,UNI}.json, clusters sorted by core rate")
    put("link.core.size", fmt_int(ty["LINK"][0]["size"]), "c3_typology_LINK.json top cluster")
    put("uni.core.size", fmt_int(ty["UNI"][0]["size"]), "c3_typology_UNI.json top cluster")
    for t in C.TOKENS:
        c = ty[t][0]
        put(f"{t.lower()}.core.medbal", fmt(c["med_balance"], 0), f"c3_typology_{t}.json top cluster med_balance")
        put(f"{t.lower()}.core.medcp", fmt_int(c["med_counterparties"]), "…med_counterparties")
        put(f"{t.lower()}.core.rate", pct(c["core_rate"], 1), "…core_rate")

    # Appendix B: body of the data-specification table (from results/spec_compare.json)
    sc = j(R / "spec_compare.json")
    lab = {"main": "\\textbf{Main}", "keep_zero": "Zero-value kept", "keep_airdrop": "Airdrop kept",
           "raw": "Both kept", "overwrite": "Edges overwritten"}
    rows_ = []
    for sp, nm in lab.items():
        a_, b_ = sc["LINK"][sp], sc["UNI"][sp]
        cells = [nm]
        for x in (a_, b_):
            cells += [fmt_int(x["graph_nodes"]), f"{x['auc_struct']:.3f}", f"{x['auc_gnn']:.3f}",
                      f"{x['auc_balance_gnn']:.3f}", f"{x['n_brokers']} / {x['brokers_overlap_main']}"]
        rows_.append(" & ".join(cells) + " \\\\")
    put("tab.specdata", " ".join(rows_), "results/spec_compare.json")
    # edge weights: summed (main) vs overwritten, same cleaning specification
    for t in C.TOKENS:
        for sp in ("main", "overwrite"):
            x = sc[t][sp]
            k = f"ew.{t.lower()}.{sp}"
            put(f"{k}.cent", f"{x['auc_centrality']:.3f}", f"spec_compare.json:{t}.{sp}.auc_centrality")
            put(f"{k}.gnn", f"{x['auc_gnn']:.3f}", "…auc_gnn")
            put(f"{k}.purratio", f"{x['purity_ratio']:.2f}", "…purity_ratio")
            put(f"{k}.coremedbal", fmt(x["core_cluster_med_balance"]), "…core_cluster_med_balance")
            put(f"{k}.rho", sgn(x['rho_bal_cp']), "…rho_bal_cp")
            put(f"{k}.brokers", str(x["n_brokers"]), "…n_brokers")
            put(f"{k}.overlap", str(x["brokers_overlap_main"]), "…brokers_overlap_main")
    put("ew.shared.main", str(sc["shared_brokers"]["main"]), "spec_compare.json:shared_brokers.main")
    put("ew.shared.overwrite", str(sc["shared_brokers"]["overwrite"]), "…overwrite")
    leg = j(C.LEGACY / "c3_typology.json")["typology"]
    lc = max(leg.values(), key=lambda c: (c["core_rate"], c["size"]))
    put("v16.core.medbal", f"{lc['med_balance']:.2f}", "results_v16_legacy/c3_typology.json: highest core-rate cluster")

    # Appendix B: the full grid of combinations
    cb = j(R / "spec_combos.json")
    for t in C.TOKENS:
        k = t.lower()
        put(f"combo.{k}.hhi_min", fmt(cb[t]["hhi_min"]), f"spec_combos.json:{t}.hhi_min")
        put(f"combo.{k}.hhi_max", fmt(cb[t]["hhi_max"]), "…hhi_max")
        put(f"combo.{k}.ratio", f"{cb[t]['hhi_max'] / cb[t]['hhi_min']:.0f}", "max/min")
        put(f"combo.{k}.gini_min", f"{cb[t]['gini_min']:.4f}", "…gini_min")
        put(f"combo.{k}.gini_max", f"{cb[t]['gini_max']:.4f}", "…gini_max")
    pl = {"all": "All", "active": "Active", "active_airdrop_kept": "Active, airdrop kept",
          "dust_floor": "$\\geq$ 0.01", "value_floor": "$\\geq$ USD 100"}
    tl = {"all": "All", "excl_burn": "Excl.\\ burn", "excl_burn_issuer": "Excl.\\ burn, issuer"}
    rows_ = []
    for a_, b_ in zip(cb["LINK"]["rows"], cb["UNI"]["rows"]):
        assert (a_["population"], a_["address_type"], a_["unit"]) == (b_["population"], b_["address_type"], b_["unit"])
        rows_.append(f"{pl[a_['population']]} & {tl[a_['address_type']]} & {a_['unit'].capitalize()} & "
                     f"{fmt(a_['hhi'])} & {a_['gini']:.4f} & {fmt(b_['hhi'])} & {b_['gini']:.4f} \\\\")
    put("tab.combos", " ".join(rows_), "spec_combos.json rows (5 populations × 3 address types × 2 units)")
    # largest effect of each factor alone (three-way conclusion: top / tail / both)
    for t in C.TOKENS:
        k = t.lower()
        put(f"combo.{k}.gini_range_nofloor", f"{cb[t]['nofloor_gini_max'] - cb[t]['nofloor_gini_min']:.4f}",
            f"spec_combos.json:{t}.nofloor_gini_max - nofloor_gini_min (18 cells without floors)")
        nf = [r for r in cb[t]["rows"] if not r["population"].endswith("floor")]
        put(f"combo.{k}.nf_hhi_min", fmt(min(r["hhi"] for r in nf)), f"spec_combos.json:{t} rows without floors, min hhi")
        put(f"combo.{k}.nf_hhi_max", fmt(max(r["hhi"] for r in nf)), "…max hhi")
        put(f"combo.{k}.nf_hhi_ratio", f"{max(r['hhi'] for r in nf) / min(r['hhi'] for r in nf):.0f}", "max/min")
        for f, e in cb[t]["factors"].items():
            put(f"fx.{k}.{f}.hhi", f"{e['hhi_ratio_max']:.1f}", f"spec_combos.json:{t}.factors.{f}.hhi_ratio_max")
            put(f"fx.{k}.{f}.gini", f"{e['gini_change_max']:.4f}", "…gini_change_max")
        D = {(r["population"], r["address_type"], r["unit"]): r for r in cb[t]["rows"]}
        a_, v_ = 1 - D[("all", "all", "address")]["gini"], 1 - D[("value_floor", "all", "address")]["gini"]
        put(f"{k}.omg.all", f"{a_:.4f}", "1 - gini(all holders)")
        put(f"{k}.omg.value", f"{v_:.4f}", "1 - gini(value floor)")
        put(f"{k}.omg.ratio", f"{v_ / a_:.1f}", "ratio")
    ao = j(R / "cleaning_LINK.json")["airdrop_only_holders"]
    assert ao["n_addresses"] == ao["n_holders"]
    put("link.airdrop_only.n", fmt_int(ao["n_holders"]), "cleaning_LINK.json:airdrop_only_holders.n_holders")
    put("link.airdrop_only.med", fmt(ao["median_balance"], 1), "…median_balance")
    put("link.airdrop_only.dust", fmt_int(ao["n_below_dust_floor"]), "…n_below_dust_floor")
    top = [cb[t]["factors"][f] for t in C.TOKENS for f in ("address_type", "entity")]
    put("fx.top.hhi_max", f"{max(e['hhi_ratio_max'] for e in top):.1f}", "max HHI ratio, address type / entity, both tokens")
    put("fx.top.gini_max", f"{max(e['gini_change_max'] for e in top):.4f}", "max Gini change, address type / entity, both tokens")
    put("floor.hhi_change_max", pct(max(cb[t]["factors"]["floor"]["hhi_change_max"] for t in C.TOKENS), 1),
        "max |hhi(floor)/hhi(all) - 1| over both tokens, both floors and every address type × unit")

    # ---------------------------------------------------------------- qualitative claims
    # Every qualitative statement in the text that follows from numbers is an
    # assertion here. If the numbers change and the text does not, generation
    # fails rather than letting the paper go silently wrong.
    cl = {t: j(R / f"concentration_{t}.json") for t in C.TOKENS}
    cs = {t: j(R / f"c2_summary_{t}.json") for t in C.TOKENS}
    claims = {
        "§4 UNI active population > 1,800 and > 2,500": cl["UNI"]["grid"]["active|all"]["hhi"] > 2500,
        "§4 LINK active population (cleaned) < 1,800": cl["LINK"]["grid"]["active|all"]["hhi"] < 1800,
        "§4 mean flow HHI < 1,800 on both ledgers": all(cs[t]["weekly_out"]["hhi"] < 1800 for t in C.TOKENS),
        "§4 every weekly address-level flow HHI < 1,800 on both ledgers": all(cs[t]["weekly_out"]["hhi_max"] < 1800 for t in C.TOKENS),
        "§4 LINK largest entity-level week > 1,500 and < 1,800": 1500 < cl["LINK"]["flow_hhi_entity_max"] < 1800,
        "§4 UNI largest entity-level week < 1,500": cl["UNI"]["flow_hhi_entity_max"] < 1500,
        "§4 UNI HHI rises when the burn address is excluded": cl["UNI"]["grid"]["all_holders|excl_burn"]["hhi"] > cl["UNI"]["grid"]["all_holders|all"]["hhi"],
        "§4 flow direction barely matters (< 5%)": all(abs(cs[t]["weekly_in"]["hhi"] / cs[t]["weekly_out"]["hhi"] - 1) < 0.05 for t in C.TOKENS),
        "§4 weekly mean > pooled window": all(cs[t]["weekly_over_pooled"] > 1 for t in C.TOKENS),
        "§4 entity resolution only raises the balance HHI": all(cl[t]["grid"]["all_holders|entity_merged"]["hhi_entity"] > cl[t]["grid"]["all_holders|all"]["hhi"] for t in C.TOKENS),
        "§6 N(40M) in delegated votes > in balances (non-voting excluded)": gv["specs"]["delegated votes (main)"]["nakamoto_quorum"] > gv["specs"]["balance: excl. non-voting"]["nakamoto_quorum"],
        "§6 the two addresses behind the balance-based N=2 have zero votes": all(x["own_votes"] == 0 for x in gv["balance_spec_top2"]),
        "§6 no proposal-eligible delegate among the top-100 senders": gv["stratification"]["top100"]["overlap"] == 0,
        "§6 the top-100 senders delegate none of their own balance": gv["stratification"]["top100"]["own_balance_delegated_share"] == 0,
        "§5 the only unnamed shared broker is one unlabelled routing contract":
            [imap[a] for a in shared if not named(imap[a])] == ["Unlabelled routing contract"],
        "§5 the broker union contains an MEV bot": any(str(imap[a]).lower().startswith("mev") for a in union),
        "§5 the broker union contains exactly one CEX hot wallet": sum(str(imap[a]).lower().startswith(rcm.CEX_PREFIXES)
                                          or str(imap[a]).lower() == "unknown" and "htx" in str(live.set_index("address").loc[a, "etherscan_name_tag"]).lower()
                                          for a in union) == 1,
        "§5 main matched-control test not significant": rc["p_value"] > 0.05,
        "§5 matched vs uniform in the expected direction but not significant": rc["matched"][0] / rc["matched"][1] > rc["uniform"][0] / rc["uniform"][1] and rc["p_matched_gt_uniform"] > 0.05,
        "§5 blind anchors agree with the records": rc["anchor_agreement"][0] == rc["anchor_agreement"][1],
        "§4 LINK active HHI with the airdrop kept equals the all-holder HHI (< 1%)":
            abs(j(SPEC["keep_airdrop"] / "concentration_LINK.json")["grid"]["active|all"]["hhi"]
                / cl["LINK"]["grid"]["all_holders|all"]["hhi"] - 1) < 0.01,
        "§9 LINK cleaned active HHI is nearly three times the all-holder HHI (2.5–3×)":
            2.5 < cl["LINK"]["grid"]["active|all"]["hhi"] / cl["LINK"]["grid"]["all_holders|all"]["hhi"] < 3,
        "§B thresholds 0.1 and 0.01 give the same result":
            {(r["senders"], r["transfers"]) for r in j(R / "cleaning_LINK.json")["sensitivity"] if r["N"] == C.AIRDROP_N} .__len__() == 1,
        "§C the CEX rule changes only the uniform control group": all(rcx[g] == rc[g] for g in ("broker_all", "matched", "broker_anchor_blind"))
            and rcx["p_value"] == rc["p_value"],
        "§A on both ledgers the core cluster has the highest core rate and median balance": all(
            j(R / f"c3_typology_{t}.json")["wealth_power"]["top_core_cluster"]
            == j(R / f"c3_typology_{t}.json")["wealth_power"]["top_balance_cluster"] for t in C.TOKENS),
        "§1/§5 matched control and brokers resolve at similar rates (< 10 pp)":
            abs(rc["broker_all"][0] / rc["broker_all"][1] - rc["matched"][0] / rc["matched"][1]) < 0.10,
        "§B UNI main == keep_airdrop and keep_zero == raw (determinism)":
            sc["UNI"]["main"] == sc["UNI"]["keep_airdrop"] and sc["UNI"]["keep_zero"] == sc["UNI"]["raw"],
        "§B without the airdrop, GNN and structural features predict LINK balance equally (< 0.02)":
            abs(sc["LINK"]["main"]["auc_balance_gnn"] - sc["LINK"]["main"]["auc_balance_struct"]) < 0.02
            and sc["LINK"]["keep_airdrop"]["auc_balance_gnn"] - sc["LINK"]["keep_airdrop"]["auc_balance_struct"] > 0.05,
        "§4.6 overwriting alone does not reproduce the v1 reversal (core median balance far above v16)":
            sc["LINK"]["overwrite"]["core_cluster_med_balance"] > 100 * lc["med_balance"],
        "§4.6 overwriting changes the broker sets and the shared count":
            all(sc[t]["overwrite"]["brokers_overlap_main"] < sc[t]["overwrite"]["n_brokers"] for t in C.TOKENS)
            and sc["shared_brokers"]["overwrite"] != sc["shared_brokers"]["main"],
        "§B senders added at N=100 spread over many weeks (>= 10 weeks, no week > 50%)":
            j(R / "cleaning_LINK.json")["extra_senders_lowest_N"]["n_weeks"] >= 10
            and j(R / "cleaning_LINK.json")["extra_senders_lowest_N"]["max_week_share"] < 0.5,
        "§4 the value floor moves the Gini more than any other row (both ledgers)": all(
            (cl[t]["grid"]["all_holders|all"]["gini"] - cl[t]["grid"]["value_floor|all"]["gini"])
            > max(m["gini"] for kk, m in cl[t]["grid"].items() if "floor" not in kk and "gini" in m)
            - min(m["gini"] for kk, m in cl[t]["grid"].items() if "floor" not in kk and "gini" in m)
            for t in C.TOKENS),
        "§4 three-way: Gini change from address type / entity < half the floor effect": all(
            max(cb[t]["factors"][f]["gini_change_max"] for f in ("address_type", "entity"))
            < cb[t]["factors"]["floor"]["gini_change_max"] / 2 for t in C.TOKENS),
        "§4 three-way: floors change the HHI < 0.5%; other factors > 1.9×": all(
            cb[t]["factors"]["floor"]["hhi_change_max"] < 0.005
            and min(cb[t]["factors"][f]["hhi_ratio_max"] for f in ("activity", "address_type", "entity")) > 1.9
            for t in C.TOKENS),
        "§4 three-way: LINK activity Gini change exceeds address type / entity and half the floor":
            cb["LINK"]["factors"]["activity"]["gini_change_max"]
            > max(cb["LINK"]["factors"][f]["gini_change_max"] for f in ("address_type", "entity"))
            and cb["LINK"]["factors"]["activity"]["gini_change_max"] > cb["LINK"]["factors"]["floor"]["gini_change_max"] / 2,
        "§5.1 single-seed GraphSAGE: interval excludes zero for at most one seed; median below the ensemble": all(
            j(R / "auc_ci.json")[t]["single_seed"]["n_ci_excludes_zero"] <= 1
            and j(R / "auc_ci.json")[t]["single_seed"]["diff_median"]
            < j(R / "auc_ci.json")[t]["diff"]["graphsage-structural"]["diff"] for t in C.TOKENS),
        "§4 the value floor changes the HHI by < 1% (both ledgers)": all(
            abs(cl[t]["grid"]["value_floor|all"]["hhi"] / cl[t]["grid"]["all_holders|all"]["hhi"] - 1) < 0.01
            for t in C.TOKENS),
        "§9 about half of the broker union are named protocols (40–60%)":
            0.4 <= sum(named(imap[a]) for a in union) / len(union) <= 0.6,
        "§5.2 subgraph median balance: LINK of order 1e-5, UNI 0":
            1e-6 <= bs["LINK"]["median_balance"] < 1e-4 and bs["UNI"]["median_balance"] == 0,
        "§5.2 the strict-zero set is a subset of the main set": all(bs[t]["zero"]["size"] == bs[t]["zero"]["overlap_main"] for t in C.TOKENS),
        "§5.5 the contracts deployed before the scrape are exactly MetaMask Swaps Spender and LI.FI Diamond": sorted(
            live.set_index("address").loc[r["address"], "etherscan_name_tag"]
            for r in dp["rows"] if r["after_label_scrape"] is False)
            == ["LI.FI: LiFi Diamond", "MetaMask: Swaps Spender"],
        "§5.3 uncleaned, the new pipeline recovers most v1 LINK brokers (>= 80%); UNI unchanged":
            len(set(pd.read_csv(V1 / "hidden_brokers_LINK.csv")["address"]) & set(pd.read_csv(SPEC["raw"] / "hidden_brokers_LINK.csv")["address"]))
            >= 0.8 * len(set(pd.read_csv(V1 / "hidden_brokers_LINK.csv")["address"]))
            and sc["UNI"]["raw"]["n_brokers"] == sc["UNI"]["main"]["n_brokers"],
        "§5.1 structural features beat centrality: interval excludes 0 (both ledgers)":
            all(j(R / "auc_ci.json")[t]["diff"]["structural-centrality"]["ci95"][0] > 0 for t in C.TOKENS),
        "§5.1 GraphSAGE margin is small, lower bound near 0 (< 0.02, upper < 0.15)":
            all(0 < j(R / "auc_ci.json")[t]["diff"]["graphsage-structural"]["ci95"][0] < 0.02
                and j(R / "auc_ci.json")[t]["diff"]["graphsage-structural"]["ci95"][1] < 0.15 for t in C.TOKENS),
        "§4.6 overwriting does not significantly change the centrality AUC (interval contains 0)":
            all(j(R / "auc_ci.json")[t]["diff"]["centrality-centrality_overwrite"]["ci95"][0] < 0
                < j(R / "auc_ci.json")[t]["diff"]["centrality-centrality_overwrite"]["ci95"][1] for t in C.TOKENS),
        "§7 sender-side HHI with / without the airdrop differ by < 0.1%": abs(a["with_airdrop"]["hhi_out"] / a["without_airdrop"]["hhi_out"] - 1) < 1e-3,
        "§7 receiver-side Gini is higher with the airdrop": a["with_airdrop"]["gini_in"] > a["without_airdrop"]["gini_in"],
    }
    bad = [k for k, ok in claims.items() if not ok]
    for k, ok in claims.items():
        print(f"  [{'OK' if ok else 'X '}] {k}")
    if bad:
        raise SystemExit(f"[X] {len(bad)} qualitative statements disagree with the numbers; fix the text first")

    # ---------------------------------------------------------------- write
    lines = ["%% Generated by gnn-decentralization/make_numbers.py. Do not edit by hand.",
             "%% key = value    % source"]
    for k, v, src in ROWS:
        lines.append(f"\\expandafter\\def\\csname v@{k}\\endcsname{{{v}}}  % {src}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(ROWS)} numbers → {OUT}")


if __name__ == "__main__":
    main()
