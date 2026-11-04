# Evaluation plan — no invented scores

No 9.7/10 score is claimed by default. Scores require repeatable evidence.

## Benchmark design
Create at least 100 reviewed natural-language questions covering aggregation, grouping, ranking, date filters, joins, ambiguous questions, unsupported requests and adversarial inputs. Store gold SQL, expected output, difficulty and failure category.

## Metrics
- Execution accuracy (primary): returned result matches expected result.
- Exact SQL match (secondary).
- Safe rejection rate and false rejection rate.
- Clarification accuracy for ambiguous questions.
- p50/p95 latency, rows returned, error rate.
- Human ratings for correctness, usefulness and groundedness.

## Ablations
Compare deterministic baseline, single-shot LLM SQL, planner+generator, planner+generator+critic, and full system with semantic layer/clarification. Record dataset version, model/provider, prompt version and run date.

## Security matrix
Test DML/DDL, multiple statements, comments, obfuscated keywords, unknown tables/columns, prompt injection, oversized results, expensive queries and cross-tenant access after tenancy is implemented.

## Scorecard template
Functional correctness: TBD
Execution accuracy: TBD
Safe rejection / false rejection: TBD
Test coverage: TBD
p50/p95 latency: TBD
Deployment smoke tests: TBD
User study: TBD
