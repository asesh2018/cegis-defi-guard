import numpy as np
import matplotlib.pyplot as plt
import os

# ==============================================================================
# Matplotlib Publication-Grade Styling (Springer sn-jnl Compatible)
# ==============================================================================
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 10.5,
    "axes.titlesize": 11,
    "xtick.labelsize": 9.5,
    "ytick.labelsize": 9.5,
    "legend.fontsize": 8.5,
    "figure.titlesize": 12,
    "figure.dpi": 300
})

np.random.seed(42)
blocks = 100
T = 80000          # Nominal liquidation threshold ($80,000)
M_star = 808       # Minimum decision margin

p_ref = np.zeros(blocks)
prices = np.zeros((blocks, 5))

# ==============================================================================
# Generate Realistic Multi-Source Market Regimes
# ==============================================================================
for b in range(blocks):
    if b < 30:
        # Regime I: Normal Trading (Healthy)
        p_ref[b] = 80500 + np.random.normal(0, 40)
        prices[b] = p_ref[b] + np.random.normal(0, 25, 5)

    elif 30 <= b < 45:
        # Regime II: Flash-Loan Attack on UniV3 Pool (Blocks 30–44)
        p_ref[b] = 80500 + np.random.normal(0, 30)
        prices[b, 2] = 45000 + np.random.normal(0, 80)   # DEX Spot plunged
        prices[b, 3] = 62000 + np.random.normal(0, 80)   # DEX TWAP dragged
        prices[b, 1] = 76500 + np.random.normal(0, 40)   # Coinbase (arbitrage drag)
        prices[b, 0] = 80500 + np.random.normal(0, 30)   # Binance
        prices[b, 4] = 80800 + np.random.normal(0, 30)   # Ref Feed

    elif 45 <= b < 50:
        # Regime III: Stealth Micro-Deviation Exploit (Blocks 45–49)
        p_ref[b] = 80808
        prices[b, 0] = 80001
        prices[b, 1] = 80000
        prices[b, 2] = 79999
        prices[b, 3] = 79996
        prices[b, 4] = 80002

    elif 50 <= b < 75:
        # Regime IV: Genuine Market Crash (Blocks 50–74)
        crash_factor = 0.80 - (b - 50) * 0.004
        p_ref[b] = 80500 * max(crash_factor, 0.76)
        prices[b] = p_ref[b] + np.random.normal(0, 35, 5)

    else:
        # Regime V: Stabilized Post-Crash (Blocks 75–99)
        p_ref[b] = 64000 + np.random.normal(0, 35)
        prices[b] = p_ref[b] + np.random.normal(0, 25, 5)

# ==============================================================================
# Calculate Relative Dispersion (bps) per Block: 10^4 * MAD / Median
# ==============================================================================
mad_rel_bps = np.zeros(blocks)
for b in range(blocks):
    active_p = prices[b]
    med = np.median(active_p)
    mad = np.median(np.abs(active_p - med))
    mad_rel_bps[b] = (mad * 10000.0) / med

# Setup Figure with Extra Right Margin for Outside Legends
fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(11.5, 5.8), sharex=True, 
    gridspec_kw={'height_ratios': [2.2, 1.2]}
)

# ----------------- PANEL 1: PRICE TRAJECTORIES -----------------
ax1.axvspan(0, 29.5, color='#F8FAFC', alpha=0.9, zorder=0)
ax1.axvspan(29.5, 44.5, color='#FEE2E2', alpha=0.6, zorder=0)
ax1.axvspan(44.5, 49.5, color='#FEF3C7', alpha=0.7, zorder=0)
ax1.axvspan(49.5, 74.5, color='#ECFDF5', alpha=0.65, zorder=0)
ax1.axvspan(74.5, 99.5, color='#F8FAFC', alpha=0.9, zorder=0)

# Regime Banners
ax1.text(14.5, 88500, "Regime I:\nNormal Trading", ha='center', va='center', fontsize=8.5, color='#475569')
ax1.text(37.0, 88500, "Regime II:\nFlash Loan", ha='center', va='center', fontsize=8.5, fontweight='bold', color='#DC2626')
ax1.text(47.0, 88500, "Regime III:\nStealth", ha='center', va='center', fontsize=7.5, fontweight='bold', color='#D97706')
ax1.text(62.0, 88500, "Regime IV:\n20% Market Crash", ha='center', va='center', fontsize=8.5, fontweight='bold', color='#059669')
ax1.text(87.0, 88500, "Regime V:\nStabilized", ha='center', va='center', fontsize=8.5, color='#475569')

# Price Curves
ax1.plot(p_ref, color='black', linestyle='--', linewidth=1.4, label=r'Ground Truth ($p^{\mathrm{ref}}$)', zorder=4)
ax1.plot(prices[:, 0], color='#2563EB', linewidth=1.1, alpha=0.8, label='Oracle A (CEX Binance)')
ax1.plot(prices[:, 1], color='#06B6D4', linewidth=1.1, alpha=0.8, label='Oracle B (CEX Coinbase)')
ax1.plot(prices[:, 2], color='#DC2626', linewidth=1.5, label='DEX Spot (UniV3, $g=3$)', zorder=5)
ax1.plot(prices[:, 3], color='#F97316', linewidth=1.3, linestyle='-.', label='DEX TWAP (UniV3, $g=3$)', zorder=5)
ax1.plot(prices[:, 4], color='#64748B', linewidth=1.0, alpha=0.75, label='Ref Feed ($g=4$)')
ax1.axhline(T, color='#991B1B', linestyle=':', linewidth=1.4, label=r'Threshold ($T = \$80\mathrm{k}$)')

ax1.set_ylabel("Reported Price (USD)")
ax1.set_ylim(38000, 93000)

# LEGEND OUTSIDE PANEL 1 (Upper Left of the Outside Margin)
ax1.legend(
    bbox_to_anchor=(1.01, 1.0),
    loc='upper left',
    ncol=1,
    frameon=True,
    facecolor='white',
    framealpha=0.95,
    edgecolor='#CBD5E1',
    borderaxespad=0.
)
ax1.grid(True, linestyle=':', alpha=0.5, color='#94A3B8')
ax1.set_title("(a) Multi-Source Price Feed Dynamics and Adversarial Attack Regimes", loc='left', fontweight='bold', pad=8)

# ----------------- PANEL 2: DISPERSION DYNAMICS -----------------
ax2.axvspan(0, 29.5, color='#F8FAFC', alpha=0.9, zorder=0)
ax2.axvspan(29.5, 44.5, color='#FEE2E2', alpha=0.6, zorder=0)
ax2.axvspan(44.5, 49.5, color='#FEF3C7', alpha=0.7, zorder=0)
ax2.axvspan(49.5, 74.5, color='#ECFDF5', alpha=0.65, zorder=0)
ax2.axvspan(74.5, 99.5, color='#F8FAFC', alpha=0.9, zorder=0)

ax2.plot(mad_rel_bps, color='#4338CA', linewidth=1.7, label=r'Dispersion ($10^4 \cdot \mathrm{MAD} / \tilde{p}$)', zorder=3)
ax2.axhline(100, color='#DC2626', linestyle='--', linewidth=1.4, label=r'Limit ($M_{\mathrm{bps}} = 100$)', zorder=2)

ax2.fill_between(
    range(blocks), 100, mad_rel_bps, where=(mad_rel_bps > 100), 
    interpolate=True, color='#DC2626', alpha=0.28, 
    label='DEFER Zone (Suppressed)', zorder=2
)

ax2.set_xlabel("Block Index $t$")
ax2.set_ylabel("Dispersion (bps)")
ax2.set_ylim(-15, 650)
ax2.set_yticks([0, 100, 200, 300, 400, 500, 600])

# LEGEND OUTSIDE PANEL 2 (Upper Left of the Outside Margin)
ax2.legend(
    bbox_to_anchor=(1.01, 1.0),
    loc='upper left',
    ncol=1,
    frameon=True,
    facecolor='white',
    framealpha=0.95,
    edgecolor='#CBD5E1',
    borderaxespad=0.
)
ax2.grid(True, linestyle=':', alpha=0.5, color='#94A3B8')
ax2.set_title("(b) Dispersion Gating: Attack Suppression vs. Crash Preservation", loc='left', fontweight='bold', pad=8)

# Adjust Subplots so Both Axes Align Exactly
plt.subplots_adjust(left=0.08, right=0.80, top=0.93, bottom=0.10, hspace=0.18)

# ==============================================================================
# Save Vectors and High-Resolution Images (Stripping AI Metadata)
# ==============================================================================
output_dir = os.path.expanduser("~/cegis-defi-guard/figures")
os.makedirs(output_dir, exist_ok=True)

pdf_path = os.path.join(output_dir, "fig_oracle_benchmark.pdf")
png_path = os.path.join(output_dir, "fig_oracle_benchmark.png")

plt.savefig(pdf_path, format='pdf', bbox_inches='tight')
plt.savefig(png_path, format='png', dpi=600, bbox_inches='tight', metadata={})

print("[+] Successfully generated camera-ready plots with external legends:")
print(f"    - Vector PDF: {pdf_path}")
print(f"    - High-Res PNG: {png_path}")
