"""Evaluation metrics: METEOR, BERTScore, and LLM-as-Judge.

Metric names for use with ``score --metrics``:
  - ``meteor`` — n-gram overlap (local, free)
  - ``bert``   — semantic similarity via DeBERTa (local, free)
  - ``judge``  — LLM-as-Judge 6-dimension scoring (API cost)
"""
