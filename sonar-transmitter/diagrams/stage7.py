from pictorial import *
s = Sheet(1400, 820, 'Stage 7 — real waveforms (firmware only: no new wiring)',
          'This sheet is the whole system as built after Stages 3–6, so you can see every connection at once.')
L, R = shrike(s, 560, 110, used={'L:5V#0', 'L:3.3V#1', 'L:IO5', 'L:IO6', 'L:IO7', 'L:GND#7', 'L:IO9', 'L:IO10', 'L:IO11',
                                  'R:IO16', 'R:IO17', 'R:IO18', 'R:IO19', 'R:IO20', 'R:IO21', 'R:IO22', 'R:IO23', 'R:IO24', 'R:IO25'},
             note='Shrike Lite (USB-C at top)')
def block(x, y, w, h, title, lines, color):
    s.rect(x, y, w, h, fill='#ffffff', stroke=color, sw=2.2, r=10)
    s.text(x + 14, y + 24, title, size=13, fill=color, weight='700')
    for i, t in enumerate(lines):
        s.text(x + 14, y + 46 + i * 17, t, size=10.5, fill='#37474f')
block(60, 120, 330, 170, 'Sensors (Stage 3)', ['DS18B20 temp → IO5 (1-Wire)', 'ADS1115: A0 turbidity, A1 depth pot', 'INA219 power monitor', 'I²C: SDA IO6 · SCL IO7', '3.3 V + 5 V + GND rails'], COL['sda'])
block(60, 330, 330, 150, 'Digital pot (Stage 6)', ['MCP41010 on 3.3 V', '/CS IO9 · SCK IO10 · SI IO11', 'sets amplitude in analog'], COL['spi'])
block(900, 120, 420, 150, 'Latch + ladder DAC (Stage 4)', ['IO16–23 → D0–D7 · IO24 → CP (PIO side-set)', '74HC574 → R-2R ladder → LADDER OUT', '8-bit, idle code 128 = 1.65 V'], '#5e35b1')
block(900, 320, 420, 150, 'Filter + output amp (Stage 6)', ['Sallen-Key + RC ≈ 700 kHz low-pass', 'digital-pot volume → op-amp B (gain 1.47)', '47 Ω → BNC (module boundary)'], COL['ana'])
block(900, 520, 420, 110, 'Scope (Stage 5)', ['CH1 ← BNC  ·  CH2 ← TRIG (IO25 via 100 Ω)', 'trigger on CH2 rising edge'], '#0288d1')
s.wire([(390, 205), (548, 205)], COL['sda'], sw=4); s.tag(470, 205, 'IO5 · IO6 · IO7', COL['sda'])
s.wire([(390, 405), (470, 405), (470, 330), (548, 330)], COL['spi'], sw=4); s.tag(470, 370, 'IO9–11', COL['spi'])
s.wire([(740, 480), (840, 480), (840, 195), (900, 195)], '#5e35b1', sw=4); s.tag(840, 300, 'IO16–24', '#5e35b1')
s.wire([(1110, 270), (1110, 320)], '#5e35b1', sw=4); s.tag(1110, 295, 'LADDER OUT', '#5e35b1')
s.wire([(1110, 470), (1110, 520)], COL['ana'], sw=4); s.tag(1110, 495, 'BNC', COL['ana'])
s.wire([(740, 308), (800, 308), (800, 600), (900, 600)], COL['trig'], sw=3); s.tag(800, 560, 'IO25 TRIG', '#f57f17')
notes(s, 60, 690, [
    '• Build all three modulation types: LFM chirp, geometric sweep, Barker-13 phase code. Make them switchable at runtime.',
    '• Window the chirps (Hann or Blackman; avoid Hamming: it leaves an 8 % step). NEVER window the Barker code: use rectangular.',
    '• Stream the Sim-0 tables (sim/sim0/out/firmware/*.h) and check their CRC-32 on the board; run the clock at 120 or 200 MHz.',
    'Gate: all three types switchable on the scope, plus the rectangular-vs-Hann sidelobe capture for the submission.',
], title='What changes in this stage (firmware)')
save(s, 'stage7_system_overview', '.')
