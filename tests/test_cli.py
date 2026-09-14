"""Tests for CLI entrypoint and main runner."""

import json
import subprocess
import sys
from pathlib import Path
import pytest

from src.cli import (
    ALL_ASSIGNMENT_IDS,
    ASSIGNMENT_KEY_MAP,
    build_parser,
    parse_cohort_students,
    resolve_evaluator,
    run_grading_pipeline,
)
from src.navigation.cohort import get_allocated_cohort
from tests.harness import CanvasGradingClient


class TestCLIParserAndResolution:
    """Test suite for CLI argument parser and assignment/cohort resolution."""

    def test_parser_defaults(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.assignment == "exp05"
        assert args.cohort == "Fri2 28-62"
        assert args.dry_run is False
        assert args.live is False
        assert args.headless is False
        assert args.headed is False
        assert args.no_browser is False
        assert args.use_ui is False
        assert args.single_student is None
        assert args.output_dir == "artifacts"
        assert args.course_id == 86326

    def test_parser_custom_flags(self):
        parser = build_parser()
        args = parser.parse_args([
            "--assignment", "exp06",
            "--cohort", "Fri2 28-35",
            "--dry-run",
            "--headless",
            "--use-ui",
            "--single-student", "156944",
            "--output-dir", "custom_artifacts",
        ])
        assert args.assignment == "exp06"
        assert args.cohort == "Fri2 28-35"
        assert args.dry_run is True
        assert args.headless is True
        assert args.use_ui is True
        assert args.single_student == 156944
        assert args.output_dir == "custom_artifacts"

    def test_resolve_evaluator_all_types(self):
        for aid in ALL_ASSIGNMENT_IDS:
            evaluator, extract_type = resolve_evaluator(aid)
            assert evaluator is not None
            assert extract_type is not None

    def test_parse_cohort_students_range(self):
        cohort = parse_cohort_students("Fri2 28-32")
        assert len(cohort) == 5
        assert cohort[0].index == 28
        assert cohort[-1].index == 32

    def test_parse_cohort_students_full(self):
        cohort = parse_cohort_students("Fri2 28-62")
        assert len(cohort) == 35
        assert cohort[0].index == 28
        assert cohort[-1].index == 62


class TestCLIRunnerExecution:
    """Test execution of CLI pipeline against mock server harness."""

    def test_run_agent_help_flag(self):
        res = subprocess.run(
            [sys.executable, "run_agent.py", "--help"],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0
        assert "Autonomous Canvas SpeedGrader grading agent" in res.stdout

    def test_run_pipeline_single_student_dry_run(self, server_url: str, tmp_path: Path):
        parser = build_parser()
        out_dir = tmp_path / "artifacts"
        args = parser.parse_args([
            "--assignment", "exp05",
            "--single-student", "156944",
            "--dry-run",
            "--no-browser",
            "--base-url", server_url,
            "--output-dir", str(out_dir),
        ])

        rc = run_grading_pipeline(args)
        assert rc == 0

        # Check ledger CSV
        csv_file = out_dir / "grading_ledger.csv"
        assert csv_file.exists()
        csv_content = csv_file.read_text(encoding="utf-8")
        assert "156944" in csv_content
        assert "dry_run" in csv_content

        # Check summary MD
        summary_file = out_dir / "grading_summary.md"
        assert summary_file.exists()
        summary_content = summary_file.read_text(encoding="utf-8")
        assert "Autonomous Grading Run Summary" in summary_content
        assert "Sbongokuhle Mbizane" in summary_content

    def test_run_pipeline_all_assignments_dry_run(self, server_url: str, tmp_path: Path):
        parser = build_parser()
        out_dir = tmp_path / "artifacts_all"
        args = parser.parse_args([
            "--assignment", "all",
            "--single-student", "156944",
            "--dry-run",
            "--no-browser",
            "--base-url", server_url,
            "--output-dir", str(out_dir),
        ])

        rc = run_grading_pipeline(args)
        assert rc == 0

        # Check ledger has all 5 assignments
        json_file = out_dir / "grading_ledger.json"
        assert json_file.exists()
        with open(json_file, encoding="utf-8") as f:
            records = json.load(f)
        assert len(records) == 5
        aids = {r["assignment_id"] for r in records}
        assert aids == set(ALL_ASSIGNMENT_IDS)
