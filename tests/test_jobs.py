import pytest
import responses

from signal_scout.sources.jobs import (
    GREENHOUSE_URL,
    LEVER_URL,
    USAJOBS_URL,
    JobsSource,
    matches_keywords,
    matches_location,
)

GH = {
    "jobs": [
        {
            "id": 1,
            "title": "IT Support Specialist",
            "absolute_url": "https://x/1",
            "location": {"name": "Huntsville, AL"},
        },
        {
            "id": 2,
            "title": "Software Engineer",
            "absolute_url": "https://x/2",
            "location": {"name": "Huntsville, AL"},
        },
        {
            "id": 3,
            "title": "Help Desk Technician",
            "absolute_url": "https://x/3",
            "location": {"name": "Austin, TX"},
        },
        {
            "id": 4,
            "title": "Network Engineer",
            "absolute_url": "https://x/4",
            "location": {"name": "Remote - US"},
        },
    ]
}
LEVER = [
    {
        "id": "a",
        "text": "Systems Administrator",
        "hostedUrl": "https://l/a",
        "categories": {"location": "Huntsville, Alabama"},
        "salaryRange": {"max": 50000},
    },
    {
        "id": "b",
        "text": "Systems Administrator II",
        "hostedUrl": "https://l/b",
        "categories": {"location": "Huntsville, Alabama"},
        "salaryRange": {"max": 90000},
    },
]
CFG = {
    "keywords": [
        "IT support",
        "help desk",
        "system administrator",
        "systems administrator",
        "network",
    ],
    "locations": ["Huntsville"],
}


def test_matchers():
    assert matches_keywords("Sr. HELP  DESK Analyst", ["help desk"])
    assert not matches_keywords("Chef", ["help desk"])
    assert matches_keywords("anything", [])
    assert matches_location("Remote", ["Huntsville"], allow_remote=True)
    assert not matches_location("Remote", ["Huntsville"], allow_remote=False)


@responses.activate
def test_greenhouse_filters(session):
    responses.get(GREENHOUSE_URL.format(board="acme"), json=GH)
    items = JobsSource({**CFG, "greenhouse": ["acme"]}, session).fetch()
    assert [i.uid for i in items] == ["greenhouse:acme:1"]


@responses.activate
def test_remote_allowed(session):
    responses.get(GREENHOUSE_URL.format(board="acme"), json=GH)
    items = JobsSource({**CFG, "allow_remote": True, "greenhouse": ["acme"]}, session).fetch()
    assert {i.uid for i in items} == {"greenhouse:acme:1", "greenhouse:acme:4"}


@responses.activate
def test_lever_salary_filter(session):
    responses.get(LEVER_URL.format(company="corp"), json=LEVER)
    items = JobsSource({**CFG, "min_salary": 60000, "lever": ["corp"]}, session).fetch()
    assert [i.uid for i in items] == ["lever:corp:b"]


@responses.activate
def test_one_board_failing_is_isolated(session):
    responses.get(GREENHOUSE_URL.format(board="broken"), status=404)
    responses.get(GREENHOUSE_URL.format(board="acme"), json=GH)
    items = JobsSource({**CFG, "greenhouse": ["broken", "acme"]}, session).fetch()
    assert len(items) == 1


@responses.activate
def test_all_boards_failing_raises(session):
    responses.get(GREENHOUSE_URL.format(board="broken"), status=500)
    with pytest.raises(RuntimeError):
        JobsSource({**CFG, "greenhouse": ["broken"]}, session).fetch()


def test_usajobs_skipped_without_key(session, monkeypatch):
    monkeypatch.delenv("USAJOBS_API_KEY", raising=False)
    src = JobsSource({**CFG, "usajobs": {"enabled": True}}, session)
    assert src.fetch() == []  # no HTTP call made (responses not active would fail anyway)


@responses.activate
def test_usajobs_headers_and_parse(session, monkeypatch):
    monkeypatch.setenv("USAJOBS_API_KEY", "k" * 20)
    monkeypatch.setenv("USAJOBS_EMAIL", "me@example.com")
    body = {
        "SearchResult": {
            "SearchResultItems": [
                {
                    "MatchedObjectDescriptor": {
                        "PositionID": "P1",
                        "PositionTitle": "IT Specialist (Network)",
                        "OrganizationName": "Army",
                        "PositionURI": "https://usajobs/P1",
                        "PositionLocationDisplay": "Redstone Arsenal, Alabama",
                        "PositionRemuneration": [{"MaximumRange": "80000"}],
                    }
                }
            ]
        }
    }
    responses.get(USAJOBS_URL, json=body)
    src = JobsSource(
        {"keywords": ["network"], "locations": ["Huntsville"], "usajobs": {"enabled": True}},
        session,
    )
    items = src.fetch()
    assert [i.uid for i in items] == ["usajobs:P1"]  # geo-filtered by API, not by name
    assert responses.calls[0].request.headers["Authorization-Key"] == "k" * 20
    assert responses.calls[0].request.headers["User-Agent"] == "me@example.com"
