"""AgentCore Runtime entrypoints for the Retail Dynamic Pricing agents.

Each module in this package wraps a Strands Agent with BedrockAgentCoreApp,
exposing POST /invocations and GET /ping endpoints for AgentCore Runtime
deployment.

Entrypoints:
- competitive_intelligence_runtime: Competitive Intelligence Agent
- demand_forecasting_runtime: Demand Forecasting Agent
- market_intelligence_runtime: Market Intelligence Agent
- strategy_synthesis_runtime: Strategy Synthesis Agent
- implementation_monitoring_runtime: Implementation Monitoring Agent
"""
