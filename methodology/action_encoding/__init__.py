"""Ingestion of the authors' precomputed 13-symbol action encodings
(arXiv 2604.02547, Zenodo 19351830) for the 13-agent population.

Deliberately outside `swebench_adapter`: the adapter is fenced from
`enriched_encodings_all.csv` (spec §0, it carries `is_failed`); this package
is the one consumer of that file and reads nothing else from their `data/`.
"""
