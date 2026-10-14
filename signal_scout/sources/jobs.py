"""Public job feeds: USAJOBS (optional key), Greenhouse and Lever public boards."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from ..models import Item
from .base import Source

log = logging.getLogger(__name__)

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/{company}?mode=json"
USAJOBS_URL = "https://data.usajobs.gov/api/search"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


def matches_keywords(title: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    t = _norm(title)
    return any(_norm(k) in t for k in keywords)


def matches_location(location: str, locations: list[str], allow_remote: bool) -> bool:
    if not locations:
        return True
    loc = _norm(location)
    if allow_remote and "remote" in loc:
        return True
    return any(_norm(x) in loc for x in locations)


class JobsSource(Source):
    name = "jobs"

    def fetch(self) -> list[Item]:
        cfg = self.config
        self.keywords: list[str] = cfg.get("keywords", [])
        self.locations: list[str] = cfg.get("locations", [])
        self.allow_remote: bool = bool(cfg.get("allow_remote", False))
        self.min_salary: float = float(cfg.get("min_salary", 0) or 0)

        raw: list[Item] = []
        errors = 0
        providers = [("greenhouse", b, self._greenhouse) for b in cfg.get("greenhouse", [])]
        providers += [("lever", c, self._lever) for c in cfg.get("lever", [])]
        for provider, target, fn in providers:
            try:
                raw.extend(fn(target))
            except Exception as exc:  # one bad board must not kill the source
                errors += 1
                log.warning(
                    "job board failed",
                    extra={"ctx": {"provider": provider, "target": target, "error": repr(exc)}},
                )
        if cfg.get("usajobs", {}).get("enabled", False):
            try:
                raw.extend(self._usajobs(cfg["usajobs"]))
            except Exception as exc:
                errors += 1
                log.warning("usajobs failed", extra={"ctx": {"error": repr(exc)}})
        if providers and errors == len(providers):
            raise RuntimeError("all job boards failed")
        kept = [i for i in raw if self._keep(i)]
        log.info("job postings scanned", extra={"ctx": {"scanned": len(raw), "kept": len(kept)}})
        return kept

    def _keep(self, item: Item) -> bool:
        if not matches_keywords(item.title, self.keywords):
            return False
        loc_ok = item.extra.get("geo_filtered") or matches_location(
            item.extra.get("location", ""), self.locations, self.allow_remote
        )
        if not loc_ok:
            return False
        salary = item.extra.get("salary_max")
        # Unknown salary passes (most public boards omit it); known salary must clear the bar.
        return not (self.min_salary and salary is not None and salary < self.min_salary)

    def _greenhouse(self, board: str) -> list[Item]:
        data = self.get_json(GREENHOUSE_URL.format(board=board))
        out = []
        for job in data.get("jobs", []):
            location = (job.get("location") or {}).get("name", "")
            out.append(
                Item(
                    source=self.name,
                    uid=f"greenhouse:{board}:{job['id']}",
                    title=f"{job.get('title', '').strip()} @ {board}",
                    url=job.get("absolute_url", ""),
                    summary=location,
                    extra={"location": location, "company": board},
                )
            )
        return out

    def _lever(self, company: str) -> list[Item]:
        data = self.get_json(LEVER_URL.format(company=company))
        out = []
        for job in data:
            cats = job.get("categories") or {}
            location = cats.get("location") or ", ".join(cats.get("allLocations") or [])
            if job.get("workplaceType") == "remote" and "remote" not in location.lower():
                location = f"{location} (Remote)".strip()
            salary = (job.get("salaryRange") or {}).get("max")
            out.append(
                Item(
                    source=self.name,
                    uid=f"lever:{company}:{job['id']}",
                    title=f"{job.get('text', '').strip()} @ {company}",
                    url=job.get("hostedUrl", ""),
                    summary=location,
                    extra={"location": location, "company": company, "salary_max": salary},
                )
            )
        return out

    def _usajobs(self, ucfg: dict[str, Any]) -> list[Item]:
        key = os.environ.get("USAJOBS_API_KEY")
        email = os.environ.get("USAJOBS_EMAIL")
        if not key or not email:
            log.info("usajobs skipped: USAJOBS_API_KEY/USAJOBS_EMAIL not set")
            return []
        headers = {"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": key}
        out = []
        for kw in self.keywords or [""]:
            params = {
                "Keyword": kw,
                "LocationName": ucfg.get("location", "Huntsville, Alabama"),
                "Radius": ucfg.get("radius_miles", 50),
                "ResultsPerPage": 100,
            }
            data = self.get_json(USAJOBS_URL, params=params, headers=headers)
            for res in data.get("SearchResult", {}).get("SearchResultItems", []):
                d = res.get("MatchedObjectDescriptor", {})
                pay = (d.get("PositionRemuneration") or [{}])[0]
                salary = float(pay["MaximumRange"]) if pay.get("MaximumRange") else None
                location = d.get("PositionLocationDisplay", "")
                out.append(
                    Item(
                        source=self.name,
                        uid=f"usajobs:{d.get('PositionID') or res.get('MatchedObjectId')}",
                        title=f"{d.get('PositionTitle', '')} @ {d.get('OrganizationName', '')}",
                        url=d.get("PositionURI", ""),
                        summary=f"{location} | up to ${salary:,.0f}" if salary else location,
                        extra={"location": location, "salary_max": salary, "geo_filtered": True},
                    )
                )
        # Dedup across keyword queries; USAJOBS already filtered by location radius.
        return list({i.uid: i for i in out}.values())
