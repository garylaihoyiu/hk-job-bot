import asyncio
import logging
import random
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
]

MAX_JOBS_PER_QUERY = 20


def _headers() -> dict:
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
    }


# ---------------------------------------------------------------------------
# JobsDB HK
# ---------------------------------------------------------------------------

async def scrape_jobsdb(query: str) -> list[dict]:
    url = f"https://hk.jobsdb.com/jobs?q={query.replace(' ', '+')}&l=Hong+Kong"
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_headers(), follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        await asyncio.sleep(random.uniform(2, 5))
        return parse_jobsdb_html(resp.text)
    except Exception as e:
        logger.warning(f"JobsDB scrape failed for '{query}': {e}")
        return []


def parse_jobsdb_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    jobs = []
    # JobsDB uses data-search-sol-meta or article cards
    cards = soup.select("article[data-search-sol-meta], [data-automation='job-card']")
    if not cards:
        # Fallback: any card-like container with a job title
        cards = soup.select(".job-card, [data-job-id]")
    for card in cards[:MAX_JOBS_PER_QUERY]:
        try:
            title_el = card.select_one(
                "[data-automation='job-card-title'], h1, h2, h3"
            )
            company_el = card.select_one(
                "[data-automation='job-card-company-name'], .FYwKg, [class*='company']"
            )
            date_el = card.select_one(
                "[data-automation='job-card-date'], .y44TY, [class*='date']"
            )
            link_el = card.select_one("a[href]")

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            date_posted = date_el.get_text(strip=True) if date_el else ""
            href = link_el["href"] if link_el else ""
            url = f"https://hk.jobsdb.com{href}" if href.startswith("/") else href

            if title and company and url:
                jobs.append({
                    "title": title, "company": company,
                    "date_posted": date_posted, "url": url, "source": "jobsdb",
                })
        except Exception:
            continue
    return jobs


# ---------------------------------------------------------------------------
# Indeed HK
# ---------------------------------------------------------------------------

async def scrape_indeed(query: str) -> list[dict]:
    url = f"https://hk.indeed.com/jobs?q={query.replace(' ', '+')}&l=Hong+Kong"
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_headers(), follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        await asyncio.sleep(random.uniform(2, 5))
        return parse_indeed_html(resp.text)
    except Exception as e:
        logger.warning(f"Indeed scrape failed for '{query}': {e}")
        return []


def parse_indeed_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    jobs = []
    cards = soup.select(".job_seen_beacon, [data-jk]")
    for card in cards[:MAX_JOBS_PER_QUERY]:
        try:
            title_el = card.select_one(
                ".jobTitle span, [data-testid='job-title'], h2 a span"
            )
            company_el = card.select_one(
                ".companyName, [data-testid='company-name'], [class*='company']"
            )
            date_el = card.select_one(
                ".date, [data-testid='myJobsStateDate'], [class*='date']"
            )
            link_el = card.select_one("a[href]")

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            date_posted = date_el.get_text(strip=True) if date_el else ""
            href = link_el["href"] if link_el else ""
            url = f"https://hk.indeed.com{href}" if href.startswith("/") else href

            if title and company and url:
                jobs.append({
                    "title": title, "company": company,
                    "date_posted": date_posted, "url": url, "source": "indeed",
                })
        except Exception:
            continue
    return jobs


# ---------------------------------------------------------------------------
# CTJobs HK
# ---------------------------------------------------------------------------

async def scrape_ctjobs(query: str) -> list[dict]:
    url = f"https://www.ctjobs.hk/en/job-search/?keyword={query.replace(' ', '+')}"
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_headers(), follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        await asyncio.sleep(random.uniform(2, 5))
        return parse_ctjobs_html(resp.text)
    except Exception as e:
        logger.warning(f"CTJobs scrape failed for '{query}': {e}")
        return []


def parse_ctjobs_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    jobs = []
    cards = soup.select(".job-item, .listing-item, [class*='job-card']")
    for card in cards[:MAX_JOBS_PER_QUERY]:
        try:
            title_el = card.select_one(".job-title, h2 a, h3 a, [class*='title'] a")
            company_el = card.select_one(
                ".company-name, .employer-name, [class*='company']"
            )
            date_el = card.select_one(".date-posted, .post-date, [class*='date']")
            link_el = card.select_one("a[href]")

            title = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            date_posted = date_el.get_text(strip=True) if date_el else ""
            href = link_el["href"] if link_el else ""
            url = href if href.startswith("http") else f"https://www.ctjobs.hk{href}"

            if title and company and url:
                jobs.append({
                    "title": title, "company": company,
                    "date_posted": date_posted, "url": url, "source": "ctjobs",
                })
        except Exception:
            continue
    return jobs
