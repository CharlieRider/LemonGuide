#!/usr/bin/env python3
"""
download_missing_pdfs.py

One-stop: scan a folder of study .md notes, find missing PDFs, and download them.

Phase 1 — automated (silent, no interaction). Strategies are chosen per publisher
instead of blindly hitting every endpoint, so we only call things that can plausibly
work and avoid bot-like direct scrapes of captcha/Cloudflare-walled hosts:
  - PMC papers        : Europe PMC (OA-gated) -> NCBI OA package -> Unpaywall
  - MDPI papers       : Unpaywall (repository copies first) -> Europe PMC if mirrored
  - Other OA / generic: Unpaywall (repo first) -> session scrape of the article page
  - Paywalled hosts   : Unpaywall only (green-OA repo copy); else flagged paywalled
All requests go through one rate-limited session that honours 429/Retry-After.

Phase 2 — browser fallback (interactive). For anything still missing, opens ONE visible
Chromium (Playwright). MDPI and other sites that just download a PDF in a real browser
are captured automatically with no interaction. For a captcha (PMC reCAPTCHA), the paper
opens in its own tab: solve it and it saves instantly, or CLOSE THE TAB to skip. By
default each captcha tab waits until you act (no timer; --browser-timeout N to auto-skip).
Clearing one PMC captcha unblocks the rest of the PMC queue via the shared cookie; while a
captcha sits unsolved the server is NOT polled (avoids tripping its bot defenses).
Plain webpages (generic sources where the page itself is the content, e.g. extension
factsheets / blogs / nursery pages) have no PDF to download, so once the page has loaded
and settled they are PRINTED to PDF via the browser and run through the same rename/save
path (status 'printed'). Disable with --no-print-pages; tune the wait with --print-settle.

Failure memory: each note's pdf_status records the outcome (downloaded / needs-browser /
paywalled / no-source). Re-runs skip the automated APIs for needs-browser/paywalled
notes (they won't succeed via API) unless --retry-automated. Disk is the source of
truth, so Ctrl+C mid-captcha and re-run any time — it only retries what's still missing.

Usage:
    pip install requests playwright            # one-time
    playwright install chromium                # one-time (downloads the browser)
    python download_missing_pdfs.py <folder>            # full run
    python download_missing_pdfs.py <folder> --no-browser
    python download_missing_pdfs.py <folder> --include-paywalled
    python download_missing_pdfs.py <folder> --retry-automated -v
"""

import argparse
import base64
import io
import logging
import random
import re
import sys
import tarfile
import time
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

# Force UTF-8 on Windows consoles that default to cp1252
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    sys.exit("requests is not installed. Run: pip install requests")

log = logging.getLogger("pdfdl")

EMAIL = "charlierider816@gmail.com"  # used for Unpaywall API (required by their ToS)

# ---- status vocabulary (written back into each note's pdf_status) ----------
ST_DOWNLOADED = "downloaded"
ST_PRINTED = "printed"        # a plain webpage rendered to PDF (no real article PDF existed)
ST_NEEDS_BROWSER = "needs-browser"
ST_PAYWALLED = "paywalled"
ST_NO_SOURCE = "no-source"

# Kinds whose source IS the webpage itself (extension factsheets, blogs, nursery pages),
# so when no real PDF can be fetched we just print the rendered page. Article hosts
# (pmc/mdpi/oa_publisher/paywall) are excluded — there we want the actual article PDF.
PRINTABLE_KINDS = {"generic"}
# Statuses whose automated path is exhausted — skipped on re-run unless --retry-automated.
SKIP_AUTOMATED = {ST_NEEDS_BROWSER, ST_PAYWALLED, ST_NO_SOURCE}

# ---- host classification ---------------------------------------------------
PAYWALL_HOSTS = (
    "link.springer.com", "onlinelibrary.wiley.com",
    "sciencedirect.com", "journals.biologists.com",
)
OA_PUBLISHER_HOSTS = (
    "frontiersin.org", "biomedcentral.com", "plos.org", "peerj.com", "hindawi.com",
)

EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

PDF_ACCEPT = "application/pdf,*/*;q=0.8"


# ---------------------------------------------------------------------------
# Polite, rate-limited HTTP (one shared session)
# ---------------------------------------------------------------------------

class RateLimiter:
    """Per-host minimum interval + jitter, with cool-off after repeated 429/503s."""

    def __init__(self, min_interval: float = 2.0, jitter: float = 0.5):
        self.min_interval = min_interval
        self.jitter = jitter
        self._last: dict[str, float] = {}
        self._429: dict[str, int] = {}
        self._cooling: set[str] = set()

    @staticmethod
    def host(url: str) -> str:
        return urlparse(url).netloc.lower()

    def is_cooling(self, url: str) -> bool:
        return self.host(url) in self._cooling

    def wait(self, url: str) -> None:
        h = self.host(url)
        last = self._last.get(h)
        if last is not None:
            gap = self.min_interval - (time.time() - last)
            if gap > 0:
                time.sleep(gap + random.uniform(0, self.jitter))
        self._last[h] = time.time()

    def note_throttle(self, url: str) -> None:
        h = self.host(url)
        self._429[h] = self._429.get(h, 0) + 1
        if self._429[h] >= 2 and h not in self._cooling:
            self._cooling.add(h)
            log.warning("  %s is throttling us — cooling off (skipping it for the rest of this run)", h)


SESSION = requests.Session()
SESSION.headers.update(BROWSER_HEADERS)
RATE = RateLimiter()


def polite_get(url: str, *, timeout: int = 40, **kw):
    """Rate-limited GET via the shared session. Returns a Response, or None on
    error / cool-off / throttle (caller treats None as a failed attempt)."""
    if RATE.is_cooling(url):
        log.debug("skip (cooling): %s", url)
        return None
    RATE.wait(url)
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True, **kw)
    except Exception:
        log.debug("GET error: %s", url, exc_info=True)
        return None
    log.debug("GET %s -> %s (%s bytes)", url, r.status_code, len(r.content))
    if r.status_code in (429, 503):
        ra = r.headers.get("Retry-After", "")
        delay = min(int(ra), 30) if ra.isdigit() else 5
        log.info("  HTTP %s from %s — backing off %ss", r.status_code, RATE.host(url), delay)
        time.sleep(delay)
        RATE.note_throttle(url)
        return None
    return r


# ---------------------------------------------------------------------------
# Frontmatter parsing / status write-back
# ---------------------------------------------------------------------------

def parse_frontmatter(path: Path) -> dict:
    """Extract fields from YAML-style frontmatter between --- delimiters."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ": " in line:
            key, _, val = line.partition(": ")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm


def update_pdf_status(path: Path, new_status: str) -> None:
    """Replace the pdf_status line in a .md file."""
    text = path.read_text(encoding="utf-8")
    updated = re.sub(r"^(pdf_status: ).*$", rf"\g<1>{new_status}", text, flags=re.MULTILINE)
    if updated != text:
        path.write_text(updated, encoding="utf-8")


def set_status(note: dict, status: str) -> None:
    """Persist a status to the note and keep the in-memory record in sync."""
    if note.get("status") != status:
        update_pdf_status(note["md_path"], status)
        note["status"] = status


def clean_doi(doi: str) -> str:
    return (doi or "").replace("https://doi.org/", "").replace("http://doi.org/", "").strip()


def is_valid_pdf(data: bytes) -> bool:
    return len(data) > 10_000 and data[:4] == b"%PDF"


def infer_pdf_name_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    basename = unquote(Path(parsed.path).name or "")
    if basename.lower().endswith(".pdf"):
        return basename
    query = parse_qs(parsed.query)
    for key in ("file", "filename", "download", "url"):
        values = query.get(key) or []
        for value in values:
            candidate = unquote(Path(value).name)
            if candidate.lower().endswith(".pdf"):
                return candidate
    return ""


def update_frontmatter_field(path: Path, key: str, value: str) -> None:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^(---\r?\n)(.*?)(\r?\n---)", text, re.DOTALL)
    if not m:
        path.write_text(f"---\n{key}: {value}\n---\n\n" + text, encoding="utf-8")
        return
    frontmatter = m.group(2)
    if re.search(rf"(?m)^{re.escape(key)}\s*:", frontmatter):
        frontmatter = re.sub(rf"(?m)^{re.escape(key)}\s*:.*$", f"{key}: {value}", frontmatter)
    else:
        frontmatter = frontmatter.rstrip() + f"\n{key}: {value}"
    new_text = m.group(1) + frontmatter + m.group(3) + text[m.end():]
    path.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Automated strategies
# ---------------------------------------------------------------------------

def europepmc_lookup(pmcid_hint: str, doi: str):
    """Return (pmcid, is_open_access) from the Europe PMC search API."""
    doi_clean = clean_doi(doi)
    if pmcid_hint:
        query = f"PMCID:{pmcid_hint}"
    elif doi_clean:
        query = f"DOI:{doi_clean}"
    else:
        return ("", False)
    r = polite_get(f"{EUROPEPMC}/search?query={query}&format=json&resultType=lite", timeout=15)
    if not r or r.status_code != 200:
        return (pmcid_hint, False)
    try:
        for res in r.json().get("resultList", {}).get("result", []):
            pmcid = res.get("pmcid") or pmcid_hint
            if pmcid:
                return (pmcid, res.get("isOpenAccess") == "Y")
    except Exception:
        log.debug("europepmc json parse failed", exc_info=True)
    return (pmcid_hint, False)


def europepmc_download(pmcid: str, dest: Path) -> bool:
    """Fetch the rendered full-text PDF directly from Europe PMC."""
    if not pmcid:
        return False
    r = polite_get(f"{EUROPEPMC}/{pmcid}/fullTextPDF",
                   headers={**BROWSER_HEADERS, "Accept": PDF_ACCEPT})
    if r and r.status_code == 200 and is_valid_pdf(r.content):
        dest.write_bytes(r.content)
        return True
    return False


def ncbi_oa_download(pmcid: str, dest: Path) -> bool:
    """NCBI OA web service: direct PDF link, else extract the PDF from the .tar.gz."""
    if not pmcid:
        return False
    r = polite_get(f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}", timeout=20)
    if not r or r.status_code != 200:
        return False
    try:
        links = ET.fromstring(r.content).findall(".//record/link")
    except Exception:
        log.debug("ncbi oa xml parse failed", exc_info=True)
        return False
    pdf_link = next((l for l in links if l.get("format") == "pdf"), None)
    tgz_link = next((l for l in links if l.get("format") == "tgz"), None)

    def to_https(href: str) -> str:
        return href.replace("ftp://ftp.ncbi.nlm.nih.gov", "https://ftp.ncbi.nlm.nih.gov")

    if pdf_link is not None and pdf_link.get("href"):
        pr = polite_get(to_https(pdf_link.get("href")), timeout=60, headers=BROWSER_HEADERS)
        if pr and pr.status_code == 200 and is_valid_pdf(pr.content):
            dest.write_bytes(pr.content)
            return True

    if tgz_link is not None and tgz_link.get("href"):
        pr = polite_get(to_https(tgz_link.get("href")), timeout=60, headers=BROWSER_HEADERS)
        if pr and pr.status_code == 200 and pr.content[:2] == b"\x1f\x8b":  # gzip magic
            try:
                with tarfile.open(fileobj=BytesIO(pr.content), mode="r:gz") as tar:
                    members = [m for m in tar.getmembers() if m.name.lower().endswith(".pdf")]
                    if members:
                        member = max(members, key=lambda m: m.size)  # article, not figures
                        data = tar.extractfile(member).read()
                        if is_valid_pdf(data):
                            dest.write_bytes(data)
                            return True
            except Exception:
                log.debug("tgz extract failed", exc_info=True)
    return False


def unpaywall_download(doi: str, dest: Path) -> bool:
    """Query Unpaywall and try its OA PDF links, repository copies first
    (they rarely sit behind the publisher's Cloudflare/captcha wall)."""
    doi = clean_doi(doi)
    if not doi:
        return False
    r = polite_get(f"https://api.unpaywall.org/v2/{doi}?email={EMAIL}", timeout=15)
    if not r or r.status_code != 200:
        return False
    try:
        data = r.json()
    except Exception:
        log.debug("unpaywall json parse failed", exc_info=True)
        return False

    locations = [loc for loc in data.get("oa_locations", []) if loc]
    best = data.get("best_oa_location")
    if best and best not in locations:
        locations.append(best)
    # repository copies first, publisher copies last
    locations.sort(key=lambda l: 0 if l.get("host_type") == "repository" else 1)

    tried = set()
    for loc in locations:
        pdf_url = loc.get("url_for_pdf")
        if not pdf_url or pdf_url in tried:
            continue
        tried.add(pdf_url)
        pr = polite_get(pdf_url, headers={**BROWSER_HEADERS, "Accept": PDF_ACCEPT})
        if pr and pr.status_code == 200 and is_valid_pdf(pr.content):
            dest.write_bytes(pr.content)
            return True
    return False


def session_download(article_url: str, pdf_url: str, dest: Path) -> bool:
    """Warm up cookies on the article page, then fetch the PDF (OA publisher flow)."""
    if not (article_url and pdf_url):
        return False
    polite_get(article_url, timeout=20)  # warm up cookies / bot counters
    pr = polite_get(pdf_url, headers={**BROWSER_HEADERS, "Accept": PDF_ACCEPT, "Referer": article_url})
    if pr and pr.status_code == 200 and is_valid_pdf(pr.content):
        dest.write_bytes(pr.content)
        return True
    return False


# ---------------------------------------------------------------------------
# Note scanning + classification
# ---------------------------------------------------------------------------

def first_host(note: dict) -> str:
    for key in ("pdf_url", "article_url", "pmc_url"):
        if note[key]:
            return urlparse(note[key]).netloc.lower()
    return ""


def classify(note: dict) -> str:
    """Source kind, used to route automated strategies."""
    if not (note["pdf_url"] or note["article_url"] or note["pmc_url"] or note["doi"]):
        return "no-source"
    host = first_host(note)
    if note["pmcid"] or "ncbi.nlm.nih.gov" in host or host.startswith("pmc."):
        return "pmc"
    if "mdpi.com" in host:
        return "mdpi"
    if any(h in host for h in PAYWALL_HOSTS):
        return "paywall"
    if any(h in host for h in OA_PUBLISHER_HOSTS):
        return "oa_publisher"
    return "generic"


def target_url(note: dict) -> str:
    return note["pdf_url"] or note["article_url"] or note["pmc_url"]


def scan_notes(folder: Path) -> list:
    """Parse every study .md into a record dict. Infers pdf_file if missing."""
    notes = []
    for md_path in sorted(folder.glob("*.md")):
        if md_path.name == "_index.md":
            continue
        meta = parse_frontmatter(md_path)
        pdf_name = meta.get("pdf_file", "").strip()
        if not pdf_name:
            pdf_name = infer_pdf_name_from_url(meta.get("pdf_url", "").strip())
        if not pdf_name:
            pdf_name = infer_pdf_name_from_url(meta.get("url", "").strip())
        if not pdf_name:
            pdf_name = f"{md_path.stem}.pdf"
        if not pdf_name.lower().endswith(".pdf"):
            log.warning("WARNING: %s has a non-.pdf pdf_file (%r) — skipping", md_path.name, pdf_name)
            continue
        if not meta.get("pdf_file", "").strip():
            update_frontmatter_field(md_path, "pdf_file", pdf_name)
            log.info("inferred pdf_file for %s: %s", md_path.name, pdf_name)
        pmc_field = meta.get("pmc", "").strip()
        m = re.search(r"PMC\d+", pmc_field)
        note = {
            "md_path": md_path,
            "pdf_name": pdf_name,
            "dest": folder / pdf_name,
            "pdf_url": meta.get("pdf_url", "").strip(),
            "article_url": meta.get("url", "").strip(),
            "doi": meta.get("doi", "").strip(),
            "pmc_url": pmc_field,
            "pmcid": m.group(0) if m else "",
            "status": meta.get("pdf_status", "").strip(),
        }
        note["kind"] = classify(note)
        notes.append(note)
    return notes


# ---------------------------------------------------------------------------
# Phase 1: automated, publisher-aware
# ---------------------------------------------------------------------------

def try_automated(note: dict) -> str:
    """Run the strategies that fit this note's publisher. Returns a status."""
    kind = note["kind"]
    dest = note["dest"]
    if kind == "no-source":
        return ST_NO_SOURCE

    # One Europe PMC lookup gives us a (maybe) PMCID + OA flag without blind PDF GETs.
    pmcid, is_oa = "", False
    if kind in ("pmc", "mdpi") or note["doi"]:
        pmcid, is_oa = europepmc_lookup(note["pmcid"], note["doi"])

    if kind == "pmc":
        if pmcid and is_oa and europepmc_download(pmcid, dest):
            return ST_DOWNLOADED
        if pmcid and ncbi_oa_download(pmcid, dest):
            return ST_DOWNLOADED
        if note["doi"] and unpaywall_download(note["doi"], dest):
            return ST_DOWNLOADED
        return ST_NEEDS_BROWSER

    if kind == "mdpi":
        if note["doi"] and unpaywall_download(note["doi"], dest):
            return ST_DOWNLOADED
        if pmcid and is_oa and europepmc_download(pmcid, dest):
            return ST_DOWNLOADED
        return ST_NEEDS_BROWSER

    if kind in ("oa_publisher", "generic"):
        if note["doi"] and unpaywall_download(note["doi"], dest):
            return ST_DOWNLOADED
        if session_download(note["article_url"], note["pdf_url"], dest):
            return ST_DOWNLOADED
        return ST_NEEDS_BROWSER

    if kind == "paywall":
        if note["doi"] and unpaywall_download(note["doi"], dest):
            return ST_DOWNLOADED
        return ST_PAYWALLED

    return ST_NEEDS_BROWSER


def automated_phase(notes: list, retry_automated: bool) -> None:
    todo = []
    for n in notes:
        if n["dest"].exists():
            continue
        if not retry_automated and n["status"] in SKIP_AUTOMATED:
            log.debug("skip automated (status=%s): %s", n["status"], n["pdf_name"])
            continue
        todo.append(n)

    if not todo:
        log.info("Phase 1 (automated): nothing to try (all present or already classified).\n")
        return

    total = len(todo)
    log.info("Phase 1 (automated): %d to try\n", total)
    for i, n in enumerate(todo, 1):
        log.info("[%d/%d] %s  (%s)", i, total, n["pdf_name"], n["kind"])
        status = try_automated(n)
        set_status(n, status)
        if status == ST_DOWNLOADED:
            log.info("       ✓ downloaded")
        else:
            log.info("       · %s", status)
    log.info("")


# ---------------------------------------------------------------------------
# Phase 2: responsive browser fallback (solve captcha, or close tab to skip)
# ---------------------------------------------------------------------------

def fetch_pdf_via_context(ctx, url: str):
    """Fetch a URL through the browser context (reuses its solved-captcha cookies).
    Returns PDF bytes, or None if it's still an HTML/captcha interstitial."""
    if not url:
        return None
    try:
        r = ctx.request.get(url, timeout=40_000, headers={"Accept": PDF_ACCEPT})
        if r.ok:
            body = r.body()
            if is_valid_pdf(body):
                return body
    except Exception as e:
        log.debug("context fetch failed: %s (%s)", url, type(e).__name__)
    return None


def print_page_to_pdf(context, tab, dest: Path) -> bool:
    """Render the currently-loaded page to PDF via CDP and save it to dest.
    This is the 'print to PDF' path for pages that are themselves the content
    (no downloadable article PDF). Works in the headful browser because it uses
    the raw Page.printToPDF CDP command (Playwright's page.pdf() is headless-only)."""
    try:
        if tab.is_closed():
            return False
        cdp = context.new_cdp_session(tab)
        res = cdp.send("Page.printToPDF", {
            "printBackground": True,
            "preferCSSPageSize": True,
        })
        data = base64.b64decode(res["data"])
        if is_valid_pdf(data):
            dest.write_bytes(data)
            return True
    except Exception:
        log.debug("printToPDF failed for %s", dest.name, exc_info=True)
    return False


CAPTCHA_MARKERS = (
    "checking your browser", "just a moment", "recaptcha",
    "attention required", "verifying you are human", "enable javascript and cookies",
)


def is_captcha_page(tab) -> bool:
    """True if the tab is showing a captcha / bot-check interstitial (so we should
    wait for the human and NOT poll the server)."""
    try:
        if tab.is_closed():
            return False
        title = (tab.title() or "").lower()
        return any(m in title for m in CAPTCHA_MARKERS)
    except Exception:
        return False


def browser_phase(notes: list, folder: Path, timeout_s: int, include_paywalled: bool,
                  print_pages: bool = True, print_settle: float = 4.0) -> None:
    missing = [n for n in notes if not n["dest"].exists() and target_url(n)
               and n["kind"] != "no-source"]
    if not include_paywalled:
        missing = [n for n in missing if n["kind"] != "paywall"]
    if not missing:
        log.info("Phase 2 (browser): nothing left to fetch.")
        return

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("Phase 2 skipped: Playwright not installed.")
        log.warning("  Run: pip install playwright  &&  playwright install chromium")
        return

    # Front-load no-interaction wins (mdpi auto-downloads), group PMC so one solve
    # cascades, paywalled last.
    kind_order = {"mdpi": 0, "pmc": 1, "oa_publisher": 2, "generic": 3, "paywall": 4}
    missing.sort(key=lambda n: kind_order.get(n["kind"], 3))
    total = len(missing)
    wait_note = "wait until you solve or close it" if timeout_s <= 0 else f"auto-skip after {timeout_s}s"
    log.info("=" * 60)
    log.info("Phase 2 (browser): %d left. A Chrome window will open.", total)
    log.info("MDPI etc. download automatically. For a captcha: solve it (saves instantly)")
    log.info("or CLOSE THE TAB to skip. Each captcha tab will %s.", wait_note)
    if print_pages:
        log.info("Plain webpages (no PDF to download) are auto-printed to PDF after %.0fs.", print_settle)
    log.info("Ctrl+C to stop — re-run any time, it resumes where you left off.")
    log.info("=" * 60 + "\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
        )
        context = browser.new_context(
            accept_downloads=True, no_viewport=True,
            user_agent=BROWSER_HEADERS["User-Agent"],
        )
        anchor = context.new_page()  # keeps the context alive when item tabs are closed
        try:
            anchor.goto("about:blank")
        except Exception:
            log.debug("anchor goto failed", exc_info=True)

        for i, n in enumerate(missing, 1):
            url = target_url(n)
            pdf_url = n["pdf_url"] or url
            tag = " [paywalled]" if n["kind"] == "paywall" else ""
            log.info("[%d/%d] %s%s", i, total, n["pdf_name"], tag)

            # Fast path: this host may already be cleared from an earlier solve.
            data = fetch_pdf_via_context(context, pdf_url)
            dl = {"ok": False}
            skipped = timed_out = printed = False
            can_print = print_pages and n["kind"] in PRINTABLE_KINDS

            if not data:
                tab = context.new_page()

                def _on_download(d, _dest=n["dest"], _dl=dl):
                    try:
                        d.save_as(str(_dest))
                        _dl["ok"] = True
                    except Exception as e:
                        log.debug("download save failed: %s", type(e).__name__)

                tab.on("download", _on_download)
                try:
                    # MDPI fires a download here (goto raises "Download is starting" — expected).
                    tab.goto(url, wait_until="domcontentloaded", timeout=60_000)
                except Exception as e:
                    log.debug("nav note: %s", str(e).splitlines()[0])

                prompted = False
                settled_since = None  # when the page first looked loaded & past any captcha
                deadline = time.time() + timeout_s if timeout_s and timeout_s > 0 else None
                while True:
                    if dl["ok"]:
                        break
                    if tab.is_closed():
                        skipped = True
                        break
                    if is_captcha_page(tab):
                        settled_since = None  # restart the settle timer once it clears
                        if not prompted:
                            log.info("       solve the captcha, or close this tab to skip ...")
                            prompted = True
                    else:
                        # Page is past any captcha — safe to ask the server (gently).
                        data = fetch_pdf_via_context(context, pdf_url)
                        if data:
                            break
                        # No downloadable PDF. If this kind's source is the webpage
                        # itself, print the rendered page once it has settled.
                        if can_print:
                            if settled_since is None:
                                settled_since = time.time()
                            elif time.time() - settled_since >= print_settle:
                                if print_page_to_pdf(context, tab, n["dest"]):
                                    printed = True
                                    break
                    if deadline and time.time() > deadline:
                        timed_out = True
                        break
                    try:
                        tab.wait_for_timeout(1500)
                    except Exception:
                        skipped = tab.is_closed()
                        break

                if not tab.is_closed():
                    try:
                        tab.close()
                    except Exception:
                        log.debug("tab close failed", exc_info=True)

                # Validate a captured download; discard if it isn't a real PDF.
                if dl["ok"]:
                    try:
                        if not (n["dest"].exists() and is_valid_pdf(n["dest"].read_bytes())):
                            dl["ok"] = False
                            n["dest"].unlink(missing_ok=True)
                    except Exception:
                        dl["ok"] = False

            if data:
                n["dest"].write_bytes(data)
                set_status(n, ST_DOWNLOADED)
                log.info("       ✓ saved (%s bytes)\n", f"{len(data):,}")
            elif dl["ok"]:
                set_status(n, ST_DOWNLOADED)
                log.info("       ✓ downloaded\n")
            elif printed:
                set_status(n, ST_PRINTED)
                log.info("       ✓ printed page to PDF (%s bytes)\n",
                         f"{n['dest'].stat().st_size:,}")
            else:
                set_status(n, ST_NEEDS_BROWSER)
                if skipped:
                    log.info("       ⏭  skipped (tab closed)\n")
                elif timed_out:
                    log.info("       ⏱  timed out — left for next time\n")
                else:
                    log.info("       ✗ not saved — left for next time\n")

        context.close()
        browser.close()
    log.info("Browser phase done.")


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def write_report(notes: list, folder: Path) -> None:
    have = [n for n in notes if n["dest"].exists()]
    missing = [n for n in notes if not n["dest"].exists()]
    paywalled = [n for n in missing if n["kind"] == "paywall" or n["status"] == ST_PAYWALLED]
    no_source = [n for n in missing if n["kind"] == "no-source"]
    blocked = [n for n in missing if n not in paywalled and n not in no_source]

    log.info("\n" + "=" * 60)
    log.info("SUMMARY")
    log.info("=" * 60)
    log.info("  Have PDF on disk  : %d", len(have))
    log.info("  Still missing     : %d  (blocked %d, paywalled %d, no-source %d)",
             len(missing), len(blocked), len(paywalled), len(no_source))

    lines = [f"PDF DOWNLOAD REPORT — {folder.name}", "=" * 60,
             f"Have PDF on disk  : {len(have)}",
             f"Still missing     : {len(missing)}",
             f"  blocked         : {len(blocked)}",
             f"  paywalled       : {len(paywalled)}",
             f"  no-source       : {len(no_source)}", ""]

    if blocked:
        lines.append("STILL MISSING (not paywalled) — re-run and solve in the browser")
        lines.append("-" * 40)
        for n in blocked:
            lines.append(f"  File : {n['pdf_name']}")
            lines.append(f"  URL  : {target_url(n)}")
            lines.append("")

    if paywalled:
        lines.append("PAYWALLED — no OA copy found; needs institutional access")
        lines.append("-" * 40)
        for n in paywalled:
            lines.append(f"  File : {n['pdf_name']}")
            lines.append(f"  URL  : {n['article_url'] or n['pdf_url']}")
            if n["doi"]:
                lines.append(f"  DOI  : {n['doi']}")
            lines.append("")

    if no_source:
        lines.append("NO SOURCE — note has no usable url/doi/pmc")
        lines.append("-" * 40)
        for n in no_source:
            lines.append(f"  File : {n['pdf_name']}  ({n['md_path'].name})")
        lines.append("")

    report_path = folder / "download_report.txt"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Full report written to: %s", report_path)


# ---------------------------------------------------------------------------
# CLI / main
# ---------------------------------------------------------------------------

def setup_logging(folder: Path, verbose: bool, log_file: str | None) -> None:
    log.setLevel(logging.DEBUG)
    log.handlers.clear()

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(ch)

    fpath = Path(log_file) if log_file else folder / "download.log"
    fh = logging.FileHandler(fpath, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        description="Download missing study PDFs (automated APIs, then a browser captcha pass).")
    ap.add_argument("folder", nargs="?", default=str(Path(__file__).parent),
                    help="study folder of .md notes (default: this script's folder)")
    ap.add_argument("--no-browser", action="store_true", help="phase 1 only, no window")
    ap.add_argument("--retry-automated", action="store_true",
                    help="re-attempt the APIs even for notes marked needs-browser/paywalled")
    ap.add_argument("--include-paywalled", action="store_true",
                    help="also open paywalled papers in the browser pass")
    ap.add_argument("--browser-timeout", type=int, default=0,
                    help="seconds to wait per captcha paper before auto-skipping "
                         "(default 0 = wait until you solve it or close the tab)")
    ap.add_argument("--no-print-pages", action="store_true",
                    help="don't auto-print plain webpages to PDF in the browser pass")
    ap.add_argument("--print-settle", type=float, default=4.0,
                    help="seconds a non-captcha webpage must stay loaded before it's "
                         "printed to PDF (default 4.0)")
    ap.add_argument("--rate", type=float, default=2.0,
                    help="minimum seconds between requests to the same host (default 2.0)")
    ap.add_argument("-v", "--verbose", action="store_true", help="debug-level console output")
    ap.add_argument("--log-file", default=None, help="log file path (default: <folder>/download.log)")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    folder = Path(args.folder).resolve()
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")

    setup_logging(folder, args.verbose, args.log_file)
    RATE.min_interval = args.rate

    notes = scan_notes(folder)
    if not notes:
        log.info("No study .md notes found in %s", folder)
        return

    log.info("Scanning %s  —  %d notes\n", folder, len(notes))

    try:
        automated_phase(notes, args.retry_automated)
        if args.no_browser:
            log.info("(--no-browser: skipping the browser phase)\n")
        else:
            browser_phase(notes, folder, args.browser_timeout, args.include_paywalled,
                          print_pages=not args.no_print_pages, print_settle=args.print_settle)
    except KeyboardInterrupt:
        log.info("\nInterrupted — writing report with progress so far.")
    finally:
        write_report(notes, folder)


if __name__ == "__main__":
    main()
