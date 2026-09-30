from pictorial import *
s = Sheet(1120, 660, 'Stage 1 — toolchain and first blink', 'One cable, no wiring. Status: PASSED 25 Sep 2026.')
BX = 800
L, R = shrike(s, BX, 120, used=set())
lp = laptop(s, 80, 250)
s.wire([lp, (560, lp[1]), (560, 88), (BX + 95, 88), (BX + 95, 108)], '#607d8b', sw=6)
s.tag(560, 170, 'USB-C data cable', '#455a64')
# onboard MCU LED: on the board itself, between the headers (not a header pin)
led = (BX + 95, 262)
s.circle(*led, 8, fill='#ffeb3b', stroke='#f57f17', sw=2)
s.circle(*led, 14, fill='none', stroke='#fbc02d', sw=1.5)
s.wire([(led[0] - 16, led[1]), (700, led[1]), (700, 330)], '#f9a825', sw=1.6, dash='4 3')
notes(s, 600, 350, ['onboard MCU LED = GPIO4', '(on the board, not a header pin)', 'Nothing to wire.'], size=11)
notes(s, 40, 480, [
    '1. Plug the Shrike Lite into the laptop. A charge-only cable will not work: use a data cable.',
    '2. First flash only: if no port appears, hold BOOT while plugging in.',
    '   After that, uploads reset it automatically.',
    '3. Board: Vicharak Shrike-Lite  (FQBN rp2040:rp2040:vicharak_shrike-lite).',
    '4. Upload firmware/stage1_blink. Serial prints "alive" once a second.',
], title='Steps')
notes(s, 40, 620, ['Gate: the onboard LED blinks and the serial heartbeat arrives.'], size=12)
save(s, 'stage1_blink', '.')
