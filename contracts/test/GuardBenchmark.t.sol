// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/LiquidationGuard.sol";

contract GuardBenchmarkTest is Test {
    LiquidationGuard public guard;

    function setUp() public {
        guard = new LiquidationGuard();
    }

    function test_AdmissibleExecutionGas() public {
        LiquidationGuard.FeedObservation[] memory obs = new LiquidationGuard.FeedObservation[](5);
        obs[0] = LiquidationGuard.FeedObservation(80500, block.timestamp, 1);
        obs[1] = LiquidationGuard.FeedObservation(80400, block.timestamp, 2);
        obs[2] = LiquidationGuard.FeedObservation(80600, block.timestamp, 3);
        obs[3] = LiquidationGuard.FeedObservation(80450, block.timestamp, 3);
        obs[4] = LiquidationGuard.FeedObservation(80550, block.timestamp, 4);

        vm.pauseGasMetering();
        guard.evaluateAdmissibility(obs);
        vm.resumeGasMetering();

        (LiquidationGuard.Action action, uint256 price) = guard.evaluateAdmissibility(obs);
        assertEq(uint256(action), uint256(LiquidationGuard.Action.ACCEPT));
        assertGt(price, 0);
    }

    function test_CorrelatedAttackSuppression() public view {
        LiquidationGuard.FeedObservation[] memory obs = new LiquidationGuard.FeedObservation[](5);
        obs[0] = LiquidationGuard.FeedObservation(80500, block.timestamp, 1);
        obs[1] = LiquidationGuard.FeedObservation(80400, block.timestamp, 2);
        obs[2] = LiquidationGuard.FeedObservation(40000, block.timestamp, 3);
        obs[3] = LiquidationGuard.FeedObservation(40000, block.timestamp, 3);
        obs[4] = LiquidationGuard.FeedObservation(80550, block.timestamp, 4);

        (LiquidationGuard.Action action, ) = guard.evaluateAdmissibility(obs);
        assertEq(uint256(action), uint256(LiquidationGuard.Action.DEFER));
    }

    /// @dev Property-Based Invariant Fuzzing: Proves that arbitrary input values
    /// never cause an EVM arithmetic panic or unhandled revert.
    function testFuzz_NeverRevertsOnArbitraryPrices(
        uint32 p0, uint32 p1, uint32 p2, uint32 p3, uint32 p4,
        uint8 f0, uint8 f1, uint8 f2, uint8 f3, uint8 f4
    ) public view {
        LiquidationGuard.FeedObservation[] memory obs = new LiquidationGuard.FeedObservation[](5);
        obs[0] = LiquidationGuard.FeedObservation(p0, block.timestamp, f0);
        obs[1] = LiquidationGuard.FeedObservation(p1, block.timestamp, f1);
        obs[2] = LiquidationGuard.FeedObservation(p2, block.timestamp, f2);
        obs[3] = LiquidationGuard.FeedObservation(p3, block.timestamp, f3);
        obs[4] = LiquidationGuard.FeedObservation(p4, block.timestamp, f4);

        // Function must execute deterministically without reverting
        (LiquidationGuard.Action action, uint256 price) = guard.evaluateAdmissibility(obs);
        assertTrue(action == LiquidationGuard.Action.ACCEPT || action == LiquidationGuard.Action.DEFER);
        if (action == LiquidationGuard.Action.ACCEPT) {
            assertGt(price, 0);
        }
    }
}
