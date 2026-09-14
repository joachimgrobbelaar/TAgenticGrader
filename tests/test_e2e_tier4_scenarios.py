"""
Tier 4: Realistic End-to-End Application Scenarios Test Suite.
Verifies full realistic grading workloads, multi-assignment batch runs, failure recovery,
and multi-attachment evaluations as specified in TEST_INFRA.md.
Requirement: ≥8 tests total.
"""

from datetime import datetime, timezone
import json
import os
import tempfile
import fitz
import pytest
import requests

from tests.harness import (
    CanvasGradingClient,
    CanvasSession,
    EvaluationResult,
    ParsedSubmission,
    RawSubmission,
    SubmissionReceipt,
    evaluate_exp05,
    evaluate_exp06,
    evaluate_lab3_final_code,
    evaluate_lab3_part_a,
    evaluate_lab3_part_b,
    generate_feedback_comment,
    parse_exp05_pdf,
    parse_exp06_pdf,
    parse_lab3_html,
)
from tests.mock_server import (
    ASSIGNMENTS,
    CURRENT_USER,
    FRI2_COHORT_DATA,
    JOACHIM_COHORT,
    REFERENCE_VPYTHON_CODE,
    create_exp05_pdf,
    create_exp06_pdf,
    create_lab3_part_a_html,
    create_lab3_part_b_html,
    create_websnappr_png,
    mock_state,
)


class TestTier4RealWorldScenarios:
    """Tier 4 Realistic End-to-End Scenarios specified in TEST_INFRA.md."""

    def test_scenario_1_exp05_e2e_grade_and_post(self, grading_client: CanvasGradingClient):
        """Scenario 1: Exp05 End-to-End Grade & Post (Valid student report)."""
        aid = 316697
        student = JOACHIM_COHORT[0]
        uid = student["id"]

        # 1. Fetch submission
        sub = grading_client.get_submission(aid, uid)
        assert sub.workflow_state == "submitted"
        assert len(sub.attachments) >= 1

        # 2. Ingest and parse PDF
        pdf_bytes = grading_client.download_attachment(sub.attachments[0]["url"])
        parsed = parse_exp05_pdf(pdf_bytes)
        assert parsed.metadata["student_name"] == "Sbongokuhle Mbizane"

        # 3. Evaluate against 20-point rubric
        res = evaluate_exp05(parsed)
        assert res.score == 20.0

        # 4. Generate feedback comment and post
        receipt = grading_client.post_grade_and_comment(aid, uid, res, "EXP 05 Thermal Expansion")
        assert receipt.status == "graded"
        assert receipt.score == 20.0

        # 5. Remote confirmation
        sub_remote = grading_client.get_submission(aid, uid)
        assert sub_remote.score == 20.0
        assert sub_remote.workflow_state == "graded"

    def test_scenario_2_exp06_e2e_grade_and_post(self, grading_client: CanvasGradingClient):
        """Scenario 2: Exp06 End-to-End Grade & Post (Full report with graph & 3 methods)."""
        aid = 316844
        student = JOACHIM_COHORT[1]
        uid = student["id"]

        sub = grading_client.get_submission(aid, uid)
        pdf_bytes = grading_client.download_attachment(sub.attachments[0]["url"])
        parsed = parse_exp06_pdf(pdf_bytes)

        res = evaluate_exp06(parsed)
        assert res.score == 20.0
        assert res.breakdown["Method 1"] == 1.0
        assert res.breakdown["Method 2"] == 7.0
        assert res.breakdown["Method 3"] == 5.0

        receipt = grading_client.post_grade_and_comment(aid, uid, res, "EXP 06 Thin Spherical Lenses")
        assert receipt.status == "graded"

        sub_remote = grading_client.get_submission(aid, uid)
        assert sub_remote.score == 20.0

    def test_scenario_3_lab3_all_parts_evaluation(self, grading_client: CanvasGradingClient):
        """Scenario 3: Lab 3 Part A, B, and Code Evaluation & Grading across 3 URLs."""
        student = JOACHIM_COHORT[2]
        uid = student["id"]

        # Part A (315832)
        sub_a = grading_client.get_submission(315832, uid)
        boxes_a = parse_lab3_html(sub_a.body_html)
        res_a = evaluate_lab3_part_a(boxes_a)
        receipt_a = grading_client.post_grade_and_comment(315832, uid, res_a, "Lab 3 Part A")
        assert receipt_a.score == 7.0

        # Part B (315833)
        sub_b = grading_client.get_submission(315833, uid)
        boxes_b = parse_lab3_html(sub_b.body_html)
        res_b = evaluate_lab3_part_b(boxes_b)
        receipt_b = grading_client.post_grade_and_comment(315833, uid, res_b, "Lab 3 Part B")
        assert receipt_b.score == 9.0

        # Final Code (315831)
        sub_c = grading_client.get_submission(315831, uid)
        res_c = evaluate_lab3_final_code(REFERENCE_VPYTHON_CODE)
        receipt_c = grading_client.post_grade_and_comment(315831, uid, res_c, "Lab 3 Final Code")
        assert receipt_c.score == 6.0

        total_lab3 = receipt_a.score + receipt_b.score + receipt_c.score
        assert total_lab3 == 22.0

    def test_scenario_4_unsubmitted_and_missing_attachment_recovery(self, grading_client: CanvasGradingClient):
        """Scenario 4: Unsubmitted & Missing Attachment Error Recovery."""
        aid = 316697
        unsubmitted_uid = 150000

        sub = grading_client.get_submission(aid, unsubmitted_uid)
        assert sub.workflow_state == "unsubmitted"
        assert len(sub.attachments) == 0

        # Handle unsubmitted gracefully: assign 0.0 with explanatory feedback note
        zero_res = EvaluationResult(
            score=0.0,
            max_score=20.0,
            breakdown={"Report Submission": 0.0},
            feedback_lines=["No laboratory report submission was received by the deadline."],
        )
        receipt = grading_client.post_grade_and_comment(aid, unsubmitted_uid, zero_res, "EXP 05")
        assert receipt.status == "graded"
        assert receipt.score == 0.0

        sub_updated = grading_client.get_submission(aid, unsubmitted_uid)
        assert sub_updated.score == 0.0

    def test_scenario_5_full_cohort_batch_run_35_students(self, grading_client: CanvasGradingClient, tmp_path):
        """Scenario 5: Full Autonomous Batch Run on Cohort (35 students: Fri2 28-62)."""
        aid = 316697
        batch_manifest = []

        for s in JOACHIM_COHORT:
            uid = s["id"]
            name = s["name"]

            # Autonomous evaluation pipeline
            sub = grading_client.get_submission(aid, uid)
            pdf_bytes = grading_client.download_attachment(sub.attachments[0]["url"])
            parsed = parse_exp05_pdf(pdf_bytes)
            eval_res = evaluate_exp05(parsed)

            receipt = grading_client.post_grade_and_comment(aid, uid, eval_res, "EXP 05")

            batch_manifest.append({
                "index": s["index"],
                "student_id": uid,
                "name": name,
                "score": receipt.score,
                "timestamp": receipt.timestamp,
                "status": "graded",
            })

        assert len(batch_manifest) == 35
        assert batch_manifest[0]["index"] == 28
        assert batch_manifest[-1]["index"] == 62
        assert all(m["score"] >= 15.0 for m in batch_manifest)

        # Save cohort grading summary manifest
        manifest_file = tmp_path / "cohort_fri2_grading_manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(batch_manifest, f, indent=2)
        assert manifest_file.exists()

    def test_scenario_6_broken_session_cookie_refresh_fallback(self, server_url: str):
        """Scenario 6: Broken session / cookie refresh fallback."""
        # 1. Simulate expired/broken session
        broken_session = CanvasSession(cookies=[], csrf_token="stale_token")
        client = CanvasGradingClient(base_url=server_url, session=broken_session)

        # Attempt call -> 401 error
        with pytest.raises(requests.exceptions.HTTPError):
            url = f"{server_url}/api/v1/courses/86326/assignments/316697/submissions/156944"
            resp = requests.put(url, data={"submission[posted_grade]": "20.0"}, headers=client._headers())
            resp.raise_for_status()

        # 2. Recover by refreshing session from persistent store
        refreshed_session = CanvasSession(
            cookies=[
                {"name": "canvas_session", "value": "fresh_session_hash_xyz789"},
                {"name": "_csrf_token", "value": "mock_token"},
            ],
            csrf_token="mock_token",
        )
        client.session = refreshed_session

        # 3. Retry succeeds
        receipt = client.post_grade_and_comment(
            assignment_id=316697,
            user_id=156944,
            result=EvaluationResult(score=19.5, max_score=20.0, breakdown={"Total": 19.5}),
            assignment_name="EXP 05",
        )
        assert receipt.status == "graded"
        assert receipt.score == 19.5

    def test_scenario_7_multi_attachment_pdf_merge_and_evaluation(self, grading_client: CanvasGradingClient):
        """Scenario 7: Multi-attachment PDF merge and evaluation."""
        # Student submitted report across two separate PDF files (Part 1 and Part 2)
        pdf1 = create_exp05_pdf(include_conclusion=False, include_q1=False, include_q2=False, include_q3=False)
        pdf2 = create_exp05_pdf(include_intro=False, include_objective=False, include_brass=False, include_ss=False)

        # Merge PDFs via PyMuPDF
        doc_merged = fitz.open()
        doc1 = fitz.open(stream=pdf1, filetype="pdf")
        doc2 = fitz.open(stream=pdf2, filetype="pdf")
        doc_merged.insert_pdf(doc1)
        doc_merged.insert_pdf(doc2)
        merged_bytes = doc_merged.tobytes()
        doc1.close()
        doc2.close()
        doc_merged.close()

        # Parse merged PDF
        parsed = parse_exp05_pdf(merged_bytes)
        eval_res = evaluate_exp05(parsed)
        assert eval_res.score == 20.0
        assert eval_res.breakdown["Brass Table"] == 3.5
        assert eval_res.breakdown["Conclusion"] == 2.0

    def test_scenario_8_headless_execution_across_all_5_target_urls(self, grading_client: CanvasGradingClient):
        """Scenario 8: Headless execution across all 5 target assignment URLs."""
        target_aids = [316697, 316844, 315832, 315833, 315831]
        student = JOACHIM_COHORT[3]
        uid = student["id"]

        results = {}
        for aid in target_aids:
            sub = grading_client.get_submission(aid, uid)
            assert sub.assignment_id == aid

            if aid == 316697:
                pdf_bytes = grading_client.download_attachment(sub.attachments[0]["url"])
                res = evaluate_exp05(parse_exp05_pdf(pdf_bytes))
            elif aid == 316844:
                pdf_bytes = grading_client.download_attachment(sub.attachments[0]["url"])
                res = evaluate_exp06(parse_exp06_pdf(pdf_bytes))
            elif aid == 315832:
                res = evaluate_lab3_part_a(parse_lab3_html(sub.body_html))
            elif aid == 315833:
                res = evaluate_lab3_part_b(parse_lab3_html(sub.body_html))
            elif aid == 315831:
                res = evaluate_lab3_final_code(REFERENCE_VPYTHON_CODE)

            receipt = grading_client.post_grade_and_comment(aid, uid, res, f"Assignment {aid}")
            assert receipt.status == "graded"
            results[aid] = receipt.score

        assert len(results) == 5
        assert results[316697] == 20.0
        assert results[316844] == 20.0
        assert results[315832] == 7.0
        assert results[315833] == 9.0
        assert results[315831] == 6.0
