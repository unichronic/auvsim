/* Host harness: runs the real firmware routine on x86 and dumps raw bytes. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "waveform.h"
#include "sim0_tables.h"

int main(int argc, char **argv) {
    if (argc < 4) { fprintf(stderr, "usage: %s <mode> <window> <outfile>\n", argv[0]); return 2; }
    const char *mode = argv[1], *wname = argv[2];
    win_t w = !strcmp(wname,"hamming") ? WIN_HAMMING :
              !strcmp(wname,"hann")    ? WIN_HANN    :
              !strcmp(wname,"blackman")? WIN_BLACKMAN: WIN_RECT;
    uint8_t *buf = malloc(N_PULSE);
    if (!strcmp(mode, "lfm"))       wf_lfm (buf, N_PULSE, 100e3, 500e3, w);
    else if (!strcmp(mode,"geom"))  wf_geom(buf, N_PULSE, 100e3, 500e3, w);
    else if (!strcmp(mode,"bpsk"))  wf_bpsk(buf, N_PULSE, 200e3, w);
    else if (!strcmp(mode,"lfm_down")) wf_lfm(buf, N_PULSE, 500e3, 100e3, w); /* down-chirp */
    else { fprintf(stderr, "bad mode %s\n", mode); return 2; }
    FILE *f = fopen(argv[3], "wb");
    if (!f) { perror("fopen"); return 1; }
    fwrite(buf, 1, N_PULSE, f); fclose(f); free(buf);
    return 0;
}
