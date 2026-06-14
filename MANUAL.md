# TV Photos — User Manual

Puts random photos from your Apple Photos libraries onto your Google TV / Sony Bravia
**Ambient mode** screensaver, and shuffles them to a fresh set every time you run it.

---

## Everyday use (the easy way)

1. **Plug in / mount the external drive** that holds your photo libraries.
2. **Double-click `TV Photos.app`.** A Terminal window opens and shows a progress bar:
   ```
   uploading [████████████░░░░░░░░░░░░]  50% 500/1000 | elapsed 11:40 | ETA 11:40
   ```
3. When it says **“Finished. You can close this window.”**, your TV album has a new random
   set. Open Ambient mode on the TV to enjoy it.

> First launch only: macOS may say the app is from an unidentified developer — **right-click
> the app → Open → Open**. It will also ask to **control Terminal** — click **OK**. If a
> browser window asks you to sign in to Google, approve it (your login occasionally needs
> refreshing).

A full run scans your libraries (a few minutes) and uploads ~1000 photos, so it can take
20–30 minutes the first time. Later runs are faster for photos already uploaded.

---

## What the summary means

```
Done. pool=33255 selected=1000 reused=20 uploaded=980 failed=0 album=+1000/-20 -> 1000
```
- **pool** — eligible photos found across all your libraries.
- **selected** — how many were chosen for this rotation (your `count` setting).
- **reused** — already in Google Photos from a past run (not re-uploaded).
- **uploaded** — newly uploaded this run.
- **failed** — uploads/creations that didn’t succeed (0 is good).
- **album +X/-Y -> N** — added X, removed Y; the album now holds N photos.

---

## Settings

All settings live in a text file:
`~/.config/tv-photos/config.toml`

```toml
[source]
libraries = ["/Volumes/HDD 4TB/Artur/Photos Library.photoslibrary", ...]
exclude_screenshots = true   # skip screenshots

[quality]
min_width = 1000             # ignore images narrower than this (px)
upload_max_long_edge = 3840  # shrink big photos to this on upload (keeps storage small)
jpeg_quality = 85

[rotation]
album_title = "TV Rotation"
count = 1000                 # how many photos the album holds each run

[behavior]
dry_run = false              # true = preview only, never uploads
```

Edit it in any text editor and save. To **add/remove a photo library**, edit the `libraries`
list. To **change how many photos** rotate, change `count`.

---

## Command line (optional)

```
./.venv/bin/python -m tv_photos run            # full rotation: scan libraries + upload new + reshuffle
./.venv/bin/python -m tv_photos run --reuse    # FAST reshuffle from already-uploaded photos (no scan, no upload)
./.venv/bin/python -m tv_photos run --dry-run  # preview: scan + plan, NO uploads
./.venv/bin/python -m tv_photos run --count 20 # a small run (e.g. to test)
./.venv/bin/python -m tv_photos status         # show album, totals, libraries
./.venv/bin/python -m tv_photos init           # one-time: sign in + create album
```

### Two ways to rotate

- **Full run** (`run`, and what `TV Photos.app` does) — scans your libraries (~5 min) and
  uploads freshly-chosen photos. Adds variety but uploads ~1000 new photos each time
  (permanent storage grows).
- **Quick reshuffle** (`run --reuse`) — picks a new random set from photos you've **already
  uploaded**; no scan, no upload, finishes in seconds, no extra storage. Best for day-to-day
  “give me a different mix.” Run a **full run** occasionally when you want new content in the pool.

---

## TV setup (one time)

On the TV: **Settings → System → Ambient mode → Google Photos**, sign in with the same Google
account, and select the **“TV Rotation”** album. After that, just rerun the app whenever you
want fresh photos.

---

## Good to know

- **Uploads are permanent.** The Google Photos API can’t delete photos — it can only add/remove
  them from the album. Every distinct photo ever shown stays in your Google Photos library and
  counts toward your storage. To free space, delete them in the Google Photos app yourself.
- **Storage grows** each run (you chose fresh-random). Check usage at photos.google.com.
- **Sign-in occasionally expires** (Google test-mode tokens). If a browser opens asking you to
  sign in, just approve it.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| “No eligible photos found” | The external drive isn’t mounted, or the library paths in config are wrong. |
| App won’t open (“unidentified developer”) | Right-click the app → **Open** → **Open**. |
| Nothing changes on the TV | Re-open Ambient mode; a TV restart forces a sync. Confirm the album is “TV Rotation”. |
| Browser keeps asking to sign in | Normal occasionally; approve it. If it persists, run `init` again. |
| Run is slow | Scanning large libraries off an external HDD takes minutes; the progress bar shows the ETA for the upload phase. |
