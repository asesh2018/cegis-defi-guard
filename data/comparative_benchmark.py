import numpy as np
import pandas as pd
import os

def generate_and_save_benchmark_data():
    np.random.seed(42)
    blocks = 100
    T = 80000          # Liquidation threshold
    delta_bps = 200    # OVer-style static deviation bound (2%)
    velocity_limit = 0.03  # SecPLF-style max price change per block (3%)
    ormer_window = 10  # Ormer-style sliding observation window

    p_ref = np.zeros(blocks)
    prices = np.zeros((blocks, 5))

    for b in range(blocks):
        if b < 30:
            # Regime 1: Normal Trading (Healthy)
            p_ref[b] = 80500 + np.random.normal(0, 50)
            noise = np.random.normal(0, 40, 5)
            prices[b] = p_ref[b] + noise
        elif 30 <= b < 45:
            # Regime 2a: Flash-loan manipulation on UniV3 pool
            p_ref[b] = 80500 + np.random.normal(0, 50)
            prices[b, 0] = p_ref[b] + np.random.normal(0, 40) # Binance (CEX)
            prices[b, 1] = p_ref[b] + np.random.normal(0, 40) # Coinbase (CEX)
            prices[b, 2] = 40000 + np.random.normal(0, 100)   # DEX Spot (UniV3)
            prices[b, 3] = 60000 + np.random.normal(0, 100)   # DEX TWAP (UniV3)
            prices[b, 4] = p_ref[b] + np.random.normal(0, 40) # Independent Ref
        elif 45 <= b < 50:
            # Regime 2b: Stealth Micro-Deviation ($1 attack)
            p_ref[b] = 80808
            prices[b, 0] = 80001
            prices[b, 1] = 80000
            prices[b, 2] = 79999 # Correlated UniV3 Spot
            prices[b, 3] = 79996 # Correlated UniV3 TWAP
            prices[b, 4] = 80002 # Independent Ref
        elif 50 <= b < 75:
            # Regime 3: Genuine Market Crash (20% drop)
            crash_factor = 0.80 - (b - 50) * 0.005
            p_ref[b] = 80500 * max(crash_factor, 0.75)
            noise = np.random.normal(0, 60, 5)
            prices[b] = p_ref[b] + noise
        else:
            # Regime 4: Post-crash stabilized state
            p_ref[b] = 64000 + np.random.normal(0, 50)
            noise = np.random.normal(0, 40, 5)
            prices[b] = p_ref[b] + noise

    # Save to CSV for persistent reproducibility
    df = pd.DataFrame({
        "block": np.arange(blocks),
        "p_ref": p_ref.astype(int),
        "feed0_cex_binance": prices[:, 0].astype(int),
        "feed1_cex_coinbase": prices[:, 1].astype(int),
        "feed2_dex_spot_univ3": prices[:, 2].astype(int),
        "feed3_dex_twap_univ3": prices[:, 3].astype(int),
        "feed4_independent_ref": prices[:, 4].astype(int),
        "definitely_liquidatable": (p_ref <= (T - 808)).astype(int),
        "definitely_healthy": (p_ref >= (T + 808)).astype(int)
    })
    
    os.makedirs(os.path.expanduser("~/cegis-defi-guard/data"), exist_ok=True)
    csv_path = os.path.expanduser("~/cegis-defi-guard/data/benchmark_trace_100blocks.csv")
    df.to_csv(csv_path, index=False)
    print(f"[+] Successfully exported persistent dataset to: {csv_path}")

    # Benchmark Execution Logic
    stats = {
        "OVer-style": {"unsafe": 0, "preserved": 0, "defer": 0},
        "SecPLF-style": {"unsafe": 0, "preserved": 0, "defer": 0},
        "Ormer-style": {"unsafe": 0, "preserved": 0, "defer": 0},
        "LiqTwin-CEGIS": {"unsafe": 0, "preserved": 0, "defer": 0}
    }

    secplf_last_price = prices[0, 2]
    ormer_buffer = list(prices[:ormer_window, 2])
    definitely_liquidatable = df["definitely_liquidatable"].values.astype(bool)
    definitely_healthy = df["definitely_healthy"].values.astype(bool)

    for b in range(blocks):
        current_p = prices[b]
        is_liquidatable = definitely_liquidatable[b]
        is_healthy = definitely_healthy[b]

        # 1. OVer-style
        dex_spot = current_p[2]
        over_accept = abs(dex_spot - 80500) * 10000 <= delta_bps * 80500
        over_liquidate = (dex_spot < T) and over_accept
        if over_liquidate and is_healthy:
            stats["OVer-style"]["unsafe"] += 1
        if is_liquidatable:
            if over_liquidate:
                stats["OVer-style"]["preserved"] += 1
            else:
                stats["OVer-style"]["defer"] += 1

        # 2. SecPLF-style
        pct_change = abs(dex_spot - secplf_last_price) / secplf_last_price
        if pct_change <= velocity_limit:
            secplf_price = dex_spot
            secplf_accept = True
            secplf_last_price = dex_spot
        else:
            secplf_price = secplf_last_price
            secplf_accept = False

        secplf_liquidate = (secplf_price < T) and secplf_accept
        if secplf_liquidate and is_healthy:
            stats["SecPLF-style"]["unsafe"] += 1
        if is_liquidatable:
            if secplf_liquidate:
                stats["SecPLF-style"]["preserved"] += 1
            else:
                stats["SecPLF-style"]["defer"] += 1

        # 3. Ormer-style
        ormer_buffer.append(dex_spot)
        if len(ormer_buffer) > ormer_window:
            ormer_buffer.pop(0)
        ormer_median = np.median(ormer_buffer)
        ormer_liquidate = ormer_median < T
        if ormer_liquidate and is_healthy:
            stats["Ormer-style"]["unsafe"] += 1
        if is_liquidatable:
            if ormer_liquidate:
                stats["Ormer-style"]["preserved"] += 1
            else:
                stats["Ormer-style"]["defer"] += 1

        # 4. LiqTwin-CEGIS
        med_p = np.median(current_p)
        mad = np.median(np.abs(current_p - med_p))
        dispersion_ok = (mad * 10000) <= (100 * med_p)
        liq_accept = (len(current_p) >= 5) and dispersion_ok
        liq_liquidate = liq_accept and (med_p < T)

        if liq_liquidate and is_healthy:
            stats["LiqTwin-CEGIS"]["unsafe"] += 1
        if is_liquidatable:
            if liq_liquidate:
                stats["LiqTwin-CEGIS"]["preserved"] += 1
            else:
                stats["LiqTwin-CEGIS"]["defer"] += 1

    total_valid = np.sum(definitely_liquidatable)
    print("------------------------------------------------------------------------------------------")
    for name, m in stats.items():
        unsafe_rate = (m['unsafe'] / blocks) * 100
        preserve_rate = (m['preserved'] / total_valid) * 100 if total_valid > 0 else 100.0
        print(f"{name:<16} | Unsafe: {m['unsafe']:<2} ({unsafe_rate:>4.1f}%) | Preserved: {m['preserved']:<2} / {total_valid} ({preserve_rate:>5.1f}%) | Defer: {m['defer']}")
    print("------------------------------------------------------------------------------------------")

if __name__ == "__main__":
    generate_and_save_benchmark_data()
