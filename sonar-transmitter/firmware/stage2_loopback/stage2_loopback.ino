// Stage 2 (self-checking) — prove the DAC bus with one jumper wire.
//
// Needs no LEDs and no multimeter. One end of a probe wire goes to GPIO26
// (through a 1 kΩ resistor, for protection); you touch the other end to each
// of GPIO16..GPIO23 in turn. The board drives the bus one pin at a time,
// reads GPIO26, and reports which bus pin the probe is on.
//
// It catches three faults a binary count can hide:
//   dead pin       -> "no signal" while the wire is definitely on the pin
//   swapped pins   -> it reports the pin's real GPIO number, not the one you expected
//   solder bridge  -> two bus pins show up at the same time
//
// Board:  Vicharak Shrike-Lite (arduino-pico)
// Gate:   the serial monitor prints "STAGE 2 PASS" once all 8 pins verify.

const int DAC_BASE = 16;   // GPIO16 = bit 0 ... GPIO23 = bit 7
const int DAC_BITS = 8;
const int PROBE    = 26;   // spare, ADC-capable; unused by the design

void writeBus(uint8_t v) {
  for (int b = 0; b < DAC_BITS; b++) digitalWrite(DAC_BASE + b, (v >> b) & 1);
}

// Returns a bitmask of which bus pins the probe "sees", or 0xFF00 flags:
//   0x100 = probe is high even with the whole bus low (touching 3.3 V, or a stuck-high pin)
uint16_t scan() {
  writeBus(0x00);
  delayMicroseconds(20);
  if (digitalRead(PROBE)) return 0x100;

  uint16_t seen = 0;
  for (int b = 0; b < DAC_BITS; b++) {
    writeBus(1 << b);
    delayMicroseconds(20);
    if (digitalRead(PROBE)) seen |= (1 << b);
  }
  writeBus(0x00);
  return seen;
}

uint8_t verified = 0;

void report(uint16_t s) {
  if (s == 0x100) {
    Serial.println("probe reads HIGH with the bus off -> touching 3.3 V, or a pin stuck high");
    return;
  }
  if (s == 0) {
    Serial.println("probe: no signal   (wire not on a bus pin -- or, if it IS, that pin is dead)");
    return;
  }
  int n = __builtin_popcount(s);
  if (n > 1) {
    Serial.print("!! BRIDGE: probe sees more than one bus pin at once:");
    for (int b = 0; b < DAC_BITS; b++) if (s & (1 << b)) { Serial.print(" GPIO"); Serial.print(DAC_BASE + b); }
    Serial.println("  -> look for a solder bridge between those header pins");
    return;
  }
  int b = __builtin_ctz(s);
  verified |= (1 << b);
  Serial.print("probe on GPIO"); Serial.print(DAC_BASE + b);
  Serial.print("  OK      verified so far:");
  for (int i = 0; i < DAC_BITS; i++) if (verified & (1 << i)) { Serial.print(" "); Serial.print(DAC_BASE + i); }
  Serial.print("  ("); Serial.print(__builtin_popcount(verified)); Serial.println("/8)");
  if (verified == 0xFF) Serial.println("\n==== STAGE 2 PASS: all eight DAC bus pins toggle, correct identity, no bridges ====\n");
}

void setup() {
  for (int b = 0; b < DAC_BITS; b++) { pinMode(DAC_BASE + b, OUTPUT); digitalWrite(DAC_BASE + b, LOW); }
  pinMode(PROBE, INPUT_PULLDOWN);  // an unconnected probe reads LOW, not random noise
  Serial.begin(115200);
  delay(1500);
  Serial.println("Stage 2 loopback ready. Probe wire: GPIO26 -> 1k resistor -> touch GPIO16..23.");
}

void loop() {
  static uint16_t last = 0xFFFF, candidate = 0xFFFF;
  static int stable = 0;

  uint16_t s = scan();
  // Only report once a reading holds for ~30 ms, so wiggling the wire
  // between holes doesn't spam half-contacts.
  if (s == candidate) { if (++stable == 3 && s != last) { report(s); last = s; } }
  else { candidate = s; stable = 0; }

  // A heartbeat every few seconds so a silent monitor means "not running",
  // never "waiting for you".
  static unsigned long t = 0;
  if (millis() - t > 5000) { t = millis(); Serial.print("."); Serial.println(__builtin_popcount(verified)); }
  delay(10);
}
