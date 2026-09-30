from pictorial import *
s = Sheet(1400, 780, 'Stage 8 — close the adaptation loop',
          'Only new hardware: the optional TDS (salinity) sensor on ADS1115 A2. Everything else is firmware.')
L, R = shrike(s, 1120, 96, used={'L:3.3V#1', 'L:IO6', 'L:IO7', 'L:GND#7'}, note='Shrike Lite (USB-C at top)')
Y = {k: L[k][1] for k in ('3.3V#1', 'IO6', 'IO7', 'GND#7')}
PX = L['IO6'][0]
for key, c, name in (('3.3V#1', 'v33', '3.3 V'), ('IO6', 'sda', 'SDA → IO6'), ('IO7', 'scl', 'SCL → IO7'), ('GND#7', 'gnd', 'GND')):
    s.wire([(470, Y[key]), (PX, Y[key])], COL[c], sw=3.2)
    s.tag(560, Y[key], name, COL[c])
ads = module_top(s, 640, 380, 'ADS1115 (as Stage 3)', ['VDD', 'GND', 'SCL', 'SDA', 'ADDR', 'ALRT', 'A0', 'A1', 'A2', 'A3'],
                 used={'A2'}, color='#1a237e', dim='#c5cae9')
s.text(640 + 135, 380 + 150, 'VDD/GND/SCL/SDA/ADDR/A0/A1 stay as in Stage 3', size=10, fill='#1a237e', anchor='middle', italic=True)
tds = module_top(s, 470, 380, 'TDS SEN0244', ['+ VCC', '− GND', 'A OUT'], color='#00695c', w=130, subtitle='optional: not yet ordered')
drop(s, tds['+ VCC'], Y['3.3V#1'], COL['v33'])
drop(s, tds['− GND'], Y['GND#7'], COL['gnd'])
s.wire([tds['A OUT'], (tds['A OUT'][0], 350), (ads['A2'][0], 350), ads['A2']], COL['ana'])
s.tag((tds['A OUT'][0] + ads['A2'][0]) / 2, 350, 'TDS A → ADS1115 A2 (0–2.3 V: no divider)', COL['ana'])
# the loop, as a picture
bx, by = 40, 110
s.rect(bx, by, 390, 540, fill='#ffffff', stroke='#cfd8dc', sw=1.2, r=10)
s.text(bx + 16, by + 26, 'The loop (firmware, every ~100 ms)', size=13, fill='#1a1a18', weight='700')
steps = [('Read', 'temp (IO5) · turbidity (A0) · depth pot (A1) · TDS (A2) · battery (INA219)'),
         ('Decide', 'pick a mode from calibrated thresholds with hysteresis, so it never flickers between modes'),
         ('Pick', 'centre frequency · bandwidth · pulse length · window'),
         ('Rebuild', 'only if the mode changed: build the new buffer, swap it in at a pulse boundary, never mid-pulse'),
         ('Set amplitude', 'MCP41010 wiper over SPI: analog, never by scaling samples'),
         ('Report', 'mode + measured latency over USB serial')]
for i, (h, t) in enumerate(steps):
    yy = by + 64 + i * 76
    s.circle(bx + 30, yy, 13, fill='#e3f2fd', stroke='#1e88e5', sw=1.6)
    s.text(bx + 30, yy + 5, str(i + 1), size=12, fill='#0d47a1', anchor='middle', weight='700')
    s.text(bx + 54, yy + 4, h, size=12, fill='#0d47a1', weight='700')
    words, line, lines = t.split(), '', []
    for w in words:
        if len(line + w) > 44: lines.append(line); line = ''
        line += w + ' '
    lines.append(line)
    for j, ln in enumerate(lines):
        s.text(bx + 54, yy + 22 + j * 15, ln.strip(), size=10.5, fill='#37474f')
    if i < len(steps) - 1:
        s.line(bx + 30, yy + 14, bx + 30, yy + 62, stroke='#90caf9', sw=2)
notes(s, 470, 600, [
    '• Demo: stir mud into the water and the waveform on the scope changes by itself. Record it on video.',
    '• Salinity demo (if the TDS sensor arrives): add salt and watch the mode shift.',
    '• Depth changes absorption by only ~3 % at 200 m: justify "deep → low frequency" by the longer range needed.',
], title='Notes')
notes(s, 470, 700, ['Gate: mud goes in, waveform changes on its own, and the latency is measured and printed.'], size=12)
save(s, 'stage8_adaptation', '.')
