Vault Mines - pure Mines math validation

Board:
- 25 tiles
- 1 to 20 mines
- no reels
- no paytable
- win_type = other

Target RTP: 96.7%
Max win: x5000

For M mines and n successfully revealed safe tiles:

    P(survive n) = C(25-M, n) / C(25, n)

The theoretical RTP-adjusted cashout multiplier is:

    multiplier = RTP / P(survive n)

The multiplier is capped at x5000.

This first implementation intentionally excludes Keys and Shield. Those features should only be added after pure-Mines books and SDK format checks validate correctly.
