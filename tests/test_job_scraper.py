import os
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("GEMINI_API_KEY", "test_key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from core.job_scraper import parse_jobsdb_html, parse_indeed_html, parse_ctjobs_html

JOBSDB_HTML = """
<html><body>
<article data-search-sol-meta='{"jobId":"123"}'>
  <a href="/job/123">
    <h2 data-automation="job-card-title">Senior Python Developer</h2>
  </a>
  <span class="FYwKg">HSBC Hong Kong</span>
  <span class="y44TY">2026-05-01</span>
</article>
</body></html>
"""

INDEED_HTML = """
<html><body>
<div class="job_seen_beacon" data-jk="abc">
  <h2 class="jobTitle"><a href="/viewjob?jk=abc"><span>Backend Engineer</span></a></h2>
  <span class="companyName">Standard Chartered</span>
  <span class="date">Posted 2 days ago</span>
</div>
</body></html>
"""

CTJOBS_HTML = """
<html><body>
<div class="job-item">
  <h3><a href="/job/456" class="job-title">Finance Analyst</a></h3>
  <span class="company-name">KPMG Hong Kong</span>
  <span class="date-posted">2026-05-03</span>
</div>
</body></html>
"""


def test_parse_jobsdb_returns_jobs():
    jobs = parse_jobsdb_html(JOBSDB_HTML)
    assert len(jobs) >= 1
    job = jobs[0]
    assert "title" in job
    assert "company" in job
    assert "url" in job
    assert "date_posted" in job
    assert job["source"] == "jobsdb"


def test_parse_jobsdb_empty_html():
    jobs = parse_jobsdb_html("<html><body></body></html>")
    assert jobs == []


def test_parse_indeed_returns_jobs():
    jobs = parse_indeed_html(INDEED_HTML)
    assert len(jobs) >= 1
    job = jobs[0]
    assert "title" in job
    assert "company" in job
    assert "url" in job
    assert job["source"] == "indeed"


def test_parse_indeed_empty_html():
    jobs = parse_indeed_html("<html><body></body></html>")
    assert jobs == []


def test_parse_ctjobs_returns_jobs():
    jobs = parse_ctjobs_html(CTJOBS_HTML)
    assert len(jobs) >= 1
    job = jobs[0]
    assert "title" in job
    assert "company" in job
    assert "url" in job
    assert job["source"] == "ctjobs"


def test_parse_ctjobs_empty_html():
    jobs = parse_ctjobs_html("<html><body></body></html>")
    assert jobs == []
