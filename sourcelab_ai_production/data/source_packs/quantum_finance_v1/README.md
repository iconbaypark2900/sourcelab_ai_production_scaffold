# Quantum Finance and Portfolio Optimization

## Purpose

Source pack for quantum and hybrid portfolio optimization, QAOA/QUBO formulation, risk modeling, and finance backtesting workflows.

## Domain

`quantum_finance`

## Topics

- quantum portfolio optimization
- QAOA
- VQE
- HRP
- Markowitz optimization
- QUBO
- risk models
- backtesting

## Example Lessons

- `quantum hybrid portfolio optimizer`
- `QAOA portfolio selection`
- `risk-aware portfolio backtesting`
- `QUBO formulation for asset selection`

## Starter Sources

- `quantum_finance_portfolio_001` — Hybrid Portfolio Optimization Workflow
- `quantum_finance_risk_002` — Risk and Validation for Finance Models

## Validation

From the SourceLab project root:

```bash
sourcelab source-pack doctor quantum_finance_v1
sourcelab evals run --pack quantum_finance_v1
sourcelab lesson create --topic "quantum hybrid portfolio optimizer" --source-pack quantum_finance_v1 --difficulty 2
```

## Notes

This pack was scaffolded from the user's recurring project and research themes. Replace or extend starter sources with stronger project notes, official docs, papers, or internal architecture records over time.
