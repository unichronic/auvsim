# Design research (patterns, not a competitor comparison)

Before finalising this architecture, we surveyed a broad range of publicly documented
approaches to real-time adaptive sonar/waveform-generation hardware on constrained embedded
platforms. We're not naming specific projects or teams here — this is a summary of the
patterns that informed our own design decisions, not a comparison.

**Sample rate is the most common bottleneck.** Most approaches we looked at use a
microcontroller's internal DAC, or a low-cost SPI DAC, running well under 2 megasamples per
second. At those rates, a 500 kHz signal gets only 2–4 samples per cycle — mathematically
insufficient to represent cleanly, regardless of what frequency band is claimed in
documentation. This is why we chose to drive our DAC bus from a PIO/DMA-class hardware
peripheral at a real ~10 MS/s, rather than relying on a microcontroller's built-in converter.

**Amplitude control is usually digital.** Scaling sample values in software to change output
amplitude is the common approach, but it costs DAC resolution exactly when the signal is
smallest — at 25% amplitude, an 8-bit DAC becomes effectively 6-bit. We instead control
amplitude in the analog domain, ahead of the output stage, so the DAC always runs at full
resolution regardless of the commanded amplitude.

**Environmental sensing is frequently simulated end-to-end.** Potentiometers standing in for
real sensors are common and spec-permitted for this class of problem, but we chose to use real
sensors (temperature, turbidity, salinity, power) wherever physically practical on a benchtop,
and reserve simulation for the one variable (depth/hydrostatic pressure) that genuinely cannot
be reproduced on a table.

**Adaptation logic is often loosely physics-motivated.** A frequency/sound-speed formula
frequently appears, but sound speed itself has only a small effect on the optimal transmit
frequency; absorption and sediment scattering are the mechanisms that actually govern the
range-vs-resolution tradeoff, and they aren't always modelled. We grounded our own adaptation
mapping in cited underwater-acoustics literature (viscous-attenuation models for suspended
sediment, standard seawater absorption formulas) rather than an arbitrary or purely
sound-speed-driven rule table.

**Windowing is usually applied but rarely measured.** Firmware-side windowing (Hann, Hamming,
Blackman) to reduce pulse-edge transients and sidelobes is common, but a measured
before/after comparison — a real capture showing rectangular vs. windowed sidelobe
suppression — is uncommon. We treat that comparison as a first-class validation artifact, not
an afterthought.
