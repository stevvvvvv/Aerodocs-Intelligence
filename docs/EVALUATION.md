# Évaluation

## Protocole

`backend/eval/questions.jsonl` contient 20 questions annotées sur le corpus de démonstration :

- **13 questions avec réponse** : valeur attendue, famille documentaire et section source. Une question est en français ; une autre (q01) porte sur un point où le manuel et le bulletin de service se contredisent.
- **7 questions sans réponse** dans le corpus. Parmi elles, une question piège (q18) : elle demande un couple de serrage pour l'écrou d'axe de roue, alors que le corpus ne donne qu'un couple pour l'écrou de presse-étoupe. Un système qui se contente de « trouver un chiffre proche » répondrait 90 N.m.

Les métriques sont mesurées maillon par maillon, pour savoir quoi améliorer :

| Métrique | Ce qu'elle mesure |
|---|---|
| `retrieval_hit@k`, `retrieval_mrr` | Le bon passage est-il dans les k premiers, et à quel rang ? |
| `answer_accuracy` | La réponse contient la valeur attendue (avec son unité) |
| `citation_accuracy` | Parmi les réponses données, au moins une citation pointe vers la bonne section |
| `refusal_recall` | Part des questions sans réponse correctement refusées |
| `refusal_precision` | Part des refus qui étaient justifiés |
| `contradiction_recall` | La contradiction attendue est signalée |

```bash
make eval                                    # dans Docker
python -m scripts.evaluate --out ../docs/eval_results.md   # en local, depuis backend/
```

## Résultats mesurés

Configuration **hors-ligne** : embeddings `hashing` (lexicaux, sans modèle) et mode `extractive` (sans LLM). Détail complet dans [eval_results_hashing_extractive.md](eval_results_hashing_extractive.md).

| Métrique | Valeur |
|---|---|
| retrieval_hit@6 | 1.00 |
| retrieval_mrr | 0.91 |
| answer_accuracy | 0.92 (12/13) |
| citation_accuracy | 1.00 |
| refusal_recall | 1.00 (7/7, y compris la question piège) |
| refusal_precision | 0.88 |
| contradiction_recall | 1.00 |

Le seul échec est q13, la question en français : des embeddings lexicaux ne relient pas « joints dynamiques » à « dynamic seals ». C'est la baseline que doit battre `multilingual-e5-small`.

### Avec multilingual-e5-small

| Métrique | hashing | e5-small |
|---|---|---|
| retrieval_hit@6 | 1.00 | 1.00 |
| retrieval_mrr | 0.91 | **1.00** |
| answer_accuracy | 0.92 | 0.92 |
| refusal_recall | 1.00 | 1.00 |
| latence médiane | 6 ms | 210 ms |

Deux enseignements :

1. **La récupération est parfaite, y compris en français.** Pour q13, e5 place le bon passage en tête. La réponse échoue quand même, mais à l'étape suivante : le mode `extractive` compare les mots de la question à ceux des phrases sources, et aucun mot français ne correspond à l'anglais. Le maillon qui casse n'est donc plus la recherche, c'est l'absence de LLM. Une vraie génération devrait corriger ce cas.
2. **La similarité seule ne suffit pas à décider d'un refus.** La question piège q18 (couple de l'écrou d'axe de roue) obtient une similarité de 0,868, plus élevée que la question légitime q10 (0,852). Aucun seuil ne sépare les deux populations. Le seuil de 0,80 sert de premier filtre : il bloque 4 questions sur 7 sans appeler le LLM. Les 3 autres sont refusées à l'étape suivante, faute de support dans les sources. C'est la justification concrète des trois niveaux de refus.

| Configuration | answer_accuracy | refusal_recall | Statut |
|---|---|---|---|
| hashing + extractive | 0.92 | 1.00 | mesuré |
| e5-small + extractive | 0.92 | 1.00 | mesuré (MRR 1.00, seuil 0.80 conservé) |
| e5-small + LLM (Claude / Mistral via Ollama) | [à mesurer] | [à mesurer] | |
| EAR Continuing Airworthiness (données réelles) | [à mesurer] | [à mesurer] | jeu de questions à construire |

## Ce que ces chiffres ne prouvent pas

- **Le corpus est petit (4 documents, 36 passages) et a été écrit en même temps que les questions.** Les scores élevés valident surtout que chaque mécanisme fonctionne de bout en bout. Ils ne disent rien de la qualité sur une documentation réelle de 1 000 pages, où les passages qui se ressemblent sont bien plus nombreux.
- **20 questions ne suffisent pas pour une statistique.** Une question de plus ou de moins fait varier les métriques de 5 à 8 points.
- **L'exactitude est vérifiée par une simple recherche de chaîne** (la valeur attendue figure-t-elle dans la réponse ?). Avec un LLM, il faudra ajouter une vérification de fidélité : chaque phrase est-elle réellement soutenue par le passage qu'elle cite ?

Prochaine étape : un jeu d'environ 50 questions sur les Easy Access Rules for Continuing Airworthiness (Part-M, Part-145, Part-CAMO), annotées avec la référence réglementaire attendue, plus des questions qui portent sur la différence entre les révisions de juillet 2024 et de septembre 2025.
