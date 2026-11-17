# Résultats d'évaluation

Configuration : embeddings `hashing`, génération `extractive`, top_k=6.
Jeu : 13 questions avec réponse, 7 sans réponse (corpus démo fictif).

| Métrique | Valeur |
|---|---|
| retrieval_hit@6 | 1.00 |
| retrieval_mrr | 0.91 |
| answer_accuracy | 0.92 |
| citation_accuracy | 1.00 |
| refusal_recall | 1.00 |
| refusal_precision | 0.88 |
| false_refusals | 1 |
| contradiction_recall | 1 |
| latency_p50_ms | 6.00 |

| id | langue | attendu | statut | rang | correct | citation | sim. max |
|---|---|---|---|---|---|---|---|
| q01 | en | réponse | answered | 1 | True | True | 0.4801 |
| q02 | en | réponse | answered | 1 | True | True | 0.5162 |
| q03 | en | réponse | answered | 1 | True | True | 0.5691 |
| q04 | en | réponse | answered | 1 | True | True | 0.5286 |
| q05 | en | réponse | answered | 1 | True | True | 0.5301 |
| q06 | en | réponse | answered | 1 | True | True | 0.5697 |
| q07 | en | réponse | answered | 2 | True | True | 0.1703 |
| q08 | en | réponse | answered | 1 | True | True | 0.3346 |
| q09 | en | réponse | answered | 1 | True | True | 0.4066 |
| q10 | en | réponse | answered | 1 | True | True | 0.3335 |
| q11 | en | réponse | answered | 1 | True | True | 0.5388 |
| q12 | en | réponse | answered | 1 | True | True | 0.4924 |
| q13 | fr | réponse | refused (no_relevant_sources) | 3 | False | False | 0.1068 |
| q14 | en | refus | refused (llm_abstained) |  |  |  | 0.1322 |
| q15 | en | refus | refused (no_relevant_sources) |  |  |  | 0.0624 |
| q16 | en | refus | refused (llm_abstained) |  |  |  | 0.181 |
| q17 | en | refus | refused (no_relevant_sources) |  |  |  | 0.114 |
| q18 | en | refus | refused (llm_abstained) |  |  |  | 0.3056 |
| q19 | en | refus | refused (llm_abstained) |  |  |  | 0.1958 |
| q20 | en | refus | refused (no_relevant_sources) |  |  |  | 0.0741 |
