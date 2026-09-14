import sys, logging
from config import BASE_URL, COURSE_ID
from src.auth.session import load_canvas_session
from src.api.client import CanvasAPIClient
from src.navigation.cohort import CohortStudent
from src.cli import run_grading_pipeline, build_parser
import src.cli

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)

# The 19 typed-PDF students (Fri2 1-31 minus the 12 handwritten)
HANDWRITTEN_IDS = {164236, 190927, 190482, 190965, 195568, 189908, 104588, 191463, 190267, 195580, 193718, 192479}

def get_typed_users():
    client = CanvasAPIClient(base_url=BASE_URL, session=load_canvas_session(base_url=BASE_URL, validate=False, fallback_to_mock=True))
    users = client.get_group_users(144689, COURSE_ID)
    users.sort(key=lambda u: (u.get("sortable_name") or u.get("name", "")).lower())
    sliced = users[0:31]  # indices 1-31
    result = []
    for idx, u in enumerate(sliced, start=1):
        if u["id"] not in HANDWRITTEN_IDS:
            result.append(CohortStudent(index=idx, user_id=u["id"], name=u.get("name", ""), sortable_name=u.get("sortable_name", u.get("name", ""))))
    return result

def custom_parse(cohort_arg, client=None, course_id=COURSE_ID):
    return get_typed_users()

src.cli.parse_cohort_students = custom_parse

if __name__ == "__main__":
    parser = build_parser()
    print(f"Regrading {len(get_typed_users())} typed students for EXP 05...")
    args = parser.parse_args(["--assignment", "316697", "--cohort", "Fri2", "--live", "--headed"])
    run_grading_pipeline(args)
    print(f"Regrading {len(get_typed_users())} typed students for EXP 06...")
    args = parser.parse_args(["--assignment", "316844", "--cohort", "Fri2", "--live", "--headed"])
    run_grading_pipeline(args)
