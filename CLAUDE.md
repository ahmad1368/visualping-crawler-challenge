# Project Architecture & Engineering Guidelines

## Build & Test Commands
- Run pytest suite: `pytest`
- Run single test file: `pytest tests/test_filename.py`
- Lint code: `flake8` or `black --check .`

## Code Style & Architecture Constraints
- **Language**: 100% English code, comments, and docstrings.
- **Pattern**: Asynchronous I/O (`httpx`, `asyncio`), SOLID principles, decoupled modules.
- **Type Safety**: Strictly use Python Type Hints.
- **Error Handling**: Graceful error catching with logging (no raw `print()` calls).
- **Atomic Operations**: File writes to `local_data/results.json` must be atomic.

## Workflow Rules for AI Interaction
1. **Test-Driven First**: Always draft or update tests alongside module implementations.
2. **Issue Traceability**: Before resolving an issue, check its criteria from GitHub and commit with reference (e.g., `feat: implement config module (#1)`).
3. **Clean Commits**: Make concise, modular commits after completing each logical issue.
## Custom Workflows & Slash Commands

### Command: `/next-issue`
When the user types `/next-issue`, execute the following fully automated sequence:

1. **Fetch Next Issue**:
   - Query GitHub CLI for the lowest-numbered open issue: `gh issue list --state open --limit 1 --json number,title,body`
   - Extract the Issue Number and Title.

2. **Branch Creation**:
   - Ensure the repository is on `staging` or `main` and fully updated (`git checkout staging && git pull`).
   - Create and checkout a new feature branch: `git checkout -b feature/issue-<number>`.

3. **Implementation & Testing**:
   - Read the acceptance criteria and engineering principles from the fetched issue body.
   - Implement the required module code and create corresponding unit tests under `tests/`.
   - Run `pytest` to verify implementation. If any test fails, fix it iteratively until 100% pass.

4. **Commit & Push**:
   - Stage modified files (`git add .`).
   - Create a clean git commit following Conventional Commits: `feat: <issue title> (#<number>)`.
   - Push the branch to remote: `git push origin feature/issue-<number>`.

5. **Pull Request Creation**:
   - Create a PR targeting the `staging` branch using GitHub CLI:
     `gh pr create --base staging --head feature/issue-<number> --title "feat: <issue title> (#<number>)" --body "Closes #<number>"`
   - Output the created PR URL and a short summary to the user.