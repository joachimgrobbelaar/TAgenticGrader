import argparse
import sys
import logging
from config import BASE_URL, COURSE_ID
from src.auth.session import load_canvas_session
from src.api.client import CanvasAPIClient
from src.navigation.cohort import CohortStudent
from src.cli import run_grading_pipeline, build_parser
import src.cli

# We must set up logging so we can actually see the output!
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout
)

def get_cohort_users(group_id, start_idx, end_idx):
    client = CanvasAPIClient(base_url=BASE_URL, session=load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True))
    users = client.get_group_users(group_id, COURSE_ID)
    users.sort(key=lambda u: (u.get("sortable_name") or u.get("name", "")).lower())
    sliced = users[start_idx - 1: end_idx]
    
    result = []
    for idx, u in enumerate(sliced, start=start_idx):
        result.append(CohortStudent(
            index=idx,
            user_id=u["id"],
            name=u.get("name", ""),
            sortable_name=u.get("sortable_name", u.get("name", ""))
        ))
    return result

def custom_parse(cohort_arg, client=None, course_id=COURSE_ID):
    return get_cohort_users(144686, 109, 113)

src.cli.parse_cohort_students = custom_parse

if __name__ == "__main__":
    parser = build_parser()
    
    print("Running Fri1 109-113 for EXP 05 (316696)...")
    args1 = parser.parse_args(["--assignment", "316696", "--cohort", "Fri1", "--live", "--headed"])
    run_grading_pipeline(args1)

    print("Running Fri1 109-113 for EXP 06 (316843)...")
    args2 = parser.parse_args(["--assignment", "316843", "--cohort", "Fri1", "--live", "--headed"])
    run_grading_pipeline(args2)

