CFLAGS = -O2 -Wall -Wextra -std=c11
all: wfgen
wfgen: host_main.c waveform.c waveform.h sim0_tables.h
	$(CC) $(CFLAGS) -o wfgen host_main.c waveform.c -lm
clean:
	rm -f wfgen *.bin
.PHONY: all clean
