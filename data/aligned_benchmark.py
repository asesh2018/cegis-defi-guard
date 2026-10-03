import numpy as np
import pandas as pd
import os

def run_aligned_benchmark():
    np.random.seed(42)
    blocks = 100
    T = 80000          # Liquidation threshold ($80,000)
    M_star = 808       # Minimum decision margin

    p_ref = np.zeros(blocks)
    prices = np.zeros((blocks, 5))
    is_stale = np.zeros((blocks, 5), dtype=bool)

    # Regimes:
    # 0-29: Normal trading (Healthy)
    # 30-44: Correlated Flash Loan Attack on UniV3 (Spot & TWAP diverge sharply)
    # 45-49: Correlated Stealth Micro-Deviation ($1 attack on even quorum where Feed 4 is stale)
    # 50-74: Genuine Market Crash (All feeds drop 20% to ~64,400)
    # 75-99: Post-crash stabilization
    for b in range(blocks):
        if b < 30:
            p_ref[b] = 80500 + np.random.normal(0, 40)
            prices[b] = p_ref[b] + np.random.normal(0, 30, 5)
        elif 30 <= b < 45:
            # Flash Loan on UniV3: Feed 2 (Spot) plunges to 40k, Feed 3 (TWAP) dragged to 62k
            p_ref[b] = 80500 + np.random.normal(0, 40)
            prices[b, 0] = p_ref[b] + np.random.normal(0, 30) # Binance (Honest)
            prices[b, 1] = p_ref[b] + np.random.normal(0, 30) # Coinbase (Honest)
            prices[b, 2] = 40000 + np.random.normal(0, 80)   # Corrupted UniV3 Spot
            prices[b, 3] = 62000 + np.random.normal(0, 80)   # Corrupted UniV3 TWAP
            prices[b, 4] = p_ref[b] + np.random.normal(0, 30) # Ref Feed (Honest)
        elif 45 <= b < 50:
            # Stealth Micro-Deviation: Feed 4 is stale (latent relayer delay) -> 4 usable feeds!
            p_ref[b] = 80808
            prices[b, 0] = 80001 # CEX Binance (Honest)
            prices[b, 1] = 80000 # CEX Coinbase (Honest)
            prices[b, 2] = 79999 # Corrupted UniV3 Spot
            prices[b, 3] = 79996 # Corrupted UniV3 TWAP
            prices[b, 4] = 85000 # Stale relayer value
            is_stale[b, 4] = True
        elif 50 <= b < 75:
            # Genuine Crash: Market drops 20%
            crash_factor = 0.80 - (b - 50) * 0.004
            p_ref[b] = 80500 * max(crash_factor, 0.76)
            prices[b] = p_ref[b] + np.random.normal(0, 50, 5)
        else:
            p_ref[b] = 64000 + np.random.normal(0, 40)
            prices[b] = p_ref[b] + np.random.normal(0, 30, 5)

    definitely_liquidatable = p_ref <= (T - M_star)
    definitely_healthy = p_ref >= (T + M_star)
    total_valid = int(np.sum(definitely_liquidatable))

    # Evaluate 4 concrete architectures:
    # 1. Unprotected Spot Feed (Relies strictly on DEX Spot)
    # 2. TWAP-Gated Spot (Requires Spot and TWAP within 2%)
    # 3. Naive 5-Feed Median (Takes median without provenance or MAD)
    # 4. Synthesized Guard (u_min=4, r_min=3, M_bps=100 bps)

    models = ["Spot Only", "TWAP-Gated", "Naive Median", "Synthesized Guard"]
    results = {m: {"unsafe": 0, "preserved": 0, "deferred": 0} for m in models}

    for b in range(blocks):
        p = prices[b]
        valid_b = definitely_liquidatable[b]
        healthy_b = definitely_healthy[b]

        # Model 1: Spot Only
        spot_p = p[2]
        spot_liq = spot_p < T
        if spot_liq and healthy_b: results["Spot Only"]["unsafe"] += 1
        if valid_b:
            if spot_liq: results["Spot Only"]["preserved"] += 1
            else: results["Spot Only"]["deferred"] += 1

        # Model 2: TWAP-Gated (Rejects if |Spot - TWAP| > 2%)
        twap_p = p[3]
        twap_agree = abs(spot_p - twap_p) * 10000 <= 200 * twap_p
        twap_liq = (spot_p < T) and twap_agree
        if twap_liq and healthy_b: results["TWAP-Gated"]["unsafe"] += 1
        if valid_b:
            if twap_liq: results["TWAP-Gated"]["preserved"] += 1
            else: results["TWAP-Gated"]["deferred"] += 1

        # Model 3: Naive Median (Ignores staleness and provenance)
        naive_p = np.median(p)
        naive_liq = naive_p < T
        if naive_liq and healthy_b: results["Naive Median"]["unsafe"] += 1
        if valid_b:
            if naive_liq: results["Naive Median"]["preserved"] += 1
            else: results["Naive Median"]["deferred"] += 1

        # Model 4: Synthesized Guard
        # Filter stale feeds
        active_idx = [i for i in range(5) if not is_stale[b, i]]
        active_p = p[active_idx]
        active_g = [1, 2, 3, 3, 4]
        active_families = len(set([active_g[i] for i in active_idx]))
        u_count = len(active_p)

        if u_count % 2 == 1:
            guard_med = np.median(active_p)
        else:
            # On even quorum, standard EVM interpolated median
            sorted_act = np.sort(active_p)
            mid = u_count // 2
            guard_med = np.floor((sorted_act[mid - 1] + sorted_act[mid]) / 2.0)

        mad = np.median(np.abs(active_p - guard_med))
        dispersion_ok = (mad * 10000) <= (100 * guard_med)
        guard_accept = (u_count >= 4) and (active_families >= 3) and dispersion_ok
        guard_liq = guard_accept and (guard_med < T)

        if guard_liq and healthy_b: results["Synthesized Guard"]["unsafe"] += 1
        if valid_b:
            if guard_liq: results["Synthesized Guard"]["preserved"] += 1
            else: results["Synthesized Guard"]["deferred"] += 1
        elif healthy_b and not guard_accept and (30 <= b < 50):
            # Track deferrals during active attack regimes
            results["Synthesized Guard"]["deferred"] += 1

    # Print clean verification table
    print("==========================================================================================")
    print(f"ALIGNED BENCHMARK RESULTS (100 Blocks, Total Valid Liquidation Blocks: {total_valid})")
    print("==========================================================================================")
    print(f"{'Defense Model':<20} | {'Unsafe Liq.':<12} | {'Unsafe Rate':<12} | {'Valid Preserved':<16} | {'Preserve Rate':<14} | {'Deferrals'}")
    print("------------------------------------------------------------------------------------------")
    for m in models:
        r = results[m]
        u_rate = (r["unsafe"] / blocks) * 100
        p_rate = (r["preserved"] / total_valid) * 100
        pres_str = f"{r['preserved']} / {total_valid}"
        print(f"{m:<20} | {r['unsafe']:<12} | {u_rate:>10.1f}% | {pres_str:<16} | {p_rate:>12.1f}% | {r['deferred']}")
    print("==========================================================================================")

    # Save to CSV
    os.makedirs(os.path.expanduser("~/cegis-defi-guard/data"), exist_ok=True)
    csv_file = os.path.expanduser("~/cegis-defi-guard/data/benchmark_trace_100blocks.csv")
    df = pd.DataFrame(prices, columns=[f"feed_{i}" for i in range(5)])
    df["p_ref"] = p_ref
    df["definitely_liquidatable"] = definitely_liquidatable
    df["definitely_healthy"] = definitely_healthy
    df.to_csv(csv_file, index=False)
    print(f"[+] Serialized exact dataset to: {csv_file}")

if __name__ == "__main__":
    run_aligned_benchmark()
