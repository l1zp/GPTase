"""Tests for Kemp batch extraction helpers."""

import pytest

from gptase.utils.kemp_batch import _wait_for_process
from gptase.utils.kemp_batch import BatchJob
from gptase.utils.kemp_batch import build_plan_command
from gptase.utils.kemp_batch import discover_batch_jobs
from gptase.utils.kemp_batch import format_jobs
from gptase.utils.kemp_batch import run_batch_jobs


class TestDiscoverBatchJobs:
    """Tests for paper folder discovery."""

    def test_prefers_full_markdown_over_pdf(self, tmp_path):
        papers_dir = tmp_path / "papers"
        output_root = tmp_path / "output" / "kemp"
        paper_dir = papers_dir / "paper_a"
        paper_dir.mkdir(parents=True)
        (paper_dir / "full.md").write_text("body", encoding="utf-8")
        (paper_dir / "abc_origin.pdf").write_bytes(b"%PDF-1.4")

        jobs = discover_batch_jobs(papers_dir, output_root)

        assert jobs == [
            BatchJob(
                name="paper_a",
                input_path=paper_dir / "full.md",
                output_path=output_root / "paper_a",
            )
        ]

    def test_falls_back_to_origin_pdf_when_markdown_missing(self, tmp_path):
        papers_dir = tmp_path / "papers"
        output_root = tmp_path / "output" / "kemp"
        paper_dir = papers_dir / "paper_b"
        paper_dir.mkdir(parents=True)
        (paper_dir / "abc_origin.pdf").write_bytes(b"%PDF-1.4")

        jobs = discover_batch_jobs(papers_dir, output_root)

        assert jobs == [
            BatchJob(
                name="paper_b",
                input_path=paper_dir / "abc_origin.pdf",
                output_path=output_root / "paper_b",
            )
        ]

    def test_skips_directories_without_supported_inputs(self, tmp_path):
        papers_dir = tmp_path / "papers"
        output_root = tmp_path / "output" / "kemp"
        (papers_dir / "paper_c").mkdir(parents=True)

        jobs = discover_batch_jobs(papers_dir, output_root)

        assert jobs == []

    def test_raises_for_missing_papers_directory(self, tmp_path):
        missing_dir = tmp_path / "missing"
        output_root = tmp_path / "output" / "kemp"

        with pytest.raises(FileNotFoundError,
                           match=f"Papers directory not found: {missing_dir}"):
            discover_batch_jobs(missing_dir, output_root)


class TestBuildPlanCommand:
    """Tests for CLI command generation."""

    def test_builds_expected_python_command_in_current_env(self, tmp_path):
        job = BatchJob(
            name="paper_a",
            input_path=tmp_path / "papers" / "paper_a" / "full.md",
            output_path=tmp_path / "output" / "kemp" / "paper_a",
        )

        command = build_plan_command(job)

        assert command[1:5] == ["-m", "gptase.main", "plan", "run"]
        assert command[-6:] == [
            "-p",
            "enzyme_extraction_pipeline",
            "-i",
            str(job.input_path),
            "-o",
            str(job.output_path),
        ]

    def test_builds_expected_conda_command_when_requested(self, tmp_path):
        job = BatchJob(
            name="paper_a",
            input_path=tmp_path / "papers" / "paper_a" / "full.md",
            output_path=tmp_path / "output" / "kemp" / "paper_a",
        )

        command = build_plan_command(job, conda_env="llm")

        assert command == [
            "conda",
            "run",
            "-n",
            "llm",
            "python",
            "-m",
            "gptase.main",
            "plan",
            "run",
            "-p",
            "enzyme_extraction_pipeline",
            "-i",
            str(job.input_path),
            "-o",
            str(job.output_path),
        ]


class TestRunBatchJobs:
    """Tests for batch execution flow."""

    def test_dry_run_does_not_execute_subprocess(self, monkeypatch, tmp_path):
        called = {"count": 0}
        job = BatchJob(
            name="paper_a",
            input_path=tmp_path / "papers" / "paper_a" / "full.md",
            output_path=tmp_path / "output" / "kemp" / "paper_a",
        )

        def fake_wait(command, result_file, **kwargs):
            called["count"] += 1
            return 0

        monkeypatch.setattr("gptase.utils.kemp_batch._wait_for_process", fake_wait)

        exit_code = run_batch_jobs([job], dry_run=True)

        assert exit_code == 0
        assert called["count"] == 0

    def test_returns_error_and_continues_when_a_job_fails(self, monkeypatch, tmp_path):
        calls = []
        jobs = [
            BatchJob(
                name="paper_a",
                input_path=tmp_path / "papers" / "paper_a" / "full.md",
                output_path=tmp_path / "output" / "kemp" / "paper_a",
            ),
            BatchJob(
                name="paper_b",
                input_path=tmp_path / "papers" / "paper_b" / "full.md",
                output_path=tmp_path / "output" / "kemp" / "paper_b",
            ),
        ]

        def fake_wait(command, result_file):
            calls.append((command, result_file))
            if len(calls) == 1:
                return 1
            return 0

        monkeypatch.setattr("gptase.utils.kemp_batch._wait_for_process", fake_wait)

        exit_code = run_batch_jobs(jobs, fail_fast=False)

        assert exit_code == 1
        assert len(calls) == 2
        assert jobs[0].output_path.exists()
        assert jobs[1].output_path.exists()

    def test_fail_fast_stops_after_first_failure(self, monkeypatch, tmp_path):
        calls = []
        jobs = [
            BatchJob(
                name="paper_a",
                input_path=tmp_path / "papers" / "paper_a" / "full.md",
                output_path=tmp_path / "output" / "kemp" / "paper_a",
            ),
            BatchJob(
                name="paper_b",
                input_path=tmp_path / "papers" / "paper_b" / "full.md",
                output_path=tmp_path / "output" / "kemp" / "paper_b",
            ),
        ]

        def fake_wait(command, result_file):
            calls.append((command, result_file))
            return 1

        monkeypatch.setattr("gptase.utils.kemp_batch._wait_for_process", fake_wait)

        exit_code = run_batch_jobs(jobs, fail_fast=True)

        assert exit_code == 1
        assert len(calls) == 1
        assert jobs[0].output_path.exists()
        assert not jobs[1].output_path.exists()

    def test_skips_existing_result_file(self, monkeypatch, tmp_path):
        calls = []
        job = BatchJob(
            name="paper_a",
            input_path=tmp_path / "papers" / "paper_a" / "full.md",
            output_path=tmp_path / "output" / "kemp" / "paper_a",
        )
        job.output_path.mkdir(parents=True)
        job.result_file.write_text("done", encoding="utf-8")

        def fake_wait(command, result_file):
            calls.append((command, result_file))
            return 0

        monkeypatch.setattr("gptase.utils.kemp_batch._wait_for_process", fake_wait)

        exit_code = run_batch_jobs([job], skip_existing=True)

        assert exit_code == 0
        assert calls == []


class TestWaitForProcess:
    """Tests for subprocess hang protection."""

    def test_returns_zero_when_result_file_exists_and_process_hangs(
            self, monkeypatch, tmp_path):
        result_file = tmp_path / "output" / "result.json"
        state = {"poll_count": 0, "terminated": False, "killed": False}

        class FakeProcess:
            """Minimal Popen stub."""

            def poll(self):
                state["poll_count"] += 1
                if state["poll_count"] == 1:
                    return None
                if state["poll_count"] == 2:
                    result_file.parent.mkdir(parents=True, exist_ok=True)
                    result_file.write_text("done", encoding="utf-8")
                    return None
                if state["terminated"]:
                    return 0
                return None

            def terminate(self):
                state["terminated"] = True

            def wait(self, timeout):
                return 0

            def kill(self):
                state["killed"] = True

        monotonic_values = iter([0.0, 0.0, 21.0])

        monkeypatch.setattr("gptase.utils.kemp_batch.subprocess.Popen",
                            lambda command: FakeProcess())
        monkeypatch.setattr("gptase.utils.kemp_batch.time.sleep", lambda _: None)
        monkeypatch.setattr("gptase.utils.kemp_batch.time.monotonic",
                            lambda: next(monotonic_values))

        return_code = _wait_for_process(["python", "-m", "gptase.main"],
                                        result_file,
                                        success_grace_period=20,
                                        poll_interval=0.0)

        assert return_code == 0
        assert state["terminated"] is True
        assert state["killed"] is False


class TestFormatJobs:
    """Tests for dry-run formatting."""

    def test_formats_jobs_as_expected(self, tmp_path):
        jobs = [
            BatchJob(
                name="paper_a",
                input_path=tmp_path / "papers" / "paper_a" / "full.md",
                output_path=tmp_path / "output" / "kemp" / "paper_a",
            )
        ]

        result = format_jobs(jobs)

        assert result == (f"paper_a: {tmp_path / 'papers' / 'paper_a' / 'full.md'} -> "
                          f"{tmp_path / 'output' / 'kemp' / 'paper_a'}")
