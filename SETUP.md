# Phase 0 — Validation gate setup

We are NOT building the full tool yet. First we prove the risky assumption on your
actual TV: **does an album created by this app (via the Google Photos API) appear in
the TV's Ambient-mode → Google Photos album picker?** Research says ~70% chance it does
not. The steps below are the cheapest way to find out before investing.

There are two manual things only you can do (0a and 0b), then we run the spike (0c),
then you check the TV (0d).

---

## 0a. Manual TV test (do this first — ~10 min, no code)

This proves the Google Photos screensaver path even exists on your TV.

1. On the TV: **Settings → System → Ambient mode** (some menus call it **Screen saver**).
2. Confirm **Google Photos** is an available source, signed in with the **same Google
   account** you'll use for the API.
3. In the Google Photos app or photos.google.com, **manually** create an album, add a few
   photos, then select that album as the ambient source on the TV. Confirm photos appear.

- **If the manual album does NOT show on the TV** → stop. The whole Google Photos direction
  is dead for your TV; we go straight to the USB/local fallback. Tell me.
- **If it works** → continue to 0b.

---

## 0b. Google Cloud project + OAuth Desktop client (~10 min, one-time)

1. Go to <https://console.cloud.google.com/> and create (or pick) a project.
2. **APIs & Services → Library →** search **"Photos Library API"** → **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - User type: **External**
   - Fill the required app name / your email; **Save and continue** through the screens.
   - Publishing status: leave as **Testing**.
   - Under **Test users**, click **Add users** and add your own Google account
     (the same one signed into the TV).
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Desktop app** → Create.
   - Click **Download JSON**.
5. Save that file as **`client_secret.json`** in this project folder
   (`/Users/arturkin/Work/googleDrivePhotoSync/`). It is gitignored — never commit it.

> Note: while the app is in **Testing**, you'll see an "unverified app" screen during
> sign-in — click **Advanced → Go to (app) (unsafe)** to proceed. That's expected for a
> personal tool. (Heads-up for later: Testing-mode refresh tokens can expire after ~7 days;
> fine for this one-time spike, something we'll address before the daily scheduled tool.)

---

## 0c. Run the spike

1. Put 3–5 test photos in a `test_photos/` folder here (or pass paths as arguments).
   HEIC is fine — it's auto-converted to JPEG via macOS `sips`.
2. Run:
   ```bash
   ./.venv/bin/python validate.py
   # or: ./.venv/bin/python validate.py ~/Desktop/a.jpg ~/Desktop/b.heic
   ```
3. A browser opens for Google sign-in (use the TV's account). On success the script
   creates the album **"TV Rotation (API test)"**, uploads the photos into it, and prints
   the new album id.

---

## 0d. The actual test (go / no-go)

On the TV, open **Ambient mode → Google Photos** album picker and look for
**"TV Rotation (API test)"**. Give it a few minutes; a TV restart can force a sync.

- **Album appears** → ✅ the premise holds. We proceed to build the full `tv-photos` CLI.
- **Album missing** → ❌ pivot to the USB/local fallback (write selected photos to USB or
  serve them to a screensaver app like Carousel/nFolio). No Google Photos API.

Report back what you see — that result decides the rest of the project.
