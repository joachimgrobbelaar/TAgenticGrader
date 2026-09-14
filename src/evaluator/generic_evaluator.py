"""
Generic Evaluator using a Memo PDF.
Parses the memo and dynamically grades the submission based on keyword/concept overlap.
For advanced usage, this can be extended to use an LLM API.
"""
from typing import Any, Dict, List
import fitz  # PyMuPDF
import re
from collections import Counter
import math

from src.evaluator.base import BaseEvaluator, EvaluationResult, ParsedSubmission

def extract_text_from_pdf(pdf_path: str) -> str:
    try:
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc)
        return text
    except Exception as e:
        return ""

def get_words(text: str) -> List[str]:
    return re.findall(r'\w+', text.lower())

def get_cosine_similarity(vec1: Counter, vec2: Counter) -> float:
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])
    sum1 = sum([vec1[x]**2 for x in vec1.keys()])
    sum2 = sum([vec2[x]**2 for x in vec2.keys()])
    denominator = math.sqrt(sum1) * math.sqrt(sum2)
    if not denominator:
        return 0.0
    return float(numerator) / denominator

class GenericMemoEvaluator(BaseEvaluator):
    def __init__(self, memo_pdf_path: str, target_max_score: float = 100.0):
        super().__init__(target_max_score=target_max_score)
        self.memo_text = extract_text_from_pdf(memo_pdf_path)
        self.memo_words = Counter(get_words(self.memo_text))

    def evaluate(self, submission: Any) -> EvaluationResult:
        sub_text = ""
        if isinstance(submission, str):
            sub_text = submission
        elif hasattr(submission, "full_text"):
            sub_text = submission.full_text
        elif isinstance(submission, dict):
            sub_text = " ".join(str(v) for v in submission.values())
            
        if not sub_text.strip():
            return EvaluationResult(
                score=0.0,
                max_score=self.target_max_score,
                breakdown={"Submission": 0.0},
                feedback_lines=["No readable submission found."]
            )

        sub_words = Counter(get_words(sub_text))
        
        # Very basic heuristic: cosine similarity scaled to max score
        similarity = get_cosine_similarity(self.memo_words, sub_words)
        
        # Curve the similarity so it's not brutally low. 
        # A 40% keyword overlap might be an excellent submission.
        curved_ratio = min(1.0, similarity * 2.5) 
        
        score = round(curved_ratio * self.target_max_score, 2)
        
        breakdown = {
            "Content Match": score
        }
        
        feedback = [f"Graded against generic memo. Content similarity index: {similarity:.2f}"]
        
        return EvaluationResult(
            score=score,
            max_score=self.target_max_score,
            breakdown=breakdown,
            feedback_lines=feedback
        )
