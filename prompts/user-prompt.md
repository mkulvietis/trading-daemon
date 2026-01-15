Please evaluate the current market state using the available trading-mcp server tools get_market_data and get_market_state.
Based on the evaluation, provide trading setups for the next session. Please forcefully use the tools, because market data changes every second and we want to make prediction based on absolutely latest version of data always.

## Tools

- `get_market_data`: Retrieves price data.
- `get_market_state`: Retrieves calculated pivots and state. Ticker @ES, timeframes [1,5,30,120]
- `list_indicators`: Lists available indicators. Ticker @ES, timeframes [1,5,30,120], don't use more than 5 bars back

