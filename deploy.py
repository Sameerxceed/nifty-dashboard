#!/usr/bin/env python3
"""
deploy.py — Push files to GitHub WITHOUT manual upload.

Usage:
  python deploy.py                   # deploy all changed files
  python deploy.py generate.py       # deploy one specific file
  python deploy.py --trigger-only    # just trigger the workflow (no file changes)

Requires ONE secret: GITHUB_TOKEN (a Personal Access Token with repo scope)
Add it to GitHub Actions secrets AND use it locally by setting env var:
  export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
  python deploy.py

OR put it in a local .env file (never commit this file):
  GITHUB_TOKEN=ghp_xxxxxxxxxxxx
"""

import os, sys, json, base64, urllib.request, urllib.parse
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
REPO_OWNER  = "Sameerxceed"
REPO_NAME   = "nifty-morning-brief"
BRANCH      = "main"              # your default branch
API_BASE    = "https://api.github.com"
WORKFLOW_ID = "dashboard.yml"     # triggers a manual run

# Files to deploy (relative paths, must exist locally)
ALL_FILES = [
    "generate.py",
    "card_generator.py",
    "post_to_instagram.py",
    "notify.py",
    "broadcast.py",
    ".github/workflows/dashboard.yml",
]

# ── LOAD TOKEN ────────────────────────────────────────────────────────────────
TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    # Try loading from local .env file
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("GITHUB_TOKEN="):
                TOKEN = line.split("=", 1)[1].strip()
                break

if not TOKEN:
    print("""
ERROR: No GITHUB_TOKEN found.

To set it:
  Option A — Environment variable:
    export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
    python deploy.py

  Option B — Create a .env file (never commit it):
    echo "GITHUB_TOKEN=ghp_xxxxxxxxxxxx" > .env
    python deploy.py

Get a token at: github.com/settings/tokens/new
  → Select scopes: repo (full), workflow
""")
    sys.exit(1)

HEADERS = {
    "Authorization": "token " + TOKEN,
    "Accept":        "application/vnd.github.v3+json",
    "Content-Type":  "application/json",
    "User-Agent":    "nifty-deploy-script",
}

# ── HELPERS ───────────────────────────────────────────────────────────────────
def api(method, path, payload=None):
    url  = API_BASE + path
    body = json.dumps(payload).encode() if payload else None
    req  = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return json.loads(body) if body else {}, e.code

def get_file_sha(repo_path):
    """Get the current SHA of a file on GitHub (needed to update it)."""
    data, status = api("GET", f"/repos/{REPO_OWNER}/{REPO_NAME}/contents/{repo_path}?ref={BRANCH}")
    if status == 200:
        return data.get("sha")
    return None  # file doesn't exist yet

def upload_file(local_path, repo_path, commit_msg=None):
    """Create or update a file in the GitHub repo."""
    local = Path(local_path)
    if not local.exists():
        print(f"  SKIP {local_path} (not found locally)")
        return False

    content_b64 = base64.b64encode(local.read_bytes()).decode()
    sha         = get_file_sha(repo_path)
    msg         = commit_msg or ("Update " + local.name)

    payload = {
        "message": msg,
        "content": content_b64,
        "branch":  BRANCH,
    }
    if sha:
        payload["sha"] = sha  # required for updates

    data, status = api("PUT", f"/repos/{REPO_OWNER}/{REPO_NAME}/contents/{repo_path}", payload)

    if status in (200, 201):
        action = "Updated" if sha else "Created"
        print(f"  ✓ {action}: {repo_path}")
        return True
    else:
        print(f"  ✗ FAILED: {repo_path} — {status} {data.get('message','')}")
        return False

def trigger_workflow():
    """Trigger the GitHub Actions workflow manually."""
    payload = {"ref": BRANCH}
    data, status = api("POST",
        f"/repos/{REPO_OWNER}/{REPO_NAME}/actions/workflows/{WORKFLOW_ID}/dispatches",
        payload)
    if status == 204:
        print("  ✓ Workflow triggered — check Actions tab in ~30 seconds")
        print(f"  → https://github.com/{REPO_OWNER}/{REPO_NAME}/actions")
        return True
    else:
        print(f"  ✗ Workflow trigger failed: {status} {data.get('message','')}")
        return False

def check_workflow_status():
    """Show status of the last few workflow runs."""
    data, status = api("GET",
        f"/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs?per_page=5")
    if status != 200:
        print(f"  Could not fetch runs: {status}")
        return
    runs = data.get("workflow_runs", [])
    if not runs:
        print("  No runs found yet")
        return
    print("\n  Last 5 workflow runs:")
    for r in runs[:5]:
        icon  = {"success":"✓","failure":"✗","in_progress":"⟳","queued":"○"}.get(r["status"],"?")
        concl = r.get("conclusion","running")
        print(f"  {icon} Run #{r['run_number']} — {concl} — {r['created_at'][:16]} — {r['html_url']}")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    args     = sys.argv[1:]
    trig_only = "--trigger-only" in args
    args      = [a for a in args if not a.startswith("--")]

    print(f"\n  Nifty Dashboard Deploy → {REPO_OWNER}/{REPO_NAME} @ {BRANCH}\n")

    if trig_only:
        print("Triggering workflow (no file changes)...")
        trigger_workflow()
        return

    # Choose files to deploy
    files_to_deploy = args if args else ALL_FILES

    # Map local filename → repo path
    local_dir = Path(__file__).parent

    print(f"Deploying {len(files_to_deploy)} file(s)...")
    ok = 0
    for f in files_to_deploy:
        local_path = local_dir / f
        repo_path  = f  # same relative path in repo
        if upload_file(str(local_path), repo_path):
            ok += 1

    print(f"\n  Deployed {ok}/{len(files_to_deploy)} files")

    if ok > 0:
        print("\nTriggering workflow run...")
        trigger_workflow()

    check_workflow_status()
    print()

if __name__ == "__main__":
    main()
