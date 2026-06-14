# Mac → Google TV Ambient-mode Photo Rotator

A macOS CLI that puts random photos from your Apple Photos library onto your Sony Bravia /
Google TV **Ambient mode** screensaver, rotating the selection on each run — API-driven, no
Google Drive desktop app.

> **Status: Phase 0 — validation gate.** Before building the full tool we are testing the
> project's #1 risk: whether an album *created by this app* via the Google Photos Library API
> actually shows up in the TV's Ambient-mode → Google Photos album picker. Research suggests
> ~70% chance it does **not**, so we validate cheaply first. See **[SETUP.md](SETUP.md)**.

## The approach (verified against the live API, June 2026)

- Upload a curated pool of photos to **one** Google Photos album **once**, then reshuffle
  *album membership* each run — never re-upload. (The API cannot delete media items, only
  remove them from an album, so re-uploading would balloon storage permanently.)
- Surviving scopes: `photoslibrary.appendonly` (upload / create / add),
  `photoslibrary.edit.appcreateddata` (remove from album),
  `photoslibrary.readonly.appcreateddata` (read app-created items).

## If validation fails

Pivot to a local path: write the random subset to a **USB stick** or serve it to a Google-TV
screensaver app (Carousel / nFolio). The Apple Photos selection + downscale logic is reused.

## Layout (current)

```
validate.py     Phase 0 throwaway spike (OAuth + create album + upload). See SETUP.md.
SETUP.md        Step-by-step gating instructions (TV test + Google Cloud OAuth client).
.venv/          uv-managed Python 3.12 environment.
```

## Dev environment

```bash
uv venv --python 3.12
uv pip install google-auth google-auth-oauthlib requests
```
