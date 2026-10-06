# Base CV starter

This folder contains fictional example data for a software-and-systems engineering candidate. It is a starting point only; it does **not** describe a real person and must be fully replaced with your own accurate information.

## Use it in the application

After running the setup command, copy the example into your private local profile:

```bash
python scripts/setup.py init-profile
```

The command refuses to overwrite an existing profile. To replace a profile deliberately, use:

```bash
python scripts/setup.py init-profile --force
```

You can then edit the profile from the dashboard at `http://127.0.0.1:5000/dashboard`, or edit `data/candidate_profile.json` directly.

## Accuracy rules

- Replace every placeholder in the personal section.
- Keep only experience, education, metrics, projects, and skills you can support.
- Mark a studied or introductory skill as `FAMILIARITY`, not `VERIFIED`.
- Delete unused sample entries instead of adapting them into inaccurate claims.

`data/candidate_profile.json` is private and ignored by Git. The example in this folder is intentionally public, fictional, and safe to share.
