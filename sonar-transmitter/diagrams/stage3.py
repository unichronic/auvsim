from pictorial import *

s = Sheet(1580, 830, 'Stage 3 — sensors on the breadboard',
          'Every sensor hangs off six lines that run straight into the Shrike Lite LEFT header. '
          'No soldering except module header pins.')

# ---- Shrike Lite on the right; its left-header pins set the bus heights --------
BX, BY = 1350, 96
used = {'L:5V#0', 'L:3.3V#1', 'L:IO5', 'L:IO6', 'L:IO7', 'L:GND#7'}
L, R = shrike(s, BX, BY, used=used)
Y = {k: L[k][1] for k in ('5V#0', '3.3V#1', 'IO5', 'IO6', 'IO7', 'GND#7')}
PX = L['IO5'][0]

buses = [('5V#0', 'v5', '5 V  (header 5V = USB VBUS)'),
         ('3.3V#1', 'v33', '3.3 V'),
         ('IO5', 'ow', '1-Wire  → IO5'),
         ('IO6', 'sda', 'I²C SDA  → IO6'),
         ('IO7', 'scl', 'I²C SCL  → IO7'),
         ('GND#7', 'gnd', 'GND  (any GND pin)')]
X0 = 34
for key, c, name in buses:
    s.wire([(X0, Y[key]), (PX, Y[key])], COL[c], sw=3.2)
    s.tag(X0 + 108, Y[key], name, COL[c])
s.text(PX - 30, Y['GND#7'] - 30, 'IO8 · IO9 unused', size=9.5, fill='#90a4ae', anchor='end', italic=True)

MY = 410                   # module top edge
LANE_A1, LANE_A0 = Y['GND#7'] + 32, Y['GND#7'] + 60

# ---- DS18B20 probe ---------------------------------------------------------
ds = module_top(s, 250, MY, 'DS18B20 probe', ['RED', 'BLACK', 'YELLOW'], color='#37474f', w=150,
                subtitle='colours vary: check yours', lead_colors=['#d32f2f', '#111', '#fbc02d'])
drop(s, ds['RED'], Y['3.3V#1'], COL['v33'])
drop(s, ds['BLACK'], Y['GND#7'], COL['gnd'])
drop(s, ds['YELLOW'], Y['IO5'], COL['ow'])
# pull-up straddling RED (3.3 V) and YELLOW (data)
py = MY - 38
resistor(s, ds['RED'][0], py, ds['YELLOW'][0], py, '4.7 kΩ', label_side=-1)
s.circle(ds['RED'][0], py, 4.2, fill=COL['v33'], stroke='#fff', sw=1.2)
s.circle(ds['YELLOW'][0], py, 4.2, fill=COL['ow'], stroke='#fff', sw=1.2)
s.text(ds['YELLOW'][0] + 14, py + 4, 'pull-up (mandatory)', size=9.5, fill='#b71c1c', italic=True)

# ---- INA219 -----------------------------------------------------------------
ina = module_top(s, 450, MY, 'INA219', ['VCC', 'GND', 'SCL', 'SDA', 'VIN-', 'VIN+'],
                 used={'VCC', 'GND', 'SCL', 'SDA'}, color='#6a1b9a', subtitle='VIN± open until Stage 9')
drop(s, ina['VCC'], Y['3.3V#1'], COL['v33'])
drop(s, ina['GND'], Y['GND#7'], COL['gnd'])
drop(s, ina['SCL'], Y['IO7'], COL['scl'])
drop(s, ina['SDA'], Y['IO6'], COL['sda'])

# ---- ADS1115 ----------------------------------------------------------------
ads = module_top(s, 650, MY, 'ADS1115  (addr 0x48)', ['VDD', 'GND', 'SCL', 'SDA', 'ADDR', 'ALRT', 'A0', 'A1', 'A2', 'A3'],
                 used={'VDD', 'GND', 'SCL', 'SDA', 'ADDR', 'A0', 'A1'}, color='#1a237e')
drop(s, ads['VDD'], Y['3.3V#1'], COL['v33'])
drop(s, ads['GND'], Y['GND#7'], COL['gnd'])
drop(s, ads['SCL'], Y['IO7'], COL['scl'])
drop(s, ads['SDA'], Y['IO6'], COL['sda'])
drop(s, ads['ADDR'], Y['GND#7'], COL['gnd'])

# ---- 10 k pot module (simulated depth) --------------------------------------
pot = module_top(s, 960, MY, '10 kΩ pot', ['VCC', 'OUT', 'GND'], color='#0277bd', subtitle='"depth" dial')
drop(s, pot['VCC'], Y['3.3V#1'], COL['v33'])
drop(s, pot['GND'], Y['GND#7'], COL['gnd'])
s.wire([pot['OUT'], (pot['OUT'][0], LANE_A1), (ads['A1'][0], LANE_A1), ads['A1']], COL['ana'])
s.text(ads['A1'][0] + 40, LANE_A1 - 7, 'pot OUT → A1', size=10.5, fill=COL['ana'], weight='700')

# ---- turbidity sensor + 10k/10k divider -------------------------------------
tb = module_top(s, 1165, MY, 'Turbidity AZDM01', ['VCC', 'GND', 'AOUT'], color='#4e342e', w=150, subtitle='5 V part · out ≤ 4.75 V')
drop(s, tb['VCC'], Y['5V#0'], COL['v5'])
drop(s, tb['GND'], Y['GND#7'], COL['gnd'])
NX = 1105                                       # divider midpoint
s.wire([tb['AOUT'], (tb['AOUT'][0], LANE_A0), (NX + 58, LANE_A0)], COL['v5'])
s.text(tb['AOUT'][0] + 8, LANE_A0 + 34, '≤ 4.75 V', size=9.5, fill=COL['v5'], italic=True)
resistor(s, NX + 58, LANE_A0, NX, LANE_A0, '10 kΩ', label_side=-1)
s.wire([(NX, LANE_A0), (ads['A0'][0], LANE_A0), ads['A0']], COL['ana'], dots=(0,))
s.tag((pot['GND'][0] + NX) / 2, LANE_A0, '→ A0', COL['ana'])
resistor(s, NX, LANE_A0, NX, Y['GND#7'], '10 kΩ', label_side=1)
s.circle(NX, Y['GND#7'], 4.2, fill=COL['gnd'], stroke='#fff', sw=1.2)

# ---- legend + notes -----------------------------------------------------------
legend(s, 34, 600, [('v5', '5 V'), ('v33', '3.3 V'), ('gnd', 'GND'), ('sda', 'I²C SDA'), ('scl', 'I²C SCL'),
                    ('ow', '1-Wire data'), ('ana', 'analog signal')],
       extra=['● dot = joined · crossing without dot = not joined'])
notes(s, 330, 620, [
    '• Module header order varies between makers: always match the PRINTED LABEL, not the position.',
    '• ADS1115 and INA219 on 3.3 V, never 5 V: their I²C pull-ups go to their own VDD.',
    '• Only the turbidity sensor uses 5 V. Its output passes the 10 k/10 k divider before the ADC.',
    '• Turbidity output is inverted: clearer water = higher voltage.',
    '• ADDR tied to GND sets ADS1115 address 0x48; INA219 defaults to 0x40.',
    '• Both breadboard blue (GND) rails must be joined to each other and to a Shrike GND pin.',
], title='Check before powering')
notes(s, 330, 755, ['Gate: I²C scan finds 0x40 + 0x48 · temperature plausible · pot sweeps 0→3.3 V · turbidity drops when muddied.'],
      size=11.5)
save(s, 'stage3_sensors', '.')
