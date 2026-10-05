# Publish after local verification

The intended repository name is **abyss-medallion**, on `main`. This package does not publish it automatically.

From WSL, run `./demo` and inspect `runs/index.html`. Generated `runs/` and `scratch/` are ignored by Git. Then, with GitHub CLI installed and authenticated:

```bash
git init -b main
git add .
git commit -m "Add synthetic Medallion pipeline with executable readiness controls"
gh repo create malex4hire/abyss-medallion --public --source=. --remote=origin --push
```

If you create the empty repository in the GitHub UI instead, use Git's `remote add` and `push` commands for that repository. Avoid creating a second README in the UI; this package already contains one.

## Matching profile update

[Draft profile PR #6](https://github.com/malex4hire/malex4hire/pull/6) adds the project card to `profile.yaml` and renders the profile README using the existing renderer. The positioning and existing cards are unchanged. The local package also contains the updated profile files and an isolated `card.yaml` block.

After publishing the project, confirm GitHub Actions passes. Then mark the profile PR ready for review and let its live account/link/binding checks pass before merging. It intentionally remains a draft while its target repository is unpublished.

The three bindings are `./demo`, `test_defective_batch_blocks_release_and_conserves_every_row`, and `docs/CONTROL-REGISTER.md`. Keep those bindings current if you rename files or gates during local review.
