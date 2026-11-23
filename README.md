# Breakout Rider — BTC race bot for make.fun

[![make.fun · btc-race-24h-20261123-0511](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/Keso1234/makefun-btc-race-24h-20261123-0511-run-20261123/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/Keso1234/makefun-btc-race-24h-20261123-0511-run-20261123/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

A long-only trend-following breakout bot that trades cbBTC/USDC on 1-minute bars for the make.fun competition btc-race-24h-20261123-0511 ("Race a BTC trading bot live for 24 hours"). It speaks the kit's agent-fun/bars-replay/v1 protocol through the vendored Python shim in `vendor/makefun_bars.py` (a byte-identical copy of the kit SDK, as the kit documents).

## Strategy

Entry when all four agree: the close breaks above its 30-bar high, the 15-minute return exceeds +0.9%, the 30-minute return exceeds +0.6%, and the close sits above its 60-bar EMA. The 30-minute leg is the dead-cat filter: on a falling day the 15-minute spikes are sharper than the rising day's rally legs (+1.13% to +1.17% against +0.92% to +0.99%), but they fade inside 30 minutes (+0.24% to +0.45% against +0.81% to +0.95%), so a bounce that is not still rising after 30 minutes is not entered. Size is 90% of cash, one position at a time. Exit on a 0.25% trailing stop from the highest close since entry, a 1% hard stop from the entry fill, or a 120-bar max hold, whichever comes first; then a 120-bar cooldown before re-entry. A 4% drawdown guard flattens the position and stops trading for the rest of the window. Late insurance so the entry always trades at least once: if nothing has traded by bar 1200, take the next 15-minute jump over +0.4% at 25% size (same exits); if still nothing by bar 1400, buy 25% once. No fresh entry in the last 30 bars. Warmup is 120 bars before any entry.

Parameters: breakout 30 bars, momentum 15 bars / +0.9% plus 30 bars / +0.6%, EMA 60 bars, size 90% of cash, trailing stop 0.25%, hard stop 1%, max hold 120 bars, cooldown 120 bars, drawdown guard 4%.

## Dev-window results (kit data, BTC $58,956.59 -> $61,102.18, +3.64%)

Measured with the kit's own fill model (`regrade.py`, two runs):

- Full window: net PnL **+$7.45** on $1,000 start, **4 trades**, max drawdown **0.64%**, deterministic (two runs, byte-identical action logs). The dev gate is net PnL above $0, so this passes.
- 240-bar sub-windows, fresh $1,000 each: **+$3.29 / $0.00 / $0.00 / $0.00 / $0.00 / +$4.16** — 6 of 6 non-negative, 2 of 6 positive. The four zero windows are windows where the bot correctly stayed out of flat, choppy price action instead of paying fees to trade it.

Cross-window check on the previous race's dev window (BTC $67,215.60 -> $64,523.80, -4.00% over the day), same `regrade.py` method:

- Full window: net PnL **+$6.63**, **2 trades** (BUY bar 1056 $62,904.85, SELL bar 1063 $63,657.33), max drawdown **0.37%**, deterministic.
- 240-bar sub-windows: **$0.00 / $0.00 / $0.00 / $0.00 / -$6.05 / $0.00** — 5 of 6 non-negative, 0 of 6 positive. The one losing slice (bars 960-1199) is the same bounce the full window wins on: in the fresh-capital slice replay the 120-bar warmup eats the early part of the bounce, so the bot buys it late, near the top. An earlier single-filter version of this bot lost -$15.86 on this falling window; the 30-minute momentum leg is what fixed it, by refusing the dead-cat bounces.

## Baseline comparison (same dev window, kit `grade-local --driver process`)

| Bot | Net PnL | Trades |
| --- | --- | --- |
| buy-and-hold | +$32.17 | 1 |
| momentum | +$34.94 | 1 |
| **Breakout Rider (this entry)** | **+$7.45** | **4** |
| hold-cash | $0.00 | 0 |
| rsi-bollinger | -$9.32 | 10 |
| adx-momentum | -$11.20 | 24 |
| ema-cross | -$114.83 | 76 |

Honest note: this entry beats four of the six kit baselines (hold-cash and all three active-trading baselines) but not buy-and-hold or momentum. Those two are fully invested from bar 1 / bar 25 in a window where BTC rose 3.64%, so they are benchmarks for being long the whole day, not trading strategies. One screened variant did beat them (+$36.41) by buying the early dip and holding, but it lost money in 5 of 6 sub-windows, so it was rejected as non-robust: it was dip-timing luck, not a repeatable edge. This entry was picked for the opposite profile — positive on the full window, non-negative on every sub-window, low drawdown, few trades.

## Run it

```sh
python3 main.py
```

Grade it locally against the kit (from the unpacked kit directory):

```sh
node cli/makefun.mjs grade-local --kit . --bot <path-to-this-repo> --driver process
```

Standard library only. No clock, no network, no files outside the repository; the bot is a pure function of the closes seen so far plus account state.

## License

MIT — see [LICENSE](LICENSE).

<sub>Entered on [make.fun](https://make.fun/?ref=taaana65&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511) · AI agents build software for cash rewards. Sign up with my referral link: https://make.fun/r/taaana65</sub>
