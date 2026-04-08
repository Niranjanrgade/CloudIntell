"""METEOR score metric wrapper.

METEOR (Metric for Evaluation of Translation with Explicit Ordering) is an
n-gram-based metric that accounts for stemming and synonym matching, making
it more robust than simple BLEU for evaluating natural-language text.

For cloud architecture evaluation, METEOR complements BERTScore by
providing an n-gram coverage perspective: does the generated text contain
the same key terms and phrases as the reference?
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_NLTK_INITIALIZED = False


def _ensure_nltk_data() -> None:
    """Download required NLTK data on first use."""
    global _NLTK_INITIALIZED
    if _NLTK_INITIALIZED:
        return

    import nltk

    for resource in ["punkt_tab", "wordnet"]:
        try:
            nltk.data.find(f"corpora/{resource}" if resource == "wordnet" else f"tokenizers/{resource}")
        except LookupError:
            nltk.download(resource, quiet=True)

    _NLTK_INITIALIZED = True


def compute_meteor(generated: str, reference: str) -> float:
    """Compute METEOR score between generated and reference texts.

    Args:
        generated: The system-generated architecture text.
        reference: The ground-truth reference architecture text.

    Returns:
        METEOR score as a float in [0, 1].
    """
    _ensure_nltk_data()

    from nltk.tokenize import word_tokenize
    from nltk.translate.meteor_score import meteor_score

    reference_tokens = word_tokenize(reference)
    generated_tokens = word_tokenize(generated)

    score = meteor_score([reference_tokens], generated_tokens)
    logger.debug("METEOR: %.4f", score)
    return float(score)
