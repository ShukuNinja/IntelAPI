# Apply the M0 completion pack

This pack contains documentation/status refreshes, a `.gitignore` update, a correction to a stale API-client comment, and a guarded cleanup script for already tracked generated artifacts. It does not implement M1 product features.

## Files in this pack

- `.gitignore` â€” ignore nested Python bytecode/cache, package metadata, build outputs, and local secrets.
- `README.md` â€” update the top-level project status to reflect the post-merge implementation.
- `docs/IMPLEMENTATION_STATUS.md` â€” replace the stale October 16 snapshot with the October 19 source audit.
- `docs/M0_BASELINE_AUDIT.md` â€” add the source inventory, observed gaps, decisions, and verification checklist.
- `docs/LOCAL_RUNBOOK.md` â€” align commands and warnings with the current Compose/API/frontend setup.
- `docs/README.md` â€” register the new audit record and refresh documentation metadata.
- `apps/web/src/lib/apiClient.ts` â€” correct the obsolete comment that said the backend was not implemented.
- `scripts/cleanup_tracked_artifacts.ps1` â€” list and, after explicit confirmation, remove tracked `__pycache__`, bytecode, and `*.egg-info` artifacts.

## Safe application steps

1. Refresh your local checkout to the latest `main` and confirm `git status --short` is clean.
2. Copy the pack's files into the matching paths in your repository, preserving the directory structure. Review the diffs before staging.
3. Run the cleanup script from the repository root:

   ```powershell
   .\scripts\cleanup_tracked_artifacts.ps1
   ```

   It lists target files and requires you to type `REMOVE`. If you cancel, no deletions occur. The updated `.gitignore` alone will not untrack files already committed.

4. Run the verification commands in `docs/M0_BASELINE_AUDIT.md` and record actual results. Do not mark checks as passed if you did not run them.
5. Review the complete diff:

   ```powershell
   git status --short
   git diff --check
   git diff --stat
   git diff
   ```

6. Commit the M0 baseline/documentation cleanup on a feature branch and open a PR. Do not push directly to `main`.

## Important limits

- The audit snapshot identifier came from the uploaded archive metadata. After applying the pack, record the actual result of `git rev-parse HEAD` from your local checkout in the audit document if it differs.
- The maintainer reported that CI passed after the feature merge; this pack does not independently query GitHub Actions.
- The API URL strategy is documented as an integration gap, not fixed by this pack. Implement and test the selected URL/proxy strategy in M1 before connecting real frontend workflows.
