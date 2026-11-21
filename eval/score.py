"""Scoring for the held-out eval. Shared and implemented; lane B builds everything around it.

A case's ground truth comes from a real note pulled out of the vault: its folder and outgoing links.
We score the system's NoteDraft against that.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class CaseScore:
    case_id: str
    folder_correct: bool
    link_precision: float
    link_recall: float
    link_f1: float
    verify_ok: bool


def _norm(s: str) -> str:
    return s.strip().lower()


def score_case(case_id: str, truth_folder: str, truth_links: list[str],
               pred_folder: str, pred_links: list[str], verify_ok: bool) -> CaseScore:
    t = {_norm(x) for x in truth_links}
    p = {_norm(x) for x in pred_links}
    tp = len(t & p)
    precision = tp / len(p) if p else (1.0 if not t else 0.0)
    recall = tp / len(t) if t else 1.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return CaseScore(case_id, _norm(truth_folder) == _norm(pred_folder), precision, recall, f1, verify_ok)


def summarize(scores: list[CaseScore]) -> dict:
    n = len(scores) or 1
    return {
        "n": len(scores),
        "folder_accuracy": sum(s.folder_correct for s in scores) / n,
        "link_precision": sum(s.link_precision for s in scores) / n,
        "link_recall": sum(s.link_recall for s in scores) / n,
        "link_f1": sum(s.link_f1 for s in scores) / n,
        "verify_pass_rate": sum(s.verify_ok for s in scores) / n,
    }


def to_rows(scores: list[CaseScore]) -> list[dict]:
    return [asdict(s) for s in scores]
