Analyze the ES futures market using the `get_market_state` tool.

I'm looking for the **highest probability trade setup** for a 5-30 minute hold.

Key questions to answer:
1. **TRENDLINES ARE YOUR PRIMARY SIGNAL.** Check all trendlines in the response. Any trendline with `proximity: "at"` or `"near"` is an active level — price is testing it RIGHT NOW. Support trendlines near price = potential long entries. Resistance trendlines near price = potential short entries or exit zones. Trendlines with higher `touch_count` and `score` carry more weight.
2. What is the current trend on multiple timeframes?
3. Where are the nearest significant support and resistance levels (pivots, VWAP)?
4. Does the trendline signal align with other confluence? (VWAP, EMAs, pivots, patterns)
5. What would be a logical stop loss and target?
6. Think like professional intraday trader and make a decision based on rationality.

7. **Provide a confidence score (1-10) based on technical confluence.**

**Guidelines:**
- **Trendline proximity is the highest-weight factor** — a trade at a tested trendline (proximity "at" or "near") with 3+ touches gets +3 confidence points automatically
- Only recommend a trade if there's strong confluence (2-3+ factors aligning)
- If no clear setup exists right now, tell me what to watch for
- I prefer to trade WITH the trend, but will take counter-trend trades at key trendlines with strong rejection
- I'm patient - I'd rather wait for a good entry than chase

Call `get_market_state`.
