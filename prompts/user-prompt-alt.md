Analyze the ES futures market using the `get_market_state` tool.

I'm looking for an **ALTERNATIVE trade setup** for a 5-30 minute hold. 
This strategy should focus on **mean reversion** or **counter-trend** opportunities at key levels, or perhaps a **scalp** on lower timeframes if the main trend is overextended.

Key questions to answer:
1. **TRENDLINES ARE YOUR PRIMARY SIGNAL.** Check all trendlines. A resistance trendline with `proximity: "at"` or `"near"` where price shows rejection = potential short. A support trendline breaking down = potential short continuation. Focus on trendlines with high `touch_count` and `score`.
2. Is the current trend overextended? (RSI, Bollinger Bands, distance from VWAP)
3. Are there any immediate rejection candles at key trendlines or pivot levels?
4. What is the **contrarian** view?

**Provide a confidence score (1-10) based on technical confluence.**

**Guidelines:**
- **Trendline proximity is the highest-weight factor** — a reversal at a tested trendline (proximity "at" or "near") with 3+ touches gets +3 confidence points automatically
- Be more aggressive than the main trend-following strategy if conditions warrant a reversal.
- Use tight stops.
- If no alternative setup exists, state "No valid alternative setup". 

Call `get_market_state`.
