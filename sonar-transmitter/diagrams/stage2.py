from pictorial import *
s = Sheet(1060, 760, 'Stage 2 — prove the DAC bus (self-loopback)',
          'One probe wire, no LEDs, no multimeter. Status: PASSED 25 Sep 2026 (all 8 pins verified).')
used = {'R:IO26', 'R:IO16', 'R:IO17', 'R:IO18', 'R:IO19', 'R:IO20', 'R:IO21', 'R:IO22', 'R:IO23'}
L, R = shrike(s, 300, 110, used=used)
p26 = R['IO26']
s.wire([p26, (560, p26[1])], COL['probe'])
resistor(s, 560, p26[1], 650, p26[1], '1 kΩ (safety)', label_side=1)
tip = (720, 470)
s.wire([(650, p26[1]), (900, p26[1]), (900, tip[1] - 40), (tip[0], tip[1] - 40), (tip[0], tip[1] - 14)], COL['probe'])
# probe tip
s.path(f'M{tip[0]-6},{tip[1]-14} L{tip[0]+6},{tip[1]-14} L{tip[0]},{tip[1]} Z', '#37474f', sw=1, fill='#b0bec5')
s.text(tip[0] + 14, tip[1] + 4, 'probe end: touch each bus pin in turn', size=11, fill=COL['probe'], weight='700')
order = ['IO16', 'IO17', 'IO18', 'IO19', 'IO20', 'IO21', 'IO22', 'IO23']
for i, name in enumerate(order):
    px, py = R[name]
    s.line(tip[0] - 2, tip[1] - 2, px + 8, py, stroke=COL['probe'], sw=1.2, dash='5 4')
    s.tag(px + 36 + (i % 2) * 44, py, f'{i + 1}', COL['probe'], size=10)
g = R['GND#12']
s.line(g[0] + 12, g[1] - 7, g[0] + 26, g[1] + 7, stroke='#c62828', sw=2.5)
s.line(g[0] + 12, g[1] + 7, g[0] + 26, g[1] - 7, stroke='#c62828', sw=2.5)
s.text(g[0] + 34, g[1] - 10, 'GND: skip', size=10.5, fill='#c62828', weight='700')
notes(s, 40, 120, [
    'How it works:',
    'firmware/stage2_loopback drives',
    'GPIO16–23 one at a time and reads',
    'IO26. Whichever bus pin the probe',
    'touches reports its own GPIO number.',
    '',
    'Catches: dead pins, swapped pins,',
    'and solder bridges (two pins at once).',
], size=11)
notes(s, 40, 640, [
    'Serial shows:  probe on GPIO18  OK   verified so far: 16 17 18  (3/8)',
    'Gate: "STAGE 2 PASS: all eight DAC bus pins toggle, correct identity, no bridges".',
    'A GND pin sits between IO21 and IO20 (red ×). Find pins by their printed LABEL, never by counting.',
], size=11.5)
save(s, 'stage2_bus_loopback', '.')
