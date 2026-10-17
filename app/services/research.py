"""Deterministic company research: fetch public pages and keep verbatim sentences.

No model is involved. Every fact is a sentence quoted from a page we actually
fetched, stored with its source URL, so the letter can only use company
knowledge that is traceable.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import DATA_DIR
from app.models.schemas import CompanyResearch, JobAnalysis

CACHE_PATH = DATA_DIR / "research_cache.json"
CACHE_TTL_SECONDS = 7 * 24 * 3600
MAX_PAGES = 3
MAX_BYTES = 1_000_000
TIMEOUT = 8.0
MAX_FACTS = 6
USER_AGENT = "JobApplicationAssistant/1.0 (personal use; reads public company pages)"

JOB_BOARD_HOSTS = (
    "linkedin.", "indeed.", "glassdoor.", "welcometothejungle.", "apec.", "francetravail.", "pole-emploi.",
    "monster.", "jobteaser.", "lever.co", "greenhouse.io", "workable.", "smartrecruiters.", "ashbyhq.",
    "myworkdayjobs.", "taleo.", "jobijoba.", "hellowork.", "ziprecruiter.", "google.", "bit.ly", "goo.gl",
    "facebook.", "twitter.", "x.com", "instagram.", "youtube.", "github.com",
)
ABOUT_HINTS = ("about", "a-propos", "apropos", "qui-sommes", "who-we-are", "company", "mission", "our-story", "entreprise", "notre-histoire")
SIGNAL_WORDS = (
    "we ", "our ", "mission", "build", "develop", "platform", "customers", "clients", "founded", "leading",
    "products", "solutions", "teams", "engineers", "global", "innovation", "specialis", "provides", "helps",
    "nous ", "notre ", "nos ", "fondée", "leader", "solutions", "plateforme", "développ", "clients", "équipes",
)
NOISE_WORDS = (
    "cookie", "privacy", "confidentialit", "terms", "newsletter", "subscribe", "copyright", "all rights",
    "javascript", "sign in", "log in", "accept", "consent", "©", "mentions légales", "tous droits",
)
URL_RE = re.compile(r"https?://[^\s<>\")\]]+|(?<![@\w.])(?:www\.)[a-z0-9.-]+\.[a-z]{2,}[^\s<>\")\]]*", re.I)
SKIPPED_TAGS = {"script", "style", "noscript", "nav", "footer", "header", "form", "svg", "iframe", "button", "aside"}


@dataclass
class ResearchResult:
    research: CompanyResearch | None = None
    notes: list[str] = field(default_factory=list)


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: list[str] = []
        self.blocks: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._skip = 0
        self._buf: list[str] = []
        self._href: str | None = None
        self._anchor: list[str] = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "meta":
            key = (data.get("name") or data.get("property") or "").lower()
            if key in {"description", "og:description", "twitter:description"} and data.get("content"):
                self.meta.append(data["content"])
        if tag == "a" and data.get("href"):
            self._href, self._anchor = data["href"], []
        if tag in SKIPPED_TAGS:
            self._skip += 1
        elif tag in {"p", "li", "h1", "h2", "h3", "div", "section", "br"}:
            self._flush()

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._anchor)))
            self._href = None
        if tag in SKIPPED_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in {"p", "li", "h1", "h2", "h3", "div", "section"}:
            self._flush()

    def handle_data(self, data):
        if self._href is not None:
            self._anchor.append(data.strip())
        if not self._skip:
            self._buf.append(data)

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        self._buf = []
        if text:
            self.blocks.append(text)

    def close(self) -> None:
        super().close()
        self._flush()


def _is_public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast:
            return False
    return True


def normalize_url(value: str) -> str:
    value = value.strip().rstrip(".,;")
    if not value:
        return ""
    if not re.match(r"^https?://", value, re.I):
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    return value


def candidate_urls(job_text: str) -> list[str]:
    """Company-looking URLs found in the posting (job boards excluded)."""
    found: list[str] = []
    for raw in URL_RE.findall(job_text or ""):
        url = normalize_url(raw)
        host = (urlparse(url).hostname or "").lower()
        if url and not any(board in host for board in JOB_BOARD_HOSTS):
            origin = f"{urlparse(url).scheme}://{host}"
            if origin not in found:
                found.append(origin)
    return found


def _fetch(url: str) -> tuple[str, str]:
    """Fetch one public HTML page; returns (final_url, html). Raises ValueError/httpx errors."""
    current = url
    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=False) as client:
        for _ in range(4):
            host = urlparse(current).hostname or ""
            if not _is_public_host(host):
                raise ValueError(f"{host or 'host'} is not a public address")
            with client.stream("GET", current) as response:
                if response.is_redirect and response.headers.get("location"):
                    current = urljoin(current, response.headers["location"])
                    if urlparse(current).scheme not in {"http", "https"}:
                        raise ValueError("redirect to a non-web address")
                    continue
                response.raise_for_status()
                if "html" not in response.headers.get("content-type", "html").lower():
                    raise ValueError("not an HTML page")
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    chunks.append(chunk)
                    if size > MAX_BYTES:
                        break
                encoding = response.encoding or "utf-8"
                return current, b"".join(chunks).decode(encoding, errors="replace")
    raise ValueError("too many redirects")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Þ0-9])", text) if s.strip()]


IMPERATIVE_STARTS = (
    "start", "customize", "learn", "explore", "discover", "get ", "try ", "read", "join", "contact", "book",
    "request", "sign", "build with", "see ", "watch", "download", "view", "find ", "talk", "démarrez", "découvrez",
    "rejoignez", "contactez", "essayez",
)


def _good_sentence(sentence: str) -> bool:
    if not 40 <= len(sentence) <= 280 or len(sentence.split()) < 6:
        return False
    # Testimonials, calls to action and cut-off fragments are not statements about the company.
    if sentence[0] in "“\"'«" or sentence[-1] not in ".!?":
        return False
    low = sentence.casefold()
    if low.startswith(IMPERATIVE_STARTS) or " your " in f" {low} ":
        return False
    if any(word in low for word in NOISE_WORDS):
        return False
    return sum(ch.isalpha() for ch in sentence) / len(sentence) > 0.7


def extract_facts(html: str, job: JobAnalysis | None = None) -> list[str]:
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    pool: list[str] = []
    for meta in parser.meta:
        pool.extend(_sentences(re.sub(r"\s+", " ", meta)))
    for block in parser.blocks:
        pool.extend(_sentences(block))
    job_terms = _job_terms(job)
    scored: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for index, sentence in enumerate(pool):
        key = sentence.casefold()
        if key in seen or not _good_sentence(sentence):
            continue
        seen.add(key)
        score = sum(1 for word in SIGNAL_WORDS if word in key + " ")
        score += 2 * sum(1 for term in job_terms if term in key)
        if score:
            scored.append((-score, index, sentence))
    scored.sort()
    return [sentence for _, _, sentence in scored[:MAX_FACTS]]


def _job_terms(job: JobAnalysis | None) -> set[str]:
    if job is None:
        return set()
    terms = [*job.domain_keywords, *job.technical_skills, *job.tools_and_technologies]
    return {t.casefold() for t in terms if len(t) > 3}


def _about_links(html: str, base: str) -> list[str]:
    parser = _PageParser()
    parser.feed(html)
    base_host = urlparse(base).hostname
    links: list[str] = []
    for href, _label in parser.links:
        target = urljoin(base, href.split("#")[0])
        parsed = urlparse(target)
        if parsed.hostname != base_host or parsed.scheme not in {"http", "https"}:
            continue
        if any(h in parsed.path.casefold() for h in ABOUT_HINTS) and target not in links and target != base:
            links.append(target)
    return links


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def research_company(job: JobAnalysis, job_text: str = "", company_url: str = "", fetch=_fetch) -> ResearchResult:
    """Research from an explicit URL, else a company URL found in the posting. Never raises."""
    result = ResearchResult()
    explicit = normalize_url(company_url)
    urls = [explicit] if explicit else candidate_urls(job_text)[:1]
    if not urls:
        return result
    root = urls[0]

    cache = _load_cache()
    cached = cache.get(root)
    if cached and time.time() - cached.get("at", 0) < CACHE_TTL_SECONDS and cached.get("facts"):
        facts, sources = cached["facts"], cached["sources"]
    else:
        facts, sources = [], []
        try:
            final, html = fetch(root)
            pages = [(final, html)]
            for link in _about_links(html, final)[: MAX_PAGES - 1]:
                try:
                    pages.append(fetch(link))
                except Exception:
                    continue
            for page_url, page_html in [*pages[1:], pages[0]]:
                page_facts = [f for f in extract_facts(page_html, job) if f not in facts]
                if page_facts:
                    facts.extend(page_facts)
                    sources.append(page_url)
            facts = facts[:MAX_FACTS + 2]
        except Exception as exc:
            result.notes.append(f"Company research skipped: could not read {root} ({type(exc).__name__}: {exc}).")
            return result
        if facts:
            cache[root] = {"at": time.time(), "facts": facts, "sources": sources}
            _save_cache(cache)

    if not facts:
        result.notes.append(f"Company research found no usable facts at {root}.")
        return result

    terms = _job_terms(job)
    relevant = [f for f in facts if any(t in f.casefold() for t in terms)]
    result.research = CompanyResearch(
        company_context=facts,
        candidate_relevant_points=relevant,
        sources=sources,
        verified=True,
    )
    host = urlparse(root).hostname
    result.notes.append(f"Company research: {len(facts)} verified facts quoted from {host}; review them before sending.")
    return result
