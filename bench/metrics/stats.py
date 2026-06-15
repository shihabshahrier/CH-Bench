"""Significance + uncertainty for benchmark metrics — pure stdlib, no numpy.

Two tools the harness leans on so a headline like "+7.9 recall" is defensible
rather than noise:

  - `bootstrap_ci`  — a percentile confidence interval for the *mean* of a
    per-question metric array, by resampling questions with replacement. Answers
    "how tight is this system's score?".
  - `paired_permutation` — a two-sided p-value for the mean *paired* difference
    between two systems scored on the same questions (aligned by qid). Answers
    "is system A really above system B, or could the gap be chance?". Paired
    because both systems answer the identical question set, so the per-question
    difference cancels question-difficulty variance.

Self-test:  python3 -m bench.metrics.stats
"""

from __future__ import annotations

import random


def bootstrap_ci(
    values: list[float], *, iters: int = 1000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float]:
    """Percentile bootstrap CI of the mean.

    Resamples `values` with replacement `iters` times, takes each resample's
    mean, and returns the (alpha/2, 1-alpha/2) percentiles of those means.
    Returns (mean, mean) for a degenerate (empty / single) array so callers
    never special-case it.
    """
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    if n == 1:
        return (values[0], values[0])
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(iters):
        s = 0.0
        for _ in range(n):
            s += values[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo_idx = int((alpha / 2) * iters)
    hi_idx = min(int((1 - alpha / 2) * iters), iters - 1)
    return (means[lo_idx], means[hi_idx])


def paired_permutation(
    a: list[float], b: list[float], *, iters: int = 10000, seed: int = 0
) -> float:
    """Two-sided p-value for the mean paired difference mean(a_i - b_i).

    `a` and `b` must be aligned (same question order). Under the null the two
    systems are exchangeable per question, so we randomly flip the sign of each
    paired difference and count how often the permuted |mean| reaches the
    observed |mean|. Add-one smoothing keeps p strictly in (0, 1].
    Returns 1.0 when there is nothing to test (no pairs, or zero observed gap).
    """
    if len(a) != len(b):
        raise ValueError(f"paired arrays differ in length: {len(a)} vs {len(b)}")
    diffs = [x - y for x, y in zip(a, b)]
    n = len(diffs)
    if n == 0:
        return 1.0
    observed = abs(sum(diffs) / n)
    if observed == 0.0:
        return 1.0
    rng = random.Random(seed)
    hits = 0
    for _ in range(iters):
        s = 0.0
        for d in diffs:
            s += d if rng.random() < 0.5 else -d
        if abs(s / n) >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (iters + 1)


def _self_test() -> int:
    # bootstrap CI of a known-constant array is the constant itself.
    lo, hi = bootstrap_ci([0.5] * 50, iters=200, seed=1)
    assert abs(lo - 0.5) < 1e-9 and abs(hi - 0.5) < 1e-9, (lo, hi)

    # CI of a spread array brackets the true mean (0.5) and is non-degenerate.
    vals = [i / 100 for i in range(101)]  # 0.00..1.00, mean 0.5
    lo, hi = bootstrap_ci(vals, iters=2000, seed=1)
    assert lo < 0.5 < hi, (lo, hi)
    assert hi - lo < 0.25, (lo, hi)
    print(f"bootstrap_ci  spread→({lo:.3f}, {hi:.3f})  ok")

    # Identical arrays → no difference → p == 1.0.
    same = [0.3, 0.7, 0.5, 0.9, 0.1] * 10
    p_same = paired_permutation(same, list(same), iters=2000, seed=1)
    assert p_same == 1.0, p_same
    print(f"paired_permutation  identical→p={p_same:.3f}  ok")

    # Clearly shifted arrays → significant.
    hi_arr = [0.9] * 40
    lo_arr = [0.1] * 40
    p_shift = paired_permutation(hi_arr, lo_arr, iters=2000, seed=1)
    assert p_shift < 0.05, p_shift
    print(f"paired_permutation  shifted→p={p_shift:.4f}  ok")

    # Noise vs noise around the same mean → not significant.
    rng = random.Random(7)
    na = [rng.random() for _ in range(60)]
    nb = [rng.random() for _ in range(60)]
    p_noise = paired_permutation(na, nb, iters=2000, seed=2)
    assert p_noise > 0.05, p_noise
    print(f"paired_permutation  noise→p={p_noise:.3f}  ok")

    print("stats self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
