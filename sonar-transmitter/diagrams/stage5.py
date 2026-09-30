from pictorial import *
s = Sheet(1180, 700, 'Stage 5 — first waveform on the scope',
          'No new circuitry: firmware streams a sine into the ladder. Add the scope trigger resistor.')
used = {'R:IO25', 'R:GND#12'}
L, R = shrike(s, 40, 110, used=used)
# the Stage 4 board, as a block
s.rect(420, 120, 250, 150, fill='#ede7f6', stroke='#5e35b1', sw=2, r=10)
s.text(545, 155, "Stage 4 board", size=13, fill='#311b92', anchor='middle', weight='700')
s.text(545, 175, "74HC574 + R-2R ladder", size=11, fill='#4527a0', anchor='middle')
lo = terminal(s, 670, 220, '', color='#5e35b1')
s.text(660, 215, 'LADDER OUT', size=10.5, fill='#311b92', anchor='end', weight='700')
lg = terminal(s, 670, 255, '', color=COL['gnd'])
s.text(660, 259, 'GND', size=10.5, fill='#311b92', anchor='end', weight='700')
s.text(545, 200, '(GPIO16–24 wiring', size=10, fill='#5e35b1', anchor='middle', italic=True)
s.text(545, 214, ' as in Stage 4)', size=10, fill='#5e35b1', anchor='middle', italic=True)
sc = scope(s, 840, 140)
# CH1 probe on LADDER OUT
c1 = sc['CH1']
s.wire([lo, (760, lo[1]), (760, c1[1]), c1], '#0288d1', sw=4)
s.tag(760, 205, 'CH1 probe tip', '#0288d1')
s.wire([lg, (730, lg[1]), (730, 330)], COL['gnd'], sw=2)
gnd_sym(s, 730, 330)
s.text(742, 352, 'CH1 ground clip', size=10, fill=COL['gnd'], italic=True)
# trigger: IO25 -> 100 ohm -> TRIG pin -> CH2
p25 = R['IO25']
s.wire([p25, (300, p25[1])], COL['trig'])
resistor(s, 300, p25[1], 390, p25[1], '100 Ω', label_side=1)
trig = terminal(s, 440, p25[1], '', color=COL['trig'])
s.wire([(390, p25[1]), trig], COL['trig'])
s.text(452, p25[1] + 20, 'TRIG header pin', size=10.5, fill='#f57f17', weight='700')
c2 = sc['CH2']
s.wire([trig, (800, trig[1]), (800, c2[1]), c2], '#0288d1', sw=4)
s.tag(800, trig[1] - 40, 'CH2 probe tip', '#0288d1')
g = R['GND#12']
s.wire([g, (300, g[1]), (300, g[1] + 40)], COL['gnd'], sw=2)
gnd_sym(s, 300, g[1] + 40)
s.text(312, g[1] + 62, 'CH2 ground clip', size=10, fill=COL['gnd'], italic=True)
notes(s, 420, 560, [
    '• The 100 Ω in series protects IO25 if a scope lead ever shorts it.',
    '• Both probe ground clips go to GND: never to 3.3 V or 5 V.',
    '• Trigger the scope on CH2 (rising edge); firmware raises IO25 just before each burst.',
    '• Start by bit-banging ~100 kS/s; then move to PIO+DMA at 1 → 5 → 10 MS/s.',
    'Gate: a recognisable stepped sine at the expected frequency (count steps per cycle).',
], title='Notes')
save(s, 'stage5_scope', '.')
