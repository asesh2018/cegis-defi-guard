// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract LiquidationGuard {
    uint256 public constant U_MIN = 5;
    uint256 public constant R_MIN_SOURCES = 3;
    uint256 public constant MAX_MAD_BPS = 100;
    uint256 public constant LIQUIDATION_THRESHOLD = 80000;

    struct FeedObservation {
        uint256 price;
        uint256 timestamp;
        uint8 sourceFamily; // 1: Binance, 2: Coinbase, 3: UniV3, 4: History/Chainlink
    }

    enum Action { ACCEPT, DEFER }

    function evaluateAdmissibility(FeedObservation[] calldata obs) external pure returns (Action, uint256) {
        if (obs.length < U_MIN) {
            return (Action.DEFER, 0);
        }

        // 1. Source family diversity check (r_min)
        uint256 familyMask = 0;
        uint256 distinctFamilies = 0;
        for (uint256 i = 0; i < obs.length; i++) {
            uint256 bit = 1 << obs[i].sourceFamily;
            if ((familyMask & bit) == 0) {
                familyMask |= bit;
                distinctFamilies++;
            }
        }
        if (distinctFamilies < R_MIN_SOURCES) {
            return (Action.DEFER, 0);
        }

        // 2. 5-element sorting network (9 compare-and-swaps)
        uint256[5] memory p;
        for (uint256 i = 0; i < 5; i++) {
            p[i] = obs[i].price;
        }

        if (p[0] > p[1]) (p[0], p[1]) = (p[1], p[0]);
        if (p[3] > p[4]) (p[3], p[4]) = (p[4], p[3]);
        if (p[2] > p[4]) (p[2], p[4]) = (p[4], p[2]);
        if (p[2] > p[3]) (p[2], p[3]) = (p[3], p[2]);
        if (p[1] > p[3]) (p[1], p[3]) = (p[3], p[1]);
        if (p[0] > p[2]) (p[0], p[2]) = (p[2], p[0]);
        if (p[1] > p[4]) (p[1], p[4]) = (p[4], p[1]);
        if (p[1] > p[2]) (p[1], p[2]) = (p[2], p[1]);
        if (p[3] > p[4]) (p[3], p[4]) = (p[4], p[3]);

        uint256 medianPrice = p[2];

        // 3. Compute MAD (Median Absolute Deviation)
        uint256[5] memory dev;
        for (uint256 i = 0; i < 5; i++) {
            dev[i] = p[i] >= medianPrice ? p[i] - medianPrice : medianPrice - p[i];
        }

        if (dev[0] > dev[1]) (dev[0], dev[1]) = (dev[1], dev[0]);
        if (dev[3] > dev[4]) (dev[3], dev[4]) = (dev[4], dev[3]);
        if (dev[2] > dev[4]) (dev[2], dev[4]) = (dev[4], dev[2]);
        if (dev[2] > dev[3]) (dev[2], dev[3]) = (dev[3], dev[2]);
        if (dev[1] > dev[3]) (dev[1], dev[3]) = (dev[3], dev[1]);
        if (dev[0] > dev[2]) (dev[0], dev[2]) = (dev[2], dev[0]);
        if (dev[1] > dev[4]) (dev[1], dev[4]) = (dev[4], dev[1]);
        if (dev[1] > dev[2]) (dev[1], dev[2]) = (dev[2], dev[1]);
        if (dev[3] > dev[4]) (dev[3], dev[4]) = (dev[4], dev[3]);

        uint256 mad = dev[2];

        // 4. Dispersion check: 10000 * MAD <= MAX_MAD_BPS * median
        if (mad * 10000 > MAX_MAD_BPS * medianPrice) {
            return (Action.DEFER, 0);
        }

        return (Action.ACCEPT, medianPrice);
    }
}
