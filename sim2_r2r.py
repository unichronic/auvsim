"""
SIM-2a -- R-2R ladder Monte Carlo, solved exactly by nodal analysis.

The bench doc runs this in SPICE.  The ladder is a linear resistor network, so
the DC transfer curve is an exact linear solve -- no simulator needed, and it
runs thousands of trials in the time SPICE takes to do a handful.  The SPICE
netlist in sim2_spice/ is retained as an independent cross-check for when
ngspice is available.

Topology (voltage-mode, N bits), nodes 0 (LSB) .. N-1 (MSB, = output):
    node 0        --2R--> GND                     (termination)
    node i        --2R--> bit driver i            (VREF or 0)
    node i        --R -->  node i+1               (i = 0..N-2)
Output is taken at node N-1 into a high-impedance buffer.
"""
import numpy as np
import params as P

N = P.DAC_BITS

def transfer_curve(r_series, r_shunt, r_term, vref=P.VREF):
    """Return V_out for all 2^N codes.  G depends only on the resistors, so it
    is built and factorised once and solved against all codes at one go."""
    n = N
    G = np.zeros((n, n))
    for i in range(n):
        G[i, i] += 1.0 / r_shunt[i]
    G[0, 0] += 1.0 / r_term
    for i in range(n - 1):
        g = 1.0 / r_series[i]
        G[i, i] += g; G[i + 1, i + 1] += g
        G[i, i + 1] -= g; G[i + 1, i] -= g
    codes = np.arange(1 << n)
    bits = ((codes[None, :] >> np.arange(n)[:, None]) & 1).astype(float)  # (n, 2^n)
    I = bits * (vref / r_shunt[:, None])
    V = np.linalg.solve(G, I)
    return V[n - 1, :]

def inl_dnl(vout):
    """Endpoint-fit INL and DNL in LSB."""
    lsb = (vout[-1] - vout[0]) / (len(vout) - 1)
    ideal = vout[0] + lsb * np.arange(len(vout))
    inl = (vout - ideal) / lsb
    dnl = np.diff(vout) / lsb - 1.0
    return inl, dnl, lsb

def trial(tol, rng, r_nom=10e3):
    """One Monte Carlo draw at the given fractional tolerance (uniform)."""
    draw = lambda size, nom: nom * (1.0 + rng.uniform(-tol, tol, size))
    return transfer_curve(draw(N - 1, r_nom), draw(N, 2 * r_nom), draw((), 2 * r_nom))

def monte_carlo(tol, trials=2000, seed=0):
    rng = np.random.default_rng(seed)
    worst_inl = np.empty(trials); worst_dnl = np.empty(trials); nonmono = 0
    for t in range(trials):
        inl, dnl, _ = inl_dnl(trial(tol, rng))
        worst_inl[t] = np.abs(inl).max()
        worst_dnl[t] = np.abs(dnl).max()
        if (dnl <= -1.0).any():
            nonmono += 1
    return {"tolerance_pct": tol * 100,
            "inl_lsb_mean": float(worst_inl.mean()),
            "inl_lsb_p99":  float(np.percentile(worst_inl, 99)),
            "inl_lsb_max":  float(worst_inl.max()),
            "dnl_lsb_mean": float(worst_dnl.mean()),
            "dnl_lsb_p99":  float(np.percentile(worst_dnl, 99)),
            "dnl_lsb_max":  float(worst_dnl.max()),
            "nonmonotonic_trials": nonmono,
            "nonmonotonic_pct": 100.0 * nonmono / trials,
            "trials": trials}

def spur_impact(tol, f_tone=350e3, n=8192, seed=0, trials=64):
    """Push a single tone through real (mismatched) ladders and watch
    non-monotonicity become spurs -- the link the bench doc asks for.

    Must be a TONE, not a chirp: an LFM sweep spreads its energy over the whole
    band, so "largest bin that is not the carrier" is just another part of the
    chirp and SFDR comes out ~0 dB regardless of the resistors.  The ideal
    ladder is measured alongside so the number quoted is the *degradation*
    caused by tolerance, not the DAC's intrinsic 8-bit floor.
    """
    import sim0_reference as s0
    from scipy.signal.windows import blackmanharris
    rng = np.random.default_rng(seed)
    w_rect = s0.make_window("rect", n)
    samples, _ = s0.gen_bpsk(f_tone, n, w_rect, code=np.array([1], dtype=np.int8))
    w = blackmanharris(n)

    def sfdr_of(v):
        v = (v - v[0]) / (v[-1] - v[0])          # normalise to 0..1 full scale
        analog = v[samples.astype(int)]
        sig = (analog - analog.mean()) * w
        X = np.abs(np.fft.rfft(sig)); X[:8] = 0
        pk = int(X.argmax()); car = X[pk]
        X2 = X.copy(); X2[max(0, pk - 8):pk + 9] = 0
        return 20 * np.log10(X2.max() / car)

    ideal = sfdr_of(transfer_curve(np.full(N - 1, 10e3), np.full(N, 20e3), 20e3))
    got = [sfdr_of(trial(tol, rng)) for _ in range(trials)]
    return {"tone_kHz": f_tone / 1e3,
            "sfdr_ideal_dbc": float(ideal),
            "sfdr_mean_dbc": float(np.mean(got)),
            "sfdr_worst_dbc": float(np.max(got)),
            "degradation_worst_db": float(np.max(got) - ideal)}
