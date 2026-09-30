// Stage 1 — toolchain, USB and upload path.
//
// This sketch does nothing useful for sonar. That is the point: it proves
// the IDE, the board core, the USB connection and the upload path all work,
// so that when something fails in Stage 5 you already know it isn't any of these.
//
// Board:  Generic RP2040  (arduino-pico core by Earle Philhower)
// Gate:   the onboard LED blinks.

const int LED_PIN = 4;  // Shrike Lite onboard LED is on GPIO4

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(115200);
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  delay(500);
  digitalWrite(LED_PIN, LOW);
  delay(500);

  // If the LED blinks but you see nothing here, the blink still counts as a
  // pass -- Serial Monitor just needs the right port and 115200 baud.
  Serial.println("alive");
}
