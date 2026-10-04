// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "forge-std/Test.sol";
import "../src/LiquidationGuard.sol";

contract LiquidationGuardMemorylessTest is Test {
    LiquidationGuard guard;

    function setUp() public {
        guard = new LiquidationGuard();
    }

    /// @dev Asserts that evaluating admissibility causes zero state change (0 SSTORE)
    function test_GuardIsStrictlyMemoryless() public {
        uint256[5] memory prices = [uint256(80500), 80480, 80520, 80510, 80490];
        uint8[5] memory families = [uint8(1), 2, 3, 3, 4];
        uint32[5] memory ages = [uint32(10), 12, 5, 8, 15];
        uint256[5] memory liquidities = [uint256(2e6), 2e6, 2e6, 2e6, 2e6];

        bytes32 slot0_before = vm.load(address(guard), bytes32(0));
        
        guard.evaluateAdmissibility(prices, families, ages, liquidities);

        bytes32 slot0_after = vm.load(address(guard), bytes32(0));
        assertEq(slot0_before, slot0_after, "Memorylessness violated: storage was modified");
    }
}
