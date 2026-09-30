from pictorial import *
s = Sheet(1440, 860, 'Stage 9 — power optimisation, pod and rehearsal',
          'Three hardware changes, each shown with a before/after INA219 reading as low-power evidence.')
used = {'L:5V#0', 'L:IO8', 'R:IO27'}
L, R = shrike(s, 560, 100, used=used, note='Shrike Lite (USB-C at top)')

# --- (1) '574 /OE moves from GND to IO8 ------------------------------------------
names = ['/OE', 'D0', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'GND', 'CP', 'Q7', 'Q6', 'Q5', 'Q4', 'Q3', 'Q2', 'Q1', 'Q0', 'VCC']
P = dip(s, 170, 236, 20, "74HC574 (rest as Stage 4)", names)
io8 = L['IO8']
s.wire([P[1], (140, P[1][1]), (140, 160), (470, 160), (470, io8[1]), io8], COL['clk'], sw=2.6)
s.tag(300, 160, '① /OE (pin 1) → IO8   (was GND)', COL['clk'])
s.text(170, 486, 'IO8 LOW = outputs on (during a ping)', size=10.5, fill='#37474f')
s.text(170, 502, 'IO8 HIGH = outputs off: ladder draws nothing', size=10.5, fill='#37474f')

# --- (2) INA219 in series with the 5 V feed ----------------------------------------
ina = module(s, 120, 560, 'INA219', ['VCC', 'GND', 'SCL', 'SDA', 'VIN-', 'VIN+'], used={'VIN-', 'VIN+'}, color='#6a1b9a', side='right')
v5 = L['5V#0']
s.wire([ina['VIN+'], (500, ina['VIN+'][1]), (500, v5[1]), v5], COL['v5'], sw=3)
s.tag(500, 540, '② Shrike 5V → VIN+', COL['v5'])
vout = terminal(s, 360, ina['VIN-'][1], '', color=COL['v5'])
s.wire([ina['VIN-'], vout], COL['v5'], sw=3)
s.text(372, ina['VIN-'][1] + 4, 'VIN− → 5 V rail', size=10.5, fill='#e65100', weight='700')
s.text(120, 760, 'VCC/GND/SCL/SDA stay as in Stage 3. The breadboard 5 V rail', size=10.5, fill='#37474f')
s.text(120, 776, 'must now be fed ONLY through the INA219, or it measures nothing.', size=10.5, fill='#37474f', weight='700')

# --- (3) 2N2222 low-side switch for the turbidity sensor ----------------------------
q = to92(s, 1000, 470)
io27 = R['IO27']
s.wire([io27, (820, io27[1])], COL['clk'])
resistor(s, 820, io27[1], 900, io27[1], '1 kΩ', label_side=1)
s.wire([(900, io27[1]), (940, io27[1]), (940, 590), (q['B'][0], 590), q['B']], COL['clk'])
s.tag(870, io27[1] - 36, '③ IO27 → 1 kΩ → base', COL['clk'])
s.wire([q['E'], (q['E'][0], 520), (962, 520)], COL['gnd']); gnd_sym(s, 962, 520)
tb = module(s, 1180, 330, 'Turbidity AZDM01', ['VCC', 'GND', 'AOUT'], color='#4e342e', w=190, side='left')
s.wire([tb['GND'], (1120, tb['GND'][1]), (1120, 630), (q['C'][0], 630), q['C']], COL['gnd'], sw=2.4)
s.text(1126, 620, 'sensor GND → collector', size=10, fill=COL['gnd'], italic=True)
t5 = terminal(s, 1110, tb['VCC'][1], '', color=COL['v5'])
s.wire([t5, tb['VCC']], COL['v5'])
s.text(1100, tb['VCC'][1] + 4, 'VCC stays on the 5 V rail', size=10, fill='#e65100', anchor='end', weight='700')
ta = terminal(s, 1220, 520, '', color=COL['ana'])
s.wire([tb['AOUT'], (1150, tb['AOUT'][1]), (1150, ta[1]), ta], COL['ana'])
s.text(1232, 524, 'AOUT → 10 k/10 k divider → A0', size=10, fill=COL['ana'], weight='700')
s.text(1060, 670, '2N2222 plastic TO-92: flat face towards you, legs down = E · B · C.', size=10.5, fill='#37474f', anchor='middle')
s.text(1060, 686, 'Check YOUR part\'s datasheet: metal-can and some clones differ.', size=10.5, fill='#b71c1c', anchor='middle', weight='700')

notes(s, 560, 700, [
    '• Firmware: IO27 HIGH powers the turbidity sensor; wait ~100 ms to settle, read, then LOW. Read only while powered.',
    '• IO27 and IO8 are new pin assignments (both were spare): add them to the pin map in COMPONENTS.md.',
    '• Log INA219 power before and after ① and ③: that table is the evidence for the low-power requirement.',
    '• As wired, the INA219 sees the 5 V rail only (sensors + analog), NOT the RP2040. Say so in the submission, or feed',
    '  the whole board through it (check Vicharak\'s schematic before back-feeding the 5V pin).',
    '• Then: print the pod, fit everything inside, run from the power bank with no laptop, rehearse twice end to end.',
], title='Notes')
save(s, 'stage9_power', '.')
