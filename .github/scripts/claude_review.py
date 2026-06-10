import json
import os
import re

import anthropic
import requests

REPO = os.environ["GITHUB_REPOSITORY"]
PR_NUMBER = int(os.environ["PR_NUMBER"])

GH_HEADERS = {
    "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "comments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "line": {"type": "integer"},
                    "body": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["info", "warning", "error"],
                    },
                },
                "required": ["path", "line", "body", "severity"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "comments"],
    "additionalProperties": False,
}


def get_pr_files() -> list[dict]:
    files = []
    url = f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}/files"
    while url:
        resp = requests.get(url, headers=GH_HEADERS, params={"per_page": 100})
        resp.raise_for_status()
        files.extend(resp.json())
        url = resp.links.get("next", {}).get("url")
    return files


def get_pr_head_sha() -> str:
    resp = requests.get(
        f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}",
        headers=GH_HEADERS,
    )
    resp.raise_for_status()
    return resp.json()["head"]["sha"]


def parse_diff_lines(patch: str) -> set[int]:
    available = set()
    current_line = 0
    for line in patch.splitlines():
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            if m:
                current_line = int(m.group(1)) - 1
        elif line.startswith("-"):
            pass
        elif line.startswith("+"):
            current_line += 1
            available.add(current_line)
        else:
            current_line += 1
    return available


def build_diff_prompt(files: list[dict]) -> tuple[str, dict[str, set[int]]]:
    sections = []
    file_lines: dict[str, set[int]] = {}

    for f in files:
        filename = f["filename"]
        patch = f.get("patch", "")
        if not patch:
            continue

        available = parse_diff_lines(patch)
        if not available:
            continue

        file_lines[filename] = available

        if len(patch) > 8_000:
            patch = patch[:8_000] + "\n... (truncated)"

        sections.append(
            f"### {filename} ({f['status']})\n"
            f"Commentable lines (new file): {sorted(available)}\n"
            f"```diff\n{patch}\n```"
        )

    return "\n\n".join(sections), file_lines


def review_with_claude(diff_text: str) -> dict:
    client = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=(
            "You are an expert code reviewer. Identify bugs, security issues, "
            "performance problems, and code quality concerns. Be concise and actionable. "
            "Only comment on lines listed under 'Commentable lines' for each file."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    "Review this pull request diff and return JSON with:\n"
                    "- summary: a short overall review (1-3 sentences)\n"
                    "- comments: inline comments, each with path, line (must be in "
                    "'Commentable lines'), body (markdown ok), severity\n\n"
                    + diff_text
                ),
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": REVIEW_SCHEMA}},
    )

    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def post_review(commit_sha: str, review: dict, file_lines: dict[str, set[int]]) -> str:
    valid_comments = []
    for c in review["comments"]:
        if c["path"] in file_lines and c["line"] in file_lines[c["path"]]:
            label = c["severity"].upper()
            valid_comments.append(
                {
                    "path": c["path"],
                    "line": c["line"],
                    "side": "RIGHT",
                    "body": f"**[{label}]** {c['body']}",
                }
            )

    has_errors = any(c["severity"] == "error" for c in review["comments"])
    event = "REQUEST_CHANGES" if has_errors else "COMMENT"

    resp = requests.post(
        f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}/reviews",
        headers=GH_HEADERS,
        json={
            "commit_id": commit_sha,
            "body": f"## Claude Code Review\n\n{review['summary']}",
            "event": event,
            "comments": valid_comments,
        },
    )
    resp.raise_for_status()
    return resp.json()["html_url"]


def main():
    print("Fetching PR files...")
    files = get_pr_files()
    if not files:
        print("No changed files.")
        return

    diff_text, file_lines = build_diff_prompt(files)
    if not file_lines:
        print("No reviewable diffs (binary or empty patches).")
        return

    print(f"Reviewing {len(file_lines)} file(s) with Claude...")
    review = review_with_claude(diff_text)
    print(f"Got {len(review['comments'])} comment(s).")

    commit_sha = get_pr_head_sha()
    url = post_review(commit_sha, review, file_lines)
    print(f"Review posted: {url}")


if __name__ == "__main__":
    main()
