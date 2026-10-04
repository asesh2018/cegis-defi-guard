// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "forge-std/Test.sol";
import "../src/LiquidationGuard.sol";

contract TightnessWitnessTest is Test {
    LiquidationGuard guard;

    function setUp() public {
        guard = new LiquidationGuard();
    }

    /// @dev SMT Counterexample Replay: K=1 stealth micro-deviation on N=4
    function test_ReplayWitness_MicroDeviation_EvenTopology_Fails() public {
        uint256[5] memory prices = [uint256(79996), 79999, 80000, 80001, 0];
        uint8[5] memory families = [uint8(3), 3, 1, 2, 0];
        uint32[5] memory ages = [uint32(10), 10, 10, 10, 999]; // 5th feed stale
        uint256[5] memory liquidities = [uint256(1e6), 1e6, 1e6, 1e6, 0];

        (LiquidationGuard.Verdict verdict, ) = guard.evaluateAdmissibility(prices, families, ages, liquidities);
        assertTrue(verdict == LiquidationGuard.Verdict.DEFER, "Safety violated: stealth micro-deviation accepted");
    }
}
