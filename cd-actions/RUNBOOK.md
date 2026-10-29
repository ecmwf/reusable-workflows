# CD v2 runbook

What to do when a CD v2 release (`main-cd.yml`, `cd-*.yml`) goes wrong. CD v2 is being replaced by v3, so this covers recovery only.

## Stop all CD

- **GitHub:** an org admin sets the organisation variable `CD_KILL_SWITCH` to `on`, and `CD_KILL_SWITCH_REASON` to a short reason. Every CD workflow then fails in its first job. Delete the variable, or set it to anything else, to resume.
- **HPC only:** create `$HOME/.cd-locks/DISABLED` as the CD HPC user (or `<lock_root>/DISABLED` if a caller sets `lock_root`). Put the reason in the file. `hpc-sync-tag` jobs then fail before touching `modulemgr`. Remove the file to resume.

The variable is not created by default; both switches are off until someone turns them on.

## Re-run failed jobs

- Use **Re-run failed jobs** on the caller's run. Jobs that succeeded are not repeated.
- HPC builds install straight into `/usr/local/apps/<module>/<version>[/<FAMILY>/<maj.min>]`. A re-run makes the tree writable again and installs over it, so a re-run repairs a half-installed module.
- `hpc-sync-tag` is safe to re-run. Sync and tag are idempotent.
- Nexus uploads are not always idempotent. See "Duplicate Nexus artifacts" below.

## Stale HPC sync/tag lock

`hpc-sync-tag` holds `$HOME/.cd-locks/modulemgr` while it runs `modulemgr` and `software-sync`. Jobs wait up to `lock_timeout` (30 min), and break a lock older than `lock_stale_minutes` (120 min) on their own.

To clear it by hand:

1. `cat $HOME/.cd-locks/modulemgr/owner` shows the repo, run URL, job, host, pid and start time.
2. Check that the owner is gone: the run URL shows it finished or was cancelled, and `squeue -u $USER` or `squeue -j <jobid>` shows no SLURM job for it.
3. `rm -rf $HOME/.cd-locks/modulemgr`.

Never remove a lock whose owner is still running. Two concurrent `modulemgr` runs can corrupt the module tree.

## Half-installed module

Signs: the module directory exists, but files are missing or still writable (`finalize` runs `chmod -R a-w` last).

- **Preferred:** re-run the failed HPC build job. It installs over the same prefix.
- **If no re-run is possible:** ask the HPC admins to remove `/usr/local/apps/<module>/<version>`, then run the release again.
- Do not tag (`modulemgr tag`) a module that is half-installed.

## A tag release cancelled during the HPC install

- A cancelled run leaves a half-installed module (see above), and possibly a stale lock if it was cancelled during sync/tag (see "Stale HPC sync/tag lock").
- Re-run the cancelled jobs from the same run. Do not push the tag again; tags are immutable.
- Check that `hpc-sync-tag` ran afterwards. It needs every build to have succeeded.

## Manual module tag

When sync worked but tagging failed or was skipped:

```bash
module load modulemgr
modulemgr -m "aa,ab,ac,ad" -f -v tag "<module>" "<version>" "<tag, e.g. new>"
```

Take the lock first (`mkdir $HOME/.cd-locks/modulemgr`, write who you are to `owner`, and `rm -rf` it afterwards), so you do not race a CD job.

## Duplicate Nexus artifacts

- System packages: the rpm upload is a `PUT`, and the deb upload is a multipart `POST`. When the version is already there, Nexus either overwrites it or answers `400`, depending on the repository's redeploy policy. If a re-run fails with `400` and the package already on Nexus is the right one, the upload has already been done.
- If a wrong package was uploaded, a Nexus admin deletes that component, then re-run the upload job.
- Do not re-upload a release under the same version with different content. Bump the version instead.

## Conda re-index

Conda packages go to **test** Nexus on purpose until production conda repositories exist.

Each conda upload dispatches `conda-index-lock.yml` in this repository. It uploads the packages and rebuilds the channel index, one run at a time. If an index run failed, or the index looks wrong:

1. Find the caller run id and the artifact name (`<caller run id>-<build name>`) in the caller's "Acquire lock and upload to Nexus" step.
2. Dispatch the lock workflow again at the same ref the caller used (`v2` normally):

   ```bash
   gh workflow run conda-index-lock.yml -R ecmwf/reusable-workflows --ref v2 \
     -f channel=test \
     -f package_artifact_name=<caller run id>-<build name> \
     -f caller_run_id=<caller run id> \
     -f caller_repo=ecmwf/<repo> \
     -f dispatch_id=manual-$(date +%s)
   ```

3. The caller's artifact must still exist; artifacts are kept for 90 days.

The lock workflow reads the Nexus credentials from org secrets. Never pass a credential as a dispatch input: dispatch inputs are stored with the run.
