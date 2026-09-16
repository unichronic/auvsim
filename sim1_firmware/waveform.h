/* Sample-generation routine destined for the RP2040.
 * Compiled here for x86 so its output can be diffed against SIM-0. */
#ifndef WAVEFORM_H
#define WAVEFORM_H
#include <stdint.h>
typedef enum { WIN_RECT=0, WIN_HAMMING, WIN_HANN, WIN_BLACKMAN } win_t;
void wf_lfm (uint8_t *out, uint32_t n, double f0, double f1, win_t w);
void wf_geom(uint8_t *out, uint32_t n, double f0, double f1, win_t w);
void wf_bpsk(uint8_t *out, uint32_t n, double fc, win_t w);
#endif
