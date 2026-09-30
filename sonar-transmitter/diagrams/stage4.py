from pictorial import *
BIT = ['#8d6e63', '#ec407a', '#ffa000', '#c0ca33', '#43a047', '#039be5', '#7e57c2', '#78909c']

s = Sheet(1480, 920, "Stage 4 — 74HC574 latch + R-2R ladder (this IS the DAC)",
          "Build on a breadboard first. Soldered version adds the 33 Ω resistors. '574 runs on 3.3 V, never 5 V.")
used = {'R:3.3V#1', 'R:GND#6', 'R:IO24', 'R:IO16', 'R:IO17', 'R:IO18', 'R:IO19', 'R:IO20', 'R:IO21', 'R:IO22', 'R:IO23'}
L, R = shrike(s, 40, 100, used=used, note='Shrike Lite (USB-C at top)')
V33, GNDY = R['3.3V#1'][1], R['GND#6'][1]
s.wire([R['3.3V#1'], (1440, V33)], COL['v33'], sw=3.2)
s.tag(360, V33, '3.3 V', COL['v33'])
s.wire([R['GND#6'], (1440, GNDY)], COL['gnd'], sw=3.2)
s.tag(360, GNDY, 'GND', COL['gnd'])

names = ['/OE', 'D0', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'GND',
         'CP', 'Q7', 'Q6', 'Q5', 'Q4', 'Q3', 'Q2', 'Q1', 'Q0', 'VCC']
P = dip(s, 560, 313, 20, "74HC574 (DIP-20, 3.3 V)", names, sub='notch up · dot = pin 1')

# D0..D7 <- IO16..IO23
for k in range(8):
    src = R[f'IO{16 + k}']
    dst = P[k + 2]
    lane = 270 + 30 * k
    s.wire([src, (lane, src[1]), (lane, dst[1]), dst], BIT[k], sw=2.4)
# CP <- IO24 (goes under the chip to pin 11 on the right side)
cp = R['IO24']
s.wire([cp, (236, cp[1]), (236, 618), (730, 618), (730, P[11][1]), P[11]], COL['clk'], sw=2.6)
s.tag(460, 618, 'IO24 → CP (pin 11) latch clock', COL['clk'])
# OE-bar -> GND, pin 10 -> GND, VCC -> 3.3 V
s.wire([P[1], (532, P[1][1]), (532, GNDY)], COL['gnd'], dots=(2,))
s.text(526, P[1][1] - 30, '/OE → GND', size=9.5, fill=COL['gnd'], anchor='end', italic=True)
s.wire([P[10], (532, P[10][1])], COL['gnd'])
gnd_sym(s, 532, P[10][1])
s.wire([P[20], (730, P[20][1]), (730, V33)], COL['v33'], dots=(2,))
capacitor(s, 770, V33, 770, GNDY, '0.1 µF at pins 20↔10', label_side=1)
s.circle(770, V33, 4.2, fill=COL['v33'], stroke='#fff', sw=1.2)
s.circle(770, GNDY, 4.2, fill=COL['gnd'], stroke='#fff', sw=1.2)

# ---- the ladder ----------------------------------------------------------------
NODE_X, CH0 = 1090, 860
for k in range(8):
    q = P[19 - k]                           # Q0 = pin 19 ... Q7 = pin 12
    ny = 400 + 56 * k
    lane = 820 - 12 * k
    s.wire([q, (lane, q[1]), (lane, ny), (CH0, ny)], BIT[k], sw=2.4)
    s.text(CH0 - 6, ny - 8, f'Q{k}', size=10, fill=BIT[k], anchor='end', weight='700')
    resistor(s, CH0, ny, CH0 + 70, ny, '')
    resistor(s, CH0 + 70, ny, CH0 + 140, ny, '')
    resistor(s, CH0 + 140, ny, CH0 + 210 - 20, ny, '')
    s.wire([(CH0 + 190, ny), (NODE_X + 130, ny)], '#607d8b', sw=1.8)
for k in range(8):
    ny = 400 + 56 * k
    nx = NODE_X + 130
    s.circle(nx, ny, 5, fill='#37474f', stroke='#fff', sw=1.2)
    s.text(nx + 12, ny - 8, f'node {k}', size=10, fill='#37474f', weight='700')
    if k < 7:
        resistor(s, nx, ny, nx, ny + 56, '1 kΩ', label_side=1)
NX = NODE_X + 130
s.text(CH0 + 35, 346, '33 Ω', size=10.5, fill='#0d47a1', anchor='middle', weight='700')
s.text(CH0 + 140, 346, '2R = 1 kΩ + 1 kΩ', size=10.5, fill='#0d47a1', anchor='middle', weight='700')
s.text(CH0 + 35, 361, '(skip on breadboard)', size=9, fill='#546e7a', anchor='middle', italic=True)
# terminator: node 0 -> 1k -> 1k -> GND
resistor(s, NX, 400, NX, 338, '')
resistor(s, NX, 338, NX, GNDY, '')
s.circle(NX, GNDY, 4.2, fill=COL['gnd'], stroke='#fff', sw=1.2)
s.text(NX + 14, 330, '2R terminator', size=10, fill='#0d47a1', weight='700')
s.text(NX + 14, 344, '(1 kΩ + 1 kΩ to GND)', size=9.5, fill='#0d47a1')
out = terminal(s, 1380, 400 + 56 * 7, '', color='#5e35b1')
s.wire([(NX, 400 + 56 * 7), out], '#5e35b1', sw=3)
s.text(1380, 400 + 56 * 7 + 26, 'LADDER OUT', size=12, fill='#311b92', anchor='middle', weight='700')
s.text(1380, 400 + 56 * 7 + 42, '→ Stage 6 · meter · scope', size=10, fill='#5e35b1', anchor='middle')

notes(s, 40, 660, [
    "• IO16→D0 (pin 2) … IO23→D7 (pin 9): wire colours match bits on both sides of the chip.",
    "• The '574's outputs are reversed: Q7 = pin 12 … Q0 = pin 19. Q7 (MSB) feeds node 7 = the output end.",
    "• Parts: 25 × 1 kΩ (16 in the 2R arms, 2 in the terminator, 7 R links) + 8 × 33 Ω (soldered build only).",
    "• With the '574 pulled out, before power: each Q wire → its node = 2.0 kΩ;",
    "  node 0 → GND = 2.0 kΩ; node 7 → GND = 9.0 kΩ. Anything else = a resistor in the wrong hole.",
    "• Firmware for the gate must write the code AND pulse CP (IO24): Stage 2's sketch never clocks the latch.",
    "• /OE = output enable, active low: tied to GND the outputs are always on (Stage 9 moves it to IO8).",
], title='Build notes')
notes(s, 900, 870 - 16, ['Static-test gate: codes 0 / 64 / 128 / 192 / 255 read ≈ 0 / 0.82 / 1.65 / 2.47 / 3.29 V,',
                         'and every single step going 0 → 255 must read higher than the one before.'], size=11)
save(s, 'stage4_latch_ladder', '.')
