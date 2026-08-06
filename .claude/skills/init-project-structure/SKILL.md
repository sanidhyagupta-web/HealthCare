---
name: init-project-structure
description: The onboarding entry point for a new project — no separate setup script involved. On first run it bootstraps .claude/wiki-project.env (auto-detecting the GitHub repo from git, asking only for what can't be derived), then inspects the cloned project repo (or scaffolds it, if empty) to decide which folders are backend, frontend, and ops/infra, each side's language, and the auth model. Writes its findings into .claude/wiki-project.env, CLAUDE.md, the rule files, and the pr-review skills.
disable-model-invocation: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
---

# Init Project Structure

This is the first skill to run on a new project — there is no setup script that runs before it.
It deliberately does not ask anything upfront that it can instead derive or detect once real code
(or at least a real git remote) exists to look at — asking blind just produces wrong guesses that
break later.

**This skill does two jobs, in order:**
1. **Bootstrap `.claude/wiki-project.env`** if it doesn't exist yet (Step 0) — auto-detecting the
   project's GitHub repo from git wherever possible, and asking only for the handful of fields
   that genuinely can't be derived (Linear project ID, optionally a Drive folder ID).
2. **Detect (or scaffold) the project's structure** — which folders are backend, frontend, and
   ops/infra, each side's language, and the auth model — by inspecting the actual repo, and writes
   the results into `.claude/wiki-project.env`, `CLAUDE.md`, the rule files, and the two
   PR-review skills.

**This is a one-time onboarding step.** Run it once, before `/init-feature-registry` (which
assumes the backend/frontend split and the auth model are already known).

## 0. Bootstrap `.claude/wiki-project.env` If Missing

Skip straight to Step 1 if `.claude/wiki-project.env` already exists — this step only runs once,
the very first time, on a workspace that has nothing yet.

**a. Resolve `GITHUB_REPO`** — never invent a URL, always confirm with the user before writing or
running anything that touches git:

```bash
git submodule status
```

- **Exactly one submodule** → likely the project repo, but confirm before trusting it. Read its
  configured URL:
  ```bash
  SUB_PATH=$(git submodule status | awk '{print $2}')
  RAW_URL=$(git config -f .gitmodules --get "submodule.${SUB_PATH}.url")
  ```
  Normalize it to `https://github.com/org/repo` form if it matches GitHub
  (`github\.com[:/]+([^/]+)/([^/.]+)(\.git)?/?$` — same pattern as below) and **ask the user to
  confirm**: "Found submodule `<SUB_PATH>` pointing at `<normalized-or-raw-url>` — is this the
  project repo?" If confirmed, set that as `GITHUB_REPO` and `MONO_DIR="$SUB_PATH"`. If the user
  says no, treat this the same as the zero-submodules case below — ask them directly for the
  correct URL rather than guessing again.
- **Zero submodules** → check this workspace's own remote:
  ```bash
  git remote get-url origin 2>/dev/null
  ```
  If it resolves and looks like a GitHub URL, **ask the user to confirm**: "No submodule found —
  is this workspace itself the project repo (using origin `<url>`), with no separate submodule
  wrapper?" If confirmed, `GITHUB_REPO` = that origin and `MONO_DIR="."` (the project's files live
  at the workspace root, not inside a submodule — this covers dropping `claude-code-starter`'s
  `.claude/`/`docs/` straight into an existing repo).
  If there's no `origin` either, or the user says this workspace is *not* the project repo, **ask
  the user directly** for the GitHub repository URL — re-prompt until it matches
  `github\.com[:/]+([^/]+)/([^/.]+)(\.git)?/?$` (accepts both `https://github.com/org/repo(.git)`
  and `git@github.com:org/repo(.git)`). Once you have a valid URL, confirm with the user, then:
  ```bash
  git submodule add "$REPO_URL" "$GH_REPO"   # $GH_REPO = the repo name captured from the regex
  ```
  Stage only — don't commit; that happens later as part of the user's own "commit your setup"
  step. Set `MONO_DIR="$GH_REPO"`.
- **Multiple submodules** → list them for the user and ask which one is the project repo; there's
  no way to guess correctly among several.

**b. Derive `WIKI_PROJECT_ID`/`WIKI_PROJECT_NAME`** from the resolved repo name:
```bash
GH_REPO=$(basename "$GITHUB_REPO" .git)
WIKI_PROJECT_NAME="$GH_REPO"
WIKI_PROJECT_ID=$(echo "$GH_REPO" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g')
```
Show both to the user and let them override — cheap to confirm now, since they show up in visible
paths (`wiki/{project-id}/`, `code-wiki/{project-id}/`) that are awkward to rename later.

**c. Ask only what can't be derived:**
- `LINEAR_PROJECT_ID` — **required**, re-prompt on a blank answer (it doubles as the
  commit-message ticket prefix used throughout this skill and `pr-review-*`).
- `DRIVE_FOLDER_ID` — optional, blank is fine (only powers `/wiki-ingest drive`).
- `LINEAR_TEAM_KEY` — optional, blank is fine (`wiki-ticket-creator` fills this in itself the
  first time it files a live ticket, if it's still blank then).

**d. Write `.claude/wiki-project.env`:**
```bash
cat << WIKI_PROJECT_EOF > .claude/wiki-project.env
# Local config for the meeting-wiki pipeline (/wiki-ingest and its sub-skills), the Linear
# ready-to-build poller (/linear-implement-trigger), and /init-project-structure. Not committed
# to git — see .gitignore. Edit any value directly; skills read this file at the start of each run.
WIKI_PROJECT_ID=$WIKI_PROJECT_ID
WIKI_PROJECT_NAME="$WIKI_PROJECT_NAME"
WIKI_PROJECT_ALIASES=
WIKI_TICKET_MODE=live
WIKI_PUBLISH_MODE=live
LINEAR_TEAM_KEY=$LINEAR_TEAM_KEY
LINEAR_PROJECT_ID=$LINEAR_PROJECT_ID
GITHUB_REPO=$GITHUB_REPO
BACKEND_DIR=
FRONTEND_DIR=
OPS_DIR=
DRIVE_FOLDER_ID=$DRIVE_FOLDER_ID
LINEAR_READY_STATE=Todo
IMPLEMENT_POLL_ENABLED=true
WIKI_PROJECT_EOF
```
`BACKEND_DIR`/`FRONTEND_DIR`/`OPS_DIR` are left blank on purpose — Steps 5-6 below fill these in
once there's a repo to actually inspect.

**e. Create `.claude/settings.local.json` if it doesn't already exist** — this file is
gitignored (per-developer), so a fresh clone or a new teammate genuinely won't have it yet:
```bash
if [[ ! -f .claude/settings.local.json ]]; then
  cat << 'SETTINGS_EOF' > .claude/settings.local.json
{
  "permissions": {
    "allow": [
      "Bash(git status)",
      "Bash(git branch:*)",
      "Bash(git checkout:*)",
      "Bash(git fetch:*)",
      "Bash(git log:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git push:*)",
      "Bash(git diff:*)",
      "Bash(git init:*)",
      "Bash(git remote:*)",
      "Bash(git submodule status)",
      "Bash(gh pr:*)",
      "Bash(gh api:*)",
      "Bash(gh auth status)",
      "Bash(docker ps:*)",
      "Bash(docker compose:*)",
      "Skill(implement)",
      "Skill(implement:*)",
      "Skill(init-project-structure)",
      "Skill(init-project-structure:*)",
      "Skill(wiki-ingest)",
      "Skill(wiki-ingest:*)"
    ]
  }
}
SETTINGS_EOF
fi
```

**f. If a new submodule was added in step (a)** → configure it to ignore dirty state, so the
workspace's own `git status` stays focused on workflow assets:
```bash
git config -f .gitmodules "submodule.$MONO_DIR.ignore" all
```

**g. Update root `CLAUDE.md` placeholders** — the only two values known this early:
```bash
TICKET_PREFIX=$(echo "$LINEAR_PROJECT_ID" | sed 's/-$//')
sed -i.bak "s|\[PROJECT NAME\]|$WIKI_PROJECT_NAME|g" CLAUDE.md
sed -i.bak "s|TICKET-123|${TICKET_PREFIX}-123|g"     CLAUDE.md
rm -f CLAUDE.md.bak
```
(Same `$TICKET_PREFIX` — `LINEAR_PROJECT_ID` with any trailing `-` trimmed — that Step 7 reuses
for the pr-review skills and `CLAUDE.md` templates below; no need to re-derive it there if this
step already ran in the same session.)

## 1. Guard — Has This Already Run?

```bash
grep -E '^(BACKEND_DIR|FRONTEND_DIR)=' .claude/wiki-project.env 2>/dev/null
```

If both `BACKEND_DIR` and `FRONTEND_DIR` already have non-empty values, **stop** — tell the user
this already ran. If they need to change the detected layout, they should edit
`.claude/wiki-project.env` directly and re-apply the relevant substitutions in Step 8 by hand,
rather than re-running this skill (it has no way to distinguish "never ran" from "ran, then the
repo changed shape").

## 2. Locate the Repo

```bash
GITHUB_REPO=$(grep '^GITHUB_REPO=' .claude/wiki-project.env | cut -d= -f2-)
MONO_DIR=$(basename "$GITHUB_REPO" .git)
```

`MONO_DIR` is normally the submodule directory the project lives in (Step 0 uses the repo name
verbatim, same as a manual `git submodule add`). Confirm `./$MONO_DIR` exists and is a git
submodule (`git submodule status | grep "$MONO_DIR"`).

If it doesn't, but `git remote get-url origin` matches `$GITHUB_REPO`, this workspace itself is
the project repo (Step 0's no-submodule path) — use `MONO_DIR="."` instead.

If neither resolves — e.g. the submodule was removed after Step 0 ran — stop and tell the user to
add it themselves (`git submodule add "$GITHUB_REPO" "$MONO_DIR"`) rather than re-running this
skill from Step 0 (which only bootstraps a missing `wiki-project.env`, not a missing submodule).

## 3. Empty vs. Populated

```bash
find "$MONO_DIR" -mindepth 1 -maxdepth 3 ! -path "*/.git*" ! -iname 'README*' ! -iname '.gitignore' | head -1
```

Nothing found → **Step 4 (Scaffold)**. Anything found → **Step 5 (Detect)**.

## 4. Empty-Repo Path: Scaffold

There's no code yet, so nothing to detect — propose creating the structure instead of guessing at
one:

1. Propose `$MONO_DIR/backend/` and `$MONO_DIR/frontend/` to the user and wait for confirmation
   (same pause idiom as `/init-code-wiki` Step 6 — this is about to commit and push into the
   project's own repo, a visible, shared-state action).
2. Ask the user for each side's language file extension directly — with no code, there is
   nothing to infer this from, unlike Step 5 below.
3. Ask the user which auth model applies (reuse `/init-feature-registry` Step 5b's Q1 wording) —
   or, if they'd rather decide once real code exists, write `security.md`'s table as `Model: Not
   yet determined — re-run /init-project-structure once real code exists` and leave
   `BACKEND_DIR`/`FRONTEND_DIR` in `.claude/wiki-project.env` set (so Step 1's guard still treats
   this as done — the layout is decided even if auth isn't yet).
4. Create the directories, and seed each with `CLAUDE.md` per Step 8's `_fill_template` logic
   below.
5. Commit and push **inside `$MONO_DIR`** (this is the project's own repo, a different remote
   than the starter kit's own) — confirm with the user first, same as `/init-code-wiki` Step 6:
   ```bash
   cd "$MONO_DIR"
   git add backend frontend
   git commit -m "chore: scaffold backend/frontend structure"
   git push
   cd -
   ```
6. Continue to Step 8 to write the rest (skip Step 5's detection and Step 6's inference — you
   already have the answers from the user).

## 5. Populated-Repo Path: Detect

Classify top-level directories under `$MONO_DIR` (and one level into common wrapper dirs like
`apps/`, `services/`, `packages/`) by manifest files and framework signals:

```bash
find "$MONO_DIR" -maxdepth 3 \( \
  -name "package.json" -o -name "pom.xml" -o -name "build.gradle" \
  -o -name "requirements.txt" -o -name "pyproject.toml" -o -name "go.mod" \
  -o -name "Gemfile" -o -name "composer.json" \
\) -not -path "*/node_modules/*" -not -path "*/.git/*"
```

- **Frontend signals**: `next.config.*`, `vite.config.*`, `angular.json`, a `package.json` with a
  `react`/`vue`/`angular`/`next` dependency, directory names like `frontend`, `client`, `web`, `ui`.
- **Backend signals**: `pom.xml`/`build.gradle`, `manage.py`/`requirements.txt`/`pyproject.toml`,
  `go.mod`, a `package.json` with `express`/`fastify`/`nestjs`/no frontend framework dependency,
  directory names like `backend`, `server`, `api`.
- **Ops/infra signals**: `terraform/`, `helm/`, `k8s/`/`kubernetes/`, many `Dockerfile`s, directory
  names like `infra`, `ops`, `infrastructure`. Ops is detected the same way as backend/frontend —
  it is not a separate onboarding concept, just another directory this step may or may not find.

For each side found, determine its dominant language extension from the manifest type
(`package.json` → `ts` if `.tsx`/`.ts` files exist else `js`, `pom.xml`/`build.gradle` → `java`,
`requirements.txt`/`pyproject.toml` → `py`, `go.mod` → `go`, `Gemfile` → `rb`).

Present findings before writing anything:

```
## Detected Project Structure

- Backend:  {path}  (*.{ext})  — found {manifest file(s)}
- Frontend: {path}  (*.{ext})  — found {manifest file(s)}
- Ops/infra: {path or "none found"}

Proceed with this layout?
```

**Wait for confirmation** — a wrong guess here changes which security/testing rules apply to
which files, worth the pause.

## 6. Infer the Auth Model (populated repos only)

Grep the backend directory for signals, in this order of specificity:

```bash
# RBAC
grep -rlE "hasRole|@RolesAllowed|@PreAuthorize|req\.user\.role|isAdmin\(" "$MONO_DIR"/{backend-path} --include="*.{ext}" 2>/dev/null | head -5

# API key / scopes
grep -rlE "x-api-key|apiKey|token\.scopes|Authorization: Bearer" "$MONO_DIR"/{backend-path} --include="*.{ext}" 2>/dev/null | head -5

# Ownership-based
grep -rlE "\.ownerId ===|\.ownerId ==|belongsTo\(user|resource\.userId" "$MONO_DIR"/{backend-path} --include="*.{ext}" 2>/dev/null | head -5
```

- **A hit in exactly one category** → that's the model. Read 2-3 of the matched files to also
  pull the mechanism (e.g. "JWT via `jsonwebtoken`", "session cookie") and the actual role/scope
  values (enum members, string literals) — do not write generic placeholder text when the real
  values are sitting in the code you just read.
- **Hits in multiple categories** → likely mixed; describe both plainly rather than forcing a
  single label.
- **No hits in any category** → `Open / internal only`, but only after actually searching — never
  write this as a lazy default when the search wasn't run.

Present the inferred model with the 2-3 supporting file references and **wait for confirmation**
before writing to `security.md` (same reasoning as Step 5 — this feeds every future security
review).

## 7. Write Everything

Escape `&`, `\`, and `|` in any substituted value before using it in a `sed` replacement (all
three are special in `sed`'s replacement string and corrupt the substitution if a path contains
them):

```bash
_esc() { echo "$1" | sed 's|[\\&|]|\\&|g'; }
```

**`.claude/wiki-project.env`:**
```bash
sed -i.bak "s|^BACKEND_DIR=.*|BACKEND_DIR=$(_esc "$BACKEND_PATH")|"   .claude/wiki-project.env
sed -i.bak "s|^FRONTEND_DIR=.*|FRONTEND_DIR=$(_esc "$FRONTEND_PATH")|" .claude/wiki-project.env
[[ -n "${OPS_PATH:-}" ]] && sed -i.bak "s|^OPS_DIR=.*|OPS_DIR=$(_esc "$OPS_PATH")|" .claude/wiki-project.env
rm -f .claude/wiki-project.env.bak
```

**Root `CLAUDE.md`:**
```bash
sed -i.bak "s|your-backend-repo|$(_esc "$BACKEND_PATH")|g"  CLAUDE.md
sed -i.bak "s|your-frontend-repo|$(_esc "$FRONTEND_PATH")|g" CLAUDE.md
rm -f CLAUDE.md.bak
```

**Rule files:**
```bash
for f in .claude/rules/backend-*.md; do
  [[ -f "$f" ]] || continue
  sed -i.bak "s|your-backend-repo|$(_esc "$BACKEND_PATH")|g" "$f"
  [[ "$BACKEND_EXT" != "java" ]] && sed -i.bak "s|\*\*/\*\.java|**/*.$(_esc "$BACKEND_EXT")|g" "$f"
  rm -f "$f.bak"
done

for f in .claude/rules/frontend-*.md; do
  [[ -f "$f" ]] || continue
  sed -i.bak "s|your-frontend-repo|$(_esc "$FRONTEND_PATH")|g" "$f"
  rm -f "$f.bak"
done

sed -i.bak \
  -e "s|your-backend-repo|$(_esc "$BACKEND_PATH")|g" \
  -e "s|your-frontend-repo|$(_esc "$FRONTEND_PATH")|g" \
  -e "s|{AUTH_MODEL}|$(_esc "$AUTH_MODEL")|g" \
  -e "s|{AUTH_MECHANISM}|$(_esc "$AUTH_MECHANISM")|g" \
  -e "s|{ACCESS_PRIMITIVE}|$(_esc "$ACCESS_PRIMITIVE")|g" \
  -e "s|{ROLES_OR_SCOPES}|$(_esc "$ROLES_OR_SCOPES")|g" \
  -e "s|{FRONTEND_AUTH_NOTE}|$(_esc "$FRONTEND_AUTH_NOTE")|g" \
  .claude/rules/security.md
rm -f .claude/rules/security.md.bak

if [[ -n "${OPS_PATH:-}" ]] && [[ -f ".claude/rules/ops-infra.md" ]]; then
  sed -i.bak "s|your-ops-repo|$(_esc "$OPS_PATH")|g" .claude/rules/ops-infra.md
  rm -f .claude/rules/ops-infra.md.bak
fi
```

If no ops/infra directory was found, leave `ops-infra.md` untouched — its existing
`your-ops-repo`/`CUSTOMIZE` placeholder is correct as "nothing detected yet."

**`receiving-code-review` skill** (permanently-dead placeholder today — nothing has ever filled
this one in):
```bash
sed -i.bak \
  -e "s|<your-backend-repo>|$(_esc "$BACKEND_PATH")|g" \
  -e "s|<your-frontend-repo>|$(_esc "$FRONTEND_PATH")|g" \
  .claude/skills/receiving-code-review/SKILL.md
rm -f .claude/skills/receiving-code-review/SKILL.md.bak
```

**`pr-review-backend`/`pr-review-frontend` skills** — three real, currently-unfilled spots each:
```bash
sed -i.bak \
  -e "s|default to the backend repo <!-- CUSTOMIZE: your default backend repo name and org -->|default to \`$GH_ORG/$GH_REPO\`|" \
  -e "s|pattern: \`TICKET-\\\\d+\`|pattern: \`${TICKET_PREFIX}-\\\\d+\`|" \
  -e "s|\`backend/CLAUDE.md\` (if accessible)|\`$(_esc "$BACKEND_PATH")/CLAUDE.md\` (if accessible)|" \
  .claude/skills/pr-review-backend/SKILL.md
rm -f .claude/skills/pr-review-backend/SKILL.md.bak

sed -i.bak \
  -e "s|default to the frontend repo <!-- CUSTOMIZE: your default frontend repo name and org -->|default to \`$GH_ORG/$GH_REPO\`|" \
  -e "s|pattern: \`TICKET-\\\\d+\`|pattern: \`${TICKET_PREFIX}-\\\\d+\`|" \
  -e "s|\`frontend/CLAUDE.md\` (if accessible)|\`$(_esc "$FRONTEND_PATH")/CLAUDE.md\` (if accessible)|" \
  .claude/skills/pr-review-frontend/SKILL.md
rm -f .claude/skills/pr-review-frontend/SKILL.md.bak
```
(`$GH_ORG`/`$GH_REPO` split from `GITHUB_REPO` in `.claude/wiki-project.env`; `$TICKET_PREFIX`
from `LINEAR_PROJECT_ID` in the same file, trailing `-` trimmed.)

**Copy `CLAUDE.md` templates into the discovered/scaffolded dirs** — `mkdir -p` first (the
directory may not exist yet, especially right after Step 4's scaffold), skip if a `CLAUDE.md`
is already there:
```bash
_fill_template() {
  local src="$1" dest="$2"
  [[ -f "$src" ]] || return
  if [[ ! -f "$dest" ]]; then
    mkdir -p "$(dirname "$dest")"
    cp "$src" "$dest"
    sed -i.bak "s|\[PROJECT NAME\]|$WIKI_PROJECT_NAME|g" "$dest"
    sed -i.bak "s|TICKET-123|${TICKET_PREFIX}-123|g" "$dest"
    rm -f "$dest.bak"
  fi
}
_fill_template "docs/templates/backend-claude-md.md"  "$BACKEND_PATH/CLAUDE.md"
_fill_template "docs/templates/frontend-claude-md.md" "$FRONTEND_PATH/CLAUDE.md"
```

## 8. Report

Tell the user:
- What was detected (or scaffolded) for backend, frontend, and ops/infra, and each side's language
- The inferred auth model and the evidence for it (or that it's still undetermined, in the
  empty-repo path)
- Which files were updated
- That narrative prose (Architecture, Security & Auth sections in each `CLAUDE.md`) still needs a
  human — this skill fills in mechanics (paths, language, auth model), not prose
- This was a one-time step — running it again will stop at the Step 1 guard

---

## Rules

- Never invent a `GITHUB_REPO` in Step 0, and never treat a detected submodule or `origin` as
  confirmed without asking — always surface what was found (submodule URL, or workspace `origin`)
  and get the user's confirmation, or ask them directly if neither resolves.
- Never run `git submodule add` in Step 0 without the user confirming the URL first — it's a
  real, if easily-reverted, git operation.
- Never write `Open / internal only` as a lazy default — only after actually running Step 6's
  grep and finding nothing.
- Never skip the confirmation pauses in Steps 4, 5, and 6 — layout and auth-model mistakes here
  propagate into every future PR review.
- Never guess at backend/frontend/ops paths without evidence (Step 5) — if the signals are
  ambiguous or absent, ask the user rather than picking one.
- Never re-run past the Step 1 guard without the user clearing it (editing
  `.claude/wiki-project.env` directly) first — this is a one-time onboarding step, not a
  recurring one.
- Only push to the project's own repo (Step 4) with the user's explicit go-ahead — it's a
  different remote than the starter kit's own, and a visible, shared-state action.
- Leave `ops-infra.md` untouched if no ops/infra directory was found — its placeholder already
  correctly reads as "nothing detected."
