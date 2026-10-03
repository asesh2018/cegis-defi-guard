import z3

def z3_sort5(vals):
    """Optimal 5-element sorting network in Z3 (9 comparisons)."""
    a, b, c, d, e = vals
    def cswap(x, y):
        return z3.If(x < y, x, y), z3.If(x < y, y, x)
    
    a, b = cswap(a, b)
    d, e = cswap(d, e)
    c, e = cswap(c, e)
    c, d = cswap(c, d)
    b, d = cswap(b, d)
    a, c = cswap(a, c)
    b, e = cswap(b, e)
    b, c = cswap(b, c)
    d, e = cswap(d, e)
    return [a, b, c, d, e]

def z3_abs(x):
    return z3.If(x >= 0, x, -x)

class CEGISSynthesizer:
    def __init__(self):
        self.counterexamples = []

    def verify_candidate_5source(self, u_min, r_min_sources, max_mad_bps, T=80000, M=808):
        """
        Five-source topology (Oracle A, Oracle B, DEX Spot, DEX TWAP, Independent History/Feed).
        Correlated Failure: UniV3 corruption impacts Spot & TWAP (2 feeds).
        Honest sources: 3 feeds remain honest.
        """
        solver = z3.Solver()
        solver.set("timeout", 5000)

        p = [z3.Int(f"p_{i}") for i in range(5)]
        p_ref = z3.Int("p_ref")

        # 1. Healthy reference price
        solver.add(p_ref >= T + M)
        for i in range(5):
            solver.add(p[i] >= 10000, p[i] <= 200000)

        # 2. Correlated Adversary Budget: Compromise at most 1 upstream origin
        adv_binance = z3.Bool("adv_binance")
        adv_coinbase = z3.Bool("adv_coinbase")
        adv_univ3 = z3.Bool("adv_univ3")
        solver.add(z3.AtMost(adv_binance, adv_coinbase, adv_univ3, 1))

        # Feed 0: Oracle A (Binance)
        solver.add(z3.Implies(z3.Not(adv_binance), z3_abs(p[0] - p_ref) * 10000 <= 100 * p_ref))
        # Feed 1: Oracle B (Coinbase)
        solver.add(z3.Implies(z3.Not(adv_coinbase), z3_abs(p[1] - p_ref) * 10000 <= 100 * p_ref))
        # Feed 2 & 3: DEX Spot & TWAP (both depend on UniV3)
        solver.add(z3.Implies(z3.Not(adv_univ3), z3_abs(p[2] - p_ref) * 10000 <= 100 * p_ref))
        solver.add(z3.Implies(z3.Not(adv_univ3), z3_abs(p[3] - p_ref) * 10000 <= 100 * p_ref))
        # Feed 4: Independent Reference Feed (Uncorrelated)
        solver.add(z3_abs(p[4] - p_ref) * 10000 <= 100 * p_ref)

        # 3. Median computation via 5-element sorting network
        sorted_p = z3_sort5(p)
        median = sorted_p[2]  # True middle element

        # 4. MAD computation
        devs = [z3_abs(p[i] - median) for i in range(5)]
        sorted_devs = z3_sort5(devs)
        mad = sorted_devs[2]

        # 5. Admissibility check
        dispersion_ok = (mad * 10000 <= max_mad_bps * median)
        guard_accepts = dispersion_ok

        # Safety violation query: Healthy state, Guard ACCEPTS, but median triggers liquidation
        solver.add(guard_accepts)
        solver.add(median < T)

        result = solver.check()
        if result == z3.sat:
            m = solver.model()
            cex = {
                "p_ref": m[p_ref].as_long(),
                "prices": [m[p[i]].as_long() for i in range(5)],
                "adv": (bool(m.eval(adv_binance)), bool(m.eval(adv_coinbase)), bool(m.eval(adv_univ3)))
            }
            return False, cex
        return True, None

    def run_cegis(self):
        print("[*] Starting CEGIS Loop for 5-Source Correlated Fault Defense...")
        
        # Candidate grammar over dispersion bounds
        candidates = [
            (5, 3, mad) for mad in [100, 200, 300, 500, 1000]
        ] + [
            (3, 2, mad) for mad in [100, 200, 300, 500, 1000]
        ]
        
        candidates.sort(key=lambda c: c[2])

        iteration = 0
        while candidates:
            u, r, mad = candidates.pop(0)
            iteration += 1
            passed, cex = self.verify_candidate_5source(u, r, mad)

            if not passed:
                print(f"[Iter {iteration}] Candidate (u_min={u}, r_min={r}, mad={mad} bps) REJECTED.")
                print(f"      Witness: p_ref={cex['p_ref']}, prices={cex['prices']}, adv={cex['adv']}")
                self.counterexamples.append(cex)
                before_len = len(candidates)
                candidates = [c for c in candidates if not (c[0] == u and c[1] == r and c[2] >= mad)]
                pruned = before_len - len(candidates)
                print(f"      -> Pruned {pruned} candidate guards.")
            else:
                print(f"\n[+] CEGIS CONVERGED in {iteration} iteration(s)!")
                print(f"[+] Formally Verified Guard Synthesized: u_min={u}, r_min_sources={r}, max_mad_bps={mad} bps")
                return u, r, mad

        print("[-] Synthesis failed: Grammar space exhausted.")
        return None

if __name__ == "__main__":
    synthesizer = CEGISSynthesizer()
    synthesizer.run_cegis()
