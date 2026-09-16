#include "waveform.h"
#include "sim0_tables.h"
#include <math.h>

#define FS 10000000.0
#define PHASE_SHIFT (PHASE_BITS - LUT_BITS)   /* 20 */

static const int8_t BARKER13[13] = {1,1,1,1,1,-1,-1,1,1,-1,1,-1,1};

static const uint16_t *win_table(win_t w) {
    switch (w) {
        case WIN_HAMMING:  return WIN_HAMMING_T;
        case WIN_HANN:     return WIN_HANN_T;
        case WIN_BLACKMAN: return WIN_BLACKMAN_T;
        default:           return WIN_RECT_T;
    }
}

/* Frequency tuning word, matching params.ftw() exactly. */
static uint32_t ftw(double f_hz) {
    return (uint32_t)(uint64_t)floor(f_hz / FS * 4294967296.0 + 0.5);
}

/* Floor division for signed values.  C's / truncates toward zero; Python's //
 * floors.  They agree only while the numerator is non-negative -- i.e. only for
 * an UP-chirp.  Getting this wrong is precisely the fixed-point defect SIM-1
 * exists to catch, so it is spelled out rather than left to luck. */
static int64_t floordiv(int64_t a, int64_t b) {
    int64_t q = a / b;
    if ((a % b != 0) && ((a < 0) != (b < 0))) q--;
    return q;
}

/* Shared back end: phase -> LUT -> Q15 window -> 8-bit DAC code. */
static inline uint8_t emit(uint32_t phase, uint16_t wq) {
    uint32_t addr = (phase >> PHASE_SHIFT) & (LUT_SIZE - 1);
    int32_t centred = (int32_t)SINE_LUT[addr] - 128;
    int32_t scaled  = (int32_t)(((int64_t)centred * (int64_t)wq) >> 15);
    int32_t v = scaled + 128;
    if (v < 0)   v = 0;
    if (v > 255) v = 255;
    return (uint8_t)v;
}

void wf_lfm(uint8_t *out, uint32_t n, double f0, double f1, win_t w) {
    const uint16_t *win = win_table(w);
    int64_t tw0 = ftw(f0), tw1 = ftw(f1);
    uint32_t acc = 0;
    for (uint32_t k = 0; k < n; k++) {
        out[k] = emit(acc, win[k]);
        acc += (uint32_t)(tw0 + floordiv((tw1 - tw0) * (int64_t)k, (int64_t)n));
    }
}

void wf_geom(uint8_t *out, uint32_t n, double f0, double f1, win_t w) {
    const uint16_t *win = win_table(w);
    double r = pow(f1 / f0, 1.0 / (double)n);
    uint64_t R = (uint64_t)floor(r * 4294967296.0 + 0.5);
    uint64_t cur = ftw(f0);
    uint32_t acc = 0;
    for (uint32_t k = 0; k < n; k++) {
        out[k] = emit(acc, win[k]);
        acc += (uint32_t)cur;
        cur = (cur * R) >> 32;
    }
}

void wf_bpsk(uint8_t *out, uint32_t n, double fc, win_t w) {
    const uint16_t *win = win_table(w);
    uint64_t tw = ftw(fc);
    for (uint32_t k = 0; k < n; k++) {
        uint32_t chip  = (uint32_t)(((uint64_t)k * 13ULL) / (uint64_t)n);
        uint32_t inv   = (BARKER13[chip] < 0) ? 0x80000000u : 0u;
        uint32_t phase = (uint32_t)(((uint64_t)k * tw) & 0xFFFFFFFFULL);
        out[k] = emit(phase + inv, win[k]);
    }
}
