---
source_id: trading_research_meta_labeling_002
title: Meta-Labeling and Outcome Verification
domain: trading_research
trust_tier: C
version: 1.0
created_at: 2026-06-25T04:57:48+00:00
---

# Meta-Labeling and Outcome Verification

## Summary

Meta-labeling workflows estimate whether a candidate trade is worth taking, while settlement verification connects predictions to resolved outcomes.

## Key Claims

- Kalshi and similar event markets need resolved outcome rows for reliable calibration.
- Triple-barrier labeling can define outcomes using profit, loss, and time boundaries.
- A model should learn when to skip weak candidates.
- Resolved outcome rows are required for reliable calibration.

## Use Cases

- crypto strategy testing
- event market verification
- trade selection models

## Kalshi Settlement Workflow

Kalshi is a CFTC-regulated event exchange that offers markets on economic, climate, health, and political outcomes with standard binary contract settlements. Each Kalshi market has a defined resolution source (e.g., a specific government agency report), a resolution date, and settlement instructions that map possible outcomes to contract payoff values. Settlement verification for Kalshi markets follows a deterministic workflow: a verification agent fetches the resolution source document at the scheduled resolution time, extracts the relevant value or category using a predefined parsing rule, maps the extracted value to the market's outcome definitions, and submits the settlement transaction to the exchange's settlement contract.

The verification agent logs each step including the source URL, the raw fetched content, the parsed value, the mapped outcome, and the settlement transaction hash. For backtesting, historical Kalshi market data must include a verified settlement record for every market in the sample. Markets that were not resolved at the time of dataset creation — or that were resolved using self-reported outcomes without an authoritative source — should be excluded from backtest datasets to prevent look-ahead or verification bias. The settlement verification pipeline also produces a daily audit report that lists all markets settled, their resolution sources, any verification discrepancies encountered, and the subset of markets that required manual intervention due to ambiguous source data.

## Source Quality Note

This is a starter SourceLab seed document derived from recurring project context. Strengthen it by adding official references, project architecture notes, implementation evidence, experiment logs, or paper citations.
