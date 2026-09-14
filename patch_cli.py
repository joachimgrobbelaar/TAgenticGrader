import sys

with open("src/cli.py", "r") as f:
    content = f.read()

import_str = "from config import (\n"
generic_eval_import = "from src.evaluator.generic_evaluator import GenericMemoEvaluator\n"

if "GenericMemoEvaluator" not in content:
    content = content.replace("from config import (", generic_eval_import + "from config import (")

# Update build_parser
parser_addition = """
    parser.add_argument(
        "--memo-pdf",
        help="Path to a PDF memorandum to use for generic rubric evaluation.",
    )
    
    parser.add_argument(
        "--max-score",
        type=float,
        default=100.0,
        help="Maximum score for the generic evaluation if using --memo-pdf (default: 100.0).",
    )
"""
if "--memo-pdf" not in content:
    content = content.replace('help="Autonomous Canvas SpeedGrader grading agent', parser_addition + '\n    help="Autonomous Canvas SpeedGrader grading agent')
    # wait that is risky. Let's just do a simple replacement for the parser
    
