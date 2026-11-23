"""Breakout Rider for btc-race-24h-20261123-0511: long-only trend following on 1-minute cbBTC/USDC bars.

Entry needs all four to agree: the close breaks above its 30-bar high, the
15-minute return exceeds +0.9%, the 30-minute return exceeds +0.6%, and the
close sits above its 60-bar EMA. The second momentum window is the
dead-cat filter: on a falling day the 15-minute spikes are sharper than the
rising day's rally legs (+1.13% to +1.17% against +0.92% to +0.99%), but
they fade inside 30 minutes (+0.24% to +0.45% against +0.81% to +0.95%),
so a bounce that is not still rising after 30 minutes is not entered.
Size is 90% of cash, one position at a time. Exit on a 0.25% trailing stop
from the highest close since entry, a 1% hard stop from the entry fill, or a
120-bar max hold, whichever comes first; then a 120-bar cooldown. A 4%
drawdown guard flattens the position and stops trading for the window.
Late insurance so the entry always trades at least once: if nothing has
traded by bar 1200, take the next 15-minute jump over +0.4% at 25% size (same
exits); if still nothing by bar 1400, buy 25% once. No fresh entry in the
last 30 bars. Warmup is 120 bars before any entry.

Pure function of the closes seen so far plus account state: standard library
only, no clock, no network, no files. Speaks agent-fun/bars-replay/v1
through the kit's vendored Python shim in vendor/makefun_bars.py.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
WARMUP = 120
BREAKOUT_BARS = 30
MOMENTUM_BARS = 15
MOMENTUM_BPS = 90          # 15-minute return must exceed +0.9%
MOMENTUM2_BARS = 30
MOMENTUM2_BPS = 60         # 30-minute return must exceed +0.6% (dead-cat filter)
EMA_BARS = 60
SIZE_BPS = 9000            # 90% of cash per entry
TRAIL_BPS = 25             # 0.25% trailing stop from the highest close since entry
HARD_STOP_BPS = 100        # 1% hard stop from the entry fill price
MAX_HOLD_BARS = 120
COOLDOWN_BARS = 120
DRAWNDOWN_GUARD_BPS = 400  # flatten and stop if equity falls 4% below its running peak
LATE_BAR = 1200
LAST_BAR = 1400
NO_ENTRY_FROM = 1410
LATE_MOMENTUM_BPS = 40     # +0.4% over 15 minutes for the late-insurance entry
LATE_SIZE_BPS = 2500       # 25% of cash for late-insurance entries
MAX_SLIPPAGE_BPS = 300
MIN_NOTIONAL = 1_000_000   # 1 USDC, in quote units


class Rider:
    """The strategy state: bar history plus the open position's bookkeeping."""

    def __init__(self):
        self.closes = []
        self.highs = []
        self.ema = None
        self.peak_equity = None
        self.entry_price = 0
        self.entry_seq = -1
        self.peak_close = 0
        self.cooldown_until = -1
        self.stopped = False
        self.traded = False

    def on_batch(self, state, batch):
        bar = state.latest.get(SYMBOL)
        if bar is None:
            # No bar for the symbol yet in this run: nothing to decide on,
            # and nothing to record, so the history stays aligned with seq.
            return []
        close = int(bar["c"])
        self.closes.append(close)
        self.highs.append(int(bar["h"]))
        if self.ema is None:
            self.ema = float(close)
        else:
            self.ema += (2.0 / (EMA_BARS + 1)) * (close - self.ema)

        holding = state.positions.get(SYMBOL)
        held_qty = holding.qty if holding is not None else 0

        # Fills from the previous batch's orders land in this batch.
        for fill in batch.get("fills", []):
            if fill.get("symbol") != SYMBOL or fill.get("status") != "filled":
                continue
            if fill["side"] == "buy":
                self.entry_price = int(fill["price"])
                self.entry_seq = state.seq
                self.peak_close = self.entry_price
                self.traded = True
            elif held_qty == 0:
                self.entry_price = 0
                self.entry_seq = -1
                self.peak_close = 0

        if self.peak_equity is None:
            self.peak_equity = state.equity
        elif state.equity > self.peak_equity:
            self.peak_equity = state.equity

        if state.warming_up or state.seq < WARMUP:
            return []

        # Drawdown guard: flatten and stop trading for the rest of the window.
        if not self.stopped and state.equity * 10000 < self.peak_equity * (10000 - DRAWNDOWN_GUARD_BPS):
            self.stopped = True
            if held_qty > 0:
                self.cooldown_until = 1 << 60
                return [self._sell(held_qty)]
            return []

        if held_qty > 0:
            if close > self.peak_close:
                self.peak_close = close
            trail_hit = close * 10000 <= self.peak_close * (10000 - TRAIL_BPS)
            hard_hit = close * 10000 <= self.entry_price * (10000 - HARD_STOP_BPS)
            held_too_long = state.seq - self.entry_seq >= MAX_HOLD_BARS
            if trail_hit or hard_hit or held_too_long:
                self.cooldown_until = state.seq + COOLDOWN_BARS
                return [self._sell(held_qty)]
            return []

        if self.stopped or state.seq < self.cooldown_until or state.seq >= NO_ENTRY_FROM:
            return []

        seq = state.seq
        # Index the history by how many bars were actually seen, not by
        # seq: a batch with no bar for the symbol must not shift the
        # momentum/breakout windows or raise an IndexError on a gap.
        n = len(self.closes)
        momentum_ok = (
            n > MOMENTUM_BARS
            and close * 10000 > self.closes[n - 1 - MOMENTUM_BARS] * (10000 + MOMENTUM_BPS)
        )
        momentum2_ok = (
            n > MOMENTUM2_BARS
            and close * 10000 > self.closes[n - 1 - MOMENTUM2_BARS] * (10000 + MOMENTUM2_BPS)
        )
        if n > BREAKOUT_BARS and momentum_ok and momentum2_ok and close > self.ema:
            breakout_high = max(self.highs[n - 1 - BREAKOUT_BARS:n - 1])
            if close > breakout_high:
                return self._buy(state, SIZE_BPS)

        # Late insurance: guarantee at least one trade in the window.
        if not self.traded:
            late_momentum_ok = (
                n > MOMENTUM_BARS
                and close * 10000
                > self.closes[n - 1 - MOMENTUM_BARS] * (10000 + LATE_MOMENTUM_BPS)
            )
            if seq >= LATE_BAR and late_momentum_ok:
                return self._buy(state, LATE_SIZE_BPS)
            if seq >= LAST_BAR:
                return self._buy(state, LATE_SIZE_BPS)
        return []

    def _buy(self, state, size_bps):
        notional = state.cash * size_bps // 10000
        room = state.weight_room(SYMBOL)
        if room < notional:
            notional = room
        if notional < MIN_NOTIONAL:
            return []
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": notional,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }]

    @staticmethod
    def _sell(qty):
        return {
            "side": "sell",
            "symbol": SYMBOL,
            "qty": qty,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        }


def on_batch(state, batch):
    return _RIDER.on_batch(state, batch)


_RIDER = Rider()

makefun_bars.run(on_batch)
