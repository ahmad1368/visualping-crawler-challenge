---
description: Fully automated workflow to fetch the next open issue, implement, test, and open a PR.
---

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

---

### Command: `/build-index`
Create or update `index.html` in the root directory to display crawler status and results on Vercel:
1. Generate an index.html file with a modern TailwindCSS dashboard template.
2. Include placeholders/sections for Issue Status, GitHub Workflows, and Crawler Execution Logs.
3. Save the file directly at `./index.html`.