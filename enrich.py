import json
import urllib.request
from pathlib import Path

DATA_PATH = Path("data.json")
OUT_PATH = Path("enriched_data.json")
HEADERS = {"User-Agent": "Mozilla/5.0"}

DIFF_MAP = {1: "Easy", 2: "Medium", 3: "Hard"}


def fetch_json(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    submissions = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    # Sort chronologically oldest -> newest
    submissions.sort(key=lambda s: s["timestamp"])

    unique_problems = {}
    for sub in submissions:
        slug = sub["slug"]
        if slug not in unique_problems:
            unique_problems[slug] = {
                "title": sub["title"],
                "slug": slug,
                "number": None,
                "difficulty": None,
                "elo": None,
            }

    # 1. Load Zerotrac ratings (local fallback or fetch from GitHub Pages)
    zt_file = Path("zerotrac.json")
    try:
        zt_raw = (
            json.loads(zt_file.read_text(encoding="utf-8"))
            if zt_file.exists()
            else fetch_json(
                "https://zerotrac.github.io/leetcode_problem_rating/data.json"
            )
        )
        zt_by_slug = {}
        for item in zt_raw:
            slug = item.get("TitleSlug") or item.get("titleSlug")
            rating = item.get("Rating") or item.get("rating")
            if slug and rating is not None:
                zt_by_slug[slug] = round(float(rating))
    except Exception as e:
        print(
            f"Warning: Could not load Zerotrac ratings ({e}). Continuing without ELO."
        )
        zt_by_slug = {}

    # 2. Load LeetCode difficulty & problem numbers
    lc_file = Path("lc_problems.json")
    try:
        lc_raw = (
            json.loads(lc_file.read_text(encoding="utf-8"))
            if lc_file.exists()
            else fetch_json("https://leetcode.com/api/problems/all/")
        )
        lc_by_slug = {}
        for pair in lc_raw.get("stat_status_pairs", []):
            stat = pair.get("stat", {})
            slug = stat.get("question__title_slug")
            if slug:
                lc_by_slug[slug] = {
                    "number": stat.get("frontend_question_id"),
                    "difficulty": DIFF_MAP.get(pair.get("difficulty", {}).get("level")),
                }
    except Exception as e:
        print(f"\nCould not fetch LeetCode problem list directly ({e}).")
        print(
            "Fallback: open leetcode.com in your browser, paste this in DevTools Console,"
        )
        print("and save the downloaded file as 'lc_problems.json' in this folder:\n")
        print(
            '  fetch("/api/problems/all/").then(r=>r.blob()).then(b=>{const a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="lc_problems.json";a.click();})'
        )
        lc_by_slug = {}

    # 3. Merge metadata for every unique problem
    diff_hits = 0
    elo_hits = 0
    for slug, info in unique_problems.items():
        if slug in lc_by_slug:
            info["number"] = lc_by_slug[slug]["number"]
            info["difficulty"] = lc_by_slug[slug]["difficulty"]
            if info["difficulty"]:
                diff_hits += 1
        if slug in zt_by_slug:
            info["elo"] = zt_by_slug[slug]
            elo_hits += 1

    output = {
        "problems": unique_problems,
        "submissions": submissions,
    }
    OUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    total = len(unique_problems)
    print(f"Done! Saved {OUT_PATH}")
    print(f"Unique problems: {total} | Submissions: {len(submissions)}")
    print(
        f"Difficulty matched: {diff_hits}/{total} | Zerotrac ELO matched: {elo_hits}/{total}"
    )


if __name__ == "__main__":
    main()
