"""BERTScore metric wrapper.

Uses the ``bert_score`` library with the ``microsoft/deberta-xlarge-mnli``
model (recommended for English text) to compute semantic similarity between
generated and reference architecture texts.

BERTScore is particularly appropriate for cloud architecture evaluation
because it captures semantic equivalence — two architectures can describe
the same solution using different wording, and BERTScore handles this
better than n-gram-based metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default model — roberta-large is well-supported across platforms
# and avoids overflow issues that deberta-xlarge-mnli has with long texts
# on Apple Silicon.
_DEFAULT_MODEL = "roberta-large"


@dataclass(frozen=True)
class BERTScoreResult:
    """BERTScore precision, recall, and F1."""

    precision: float
    recall: float
    f1: float


def compute_bert_score(
    generated: str,
    reference: str,
    model_type: str = _DEFAULT_MODEL,
) -> BERTScoreResult:
    """Compute BERTScore between generated and reference texts.

    Args:
        generated: The system-generated architecture text.
        reference: The ground-truth reference architecture text.
        model_type: HuggingFace model for token embeddings.

    Returns:
        A ``BERTScoreResult`` with precision, recall, and F1 (each 0-1).
    """
    from bert_score import score as bert_score_fn

    P, R, F1 = bert_score_fn(
        [generated],
        [reference],
        model_type=model_type,
        verbose=False,
    )

    result = BERTScoreResult(
        precision=P[0].item(),
        recall=R[0].item(),
        f1=F1[0].item(),
    )
    logger.debug("BERTScore: P=%.4f R=%.4f F1=%.4f", result.precision, result.recall, result.f1)
    return result
