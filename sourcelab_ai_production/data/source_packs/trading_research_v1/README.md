# Trading Research and Market Strategy Validation

## Purpose

Source pack for event markets, equities factors, crypto meta-labeling, options/forex strategy testing, and settlement verification workflows.

## Domain

`trading_research`

## Topics

- event markets
- Kalshi
- Polymarket
- crypto meta-labeling
- triple-barrier labeling
- equities factors
- options strategies
- forex regimes
- settlement verification

## Example Lessons

- `factor ranking equity strategy`
- `event market settlement verification`
- `crypto triple-barrier meta-labeling`
- `options flow validation workflow`

## Starter Sources

- `trading_research_validation_001` — Trading Strategy Validation Gates
- `trading_research_meta_labeling_002` — Meta-Labeling and Outcome Verification

## Validation

From the SourceLab project root:

```bash
sourcelab source-pack doctor trading_research_v1
sourcelab evals run --pack trading_research_v1
sourcelab lesson create --topic "factor ranking equity strategy" --source-pack trading_research_v1 --difficulty 2
```

## Notes

This pack was scaffolded from the user's recurring project and research themes. Replace or extend starter sources with stronger project notes, official docs, papers, or internal architecture records over time.
