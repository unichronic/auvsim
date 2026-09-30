from pictorial import *
s = Sheet(1720, 1010, 'Stage 6 — filter, digital-pot volume control, output amp, BNC',
          'Two SOIC chips on SOP8→DIP8 adapters (you have exactly one of each: practise first). Ground symbol = connect to the GND rail.')
used = {'L:5V#0', 'L:3.3V#1', 'L:IO9', 'L:IO10', 'L:IO11', 'L:GND#7'}
L, R = shrike(s, 1480, 56, used=used, note='Shrike Lite (USB-C at top)')
V5, V33 = L['5V#0'][1], L['3.3V#1'][1]
s.wire([(40, V5), L['5V#0']], COL['v5'], sw=3.2); s.tag(120, V5, '5 V rail (analog)', COL['v5'])
s.wire([(40, V33), L['3.3V#1']], COL['v33'], sw=3.2); s.tag(300, V33, '3.3 V rail', COL['v33'])
g = L['GND#7']
s.wire([g, (1462, g[1])], COL['gnd']); gnd_sym(s, 1462, g[1])

T = dip2(s, 560, 330, 8, 'TSH82', ['OUT1', 'IN1−', 'IN1+', 'GND', 'IN2+', 'IN2−', 'OUT2', 'VCC+'],
         sub='on SOP8→DIP8')
M = dip2(s, 1100, 330, 8, 'MCP41010', ['/CS', 'SCK', 'SI', 'VSS', 'PA0', 'PW0', 'PB0', 'VDD'],
         sub='rotated 180°', flip=True)
s.text(610, 562, 'op-amp A (pins 1–3) = filter', size=10, fill='#546e7a', anchor='middle', italic=True)
s.text(610, 576, 'op-amp B (pins 5–7) = output', size=10, fill='#546e7a', anchor='middle', italic=True)

# ---- input + Sallen-Key (op-amp A) -------------------------------------------
tin = terminal(s, 90, 428, '', color='#5e35b1')
s.text(90, 410, 'LADDER OUT', size=11.5, fill='#311b92', anchor='middle', weight='700')
s.text(90, 452, '(Stage 4, node 7)', size=9.5, fill='#5e35b1', anchor='middle')
A, X = (200, 428), (340, 428)
s.wire([tin, A], COL['ana'], dots=(1,))
resistor(s, A[0], A[1], X[0], X[1], 'R2 1 kΩ', label_side=-1)
s.wire([X, T[3]], COL['ana'], dots=(0,))
capacitor(s, X[0], X[1], X[0], 500, 'C2 100 pF', label_side=1); gnd_sym(s, X[0], 500)
capacitor(s, A[0], A[1], A[0], 348, 'C1 470 pF', label_side=-1)
s.wire([(A[0], 348), (440, 348), (544, 348), T[1]], COL['ana'], dots=(1, 2))
s.wire([(544, 348), (544, 388), T[2]], COL['ana'])
s.text(510, 404, 'IN1− ↔ OUT1', size=9, fill='#546e7a', anchor='end', italic=True)
s.wire([T[4], (526, T[4][1])], COL['gnd']); gnd_sym(s, 526, T[4][1])
# 3rd pole: OUT1 -> 1k -> P, 220 pF to ground
P = (585, 250)
s.wire([(440, 348), (440, P[1])], COL['ana'])
resistor(s, 440, P[1], P[0], P[1], '1 kΩ', label_side=1)
capacitor(s, P[0], P[1], P[0], 292, '220 pF', label_side=-1); gnd_sym(s, P[0], 292)
s.text(P[0] + 8, P[1] - 14, 'P', size=11, fill=COL['ana'], weight='700')
# TSH82 power + decoupling
s.wire([T[8], (712, T[8][1]), (712, V5)], COL['v5'], dots=(2,))
capacitor(s, 712, 302, 640, 302, '', label_side=1); gnd_sym(s, 640, 302)
s.circle(712, 302, 4, fill=COL['v5'], stroke='#fff', sw=1)
s.text(640, 296, '0.1 µF', size=9.5, fill='#bf360c', anchor='end', weight='700')

# ---- P -> digital pot (volume control) ---------------------------------------
s.wire([P, (1040, P[1]), (1040, M[5][1]), M[5]], COL['ana'], dots=(0,))
s.tag(870, P[1], 'filtered signal P → PA0', COL['ana'])
s.wire([M[7], (1070, M[7][1])], COL['gnd']); gnd_sym(s, 1070, M[7][1])
s.wire([M[8], (1015, M[8][1]), (1015, V33)], COL['v33'], dots=(2,))
capacitor(s, 1050, M[8][1], 1050, 530, '0.1 µF', label_side=1); gnd_sym(s, 1050, 530)
s.circle(1050, M[8][1], 4, fill=COL['v33'], stroke='#fff', sw=1)
s.wire([M[4], (1236, M[4][1])], COL['gnd']); gnd_sym(s, 1236, M[4][1])
# SPI from the board
for pin, lane, col, lab in ((1, 1300, '#8d6e63', 'from IO9'), (2, 1330, '#ec407a', 'from IO10'), (3, 1360, '#00897b', 'from IO11')):
    src = L[{1: 'IO9', 2: 'IO10', 3: 'IO11'}[pin]]
    s.wire([src, (lane, src[1]), (lane, M[pin][1]), M[pin]], col, sw=2.4)
    s.text(M[pin][0] + 50, M[pin][1] + 16, lab, size=9.5, fill=col, weight='700')

# ---- wiper -> AC coupling -> op-amp B -----------------------------------------
Q = (820, 468)
s.wire([M[6], (900, M[6][1])], COL['ana'])
capacitor(s, 900, M[6][1], 820, M[6][1], '0.1 µF', label_side=1)
s.wire([(820, M[6][1]), Q], COL['ana'])
s.wire([T[5], Q], COL['ana'], dots=(1,))
s.text(870, M[6][1] + 36, 'wiper PW0 → AC-couple → IN2+', size=9.5, fill=COL['ana'], italic=True)
VB = (820, 600)
resistor(s, Q[0], Q[1], VB[0], VB[1], '100 kΩ', label_side=-1)
# IN2- network: 10k to VB, 4.7k to OUT2
s.wire([T[6], (720, T[6][1]), (760, T[6][1])], COL['ana'], dots=(1, 2))
s.wire([(720, T[6][1]), (720, VB[1])], COL['ana'])
resistor(s, 720, VB[1], VB[0], VB[1], '10 kΩ', label_side=-1)
s.wire([T[7], (760, T[7][1])], '#5e35b1', dots=(1,))
resistor(s, 760, T[7][1], 760, T[6][1], '4.7 kΩ', label_side=1)
# VB bias network
s.wire([VB, (960, VB[1])], COL['ana'], dots=(0, 1))
s.text(VB[0] + 4, VB[1] + 20, 'VB = 2.5 V', size=10.5, fill=COL['ana'], weight='700')
resistor(s, 960, VB[1], 960, 520, '10 kΩ', label_side=1)
s.wire([(960, 520), (960, V5)], COL['v5'], dots=(1,))
resistor(s, 960, VB[1], 960, 690, '10 kΩ', label_side=1); gnd_sym(s, 960, 690)
capacitor(s, 880, VB[1], 880, 690, '0.1 µF', label_side=-1); gnd_sym(s, 880, 690)
s.circle(880, VB[1], 4, fill=COL['ana'], stroke='#fff', sw=1)
# OUT2 -> 47 ohm -> BNC
s.wire([(760, T[7][1]), (760, 175)], '#5e35b1')
resistor(s, 760, 175, 860, 175, '47 Ω', label_side=1)
b = bnc(s, 925, 175, label='BNC out')
s.wire([(860, 175), (908, 175)], '#5e35b1')
gnd_sym(s, b['shell'][0], b['shell'][1])

legend(s, 40, 760, [('v5', '5 V (TSH82, bias)'), ('v33', '3.3 V (digital pot)'), ('gnd', 'GND'), ('ana', 'analog signal')],
       extra=['ground symbol = to GND rail · dot = joined'])
notes(s, 330, 770, [
    '• Signal path: LADDER OUT → Sallen-Key (op-amp A, ~730 kHz) → RC pole → pot PA0 → wiper PW0 → 0.1 µF → IN2+ → OUT2 → 47 Ω → BNC.',
    '• TSH82 on 5 V (pin 8); MCP41010 on 3.3 V (pin 8 = VDD). The pot must NOT go on 5 V: its SPI needs 0.7 × VDD.',
    '• Capacitors in the signal path (470 p, 100 p, 220 p) must be C0G/NP0: small values in your kit almost always are.',
    '• MCP41010 is drawn rotated 180° so its analog pins face the op-amp; check pin 1 (dot) before seating it.',
    '• Before inserting chips: TSH82 socket pin 8 = 5 V, MCP41010 socket pin 8 = 3.3 V, VB = 2.5 V, both pin 4 = 0 V.',
    '• Firmware caps the pot wiper at ~75 % until the TSH82 input common-mode range at 5 V is checked.',
], title='Notes')
notes(s, 330, 900, ['Gate: scope on LADDER OUT shows a staircase; scope on BNC shows a smooth sine. Screenshot both.'], size=12)
save(s, 'stage6_analog_chain', '.')
