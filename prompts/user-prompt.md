Analyze the ES futures market using the `get_market_data` tool.

I'm looking for the **highest probability trade setup** for a 5-30 minute hold.

Key questions to answer:
1. What is the current trend on multiple timeframes?
2. Where are the nearest significant support and resistance levels?
3. Is price at or approaching a high-probability entry zone?
4. What confluence factors support a trade? (VWAP, EMAs, pivots, patterns, volume, other)
5. What would be a logical stop loss and target?
6. Think like professional intraday trader and make a decision based on rationality.

**Guidelines:**
- Only recommend a trade if there's strong confluence (2-3+ factors aligning)
- If no clear setup exists right now, tell me what to watch for
- I prefer to trade WITH the trend, but will take counter-trend trades at key levels with strong rejection
- I'm patient - I'd rather wait for a good entry than chase

Call `get_market_data` with ticker '@ES' and timeframes [1, 5, 30, 120].
