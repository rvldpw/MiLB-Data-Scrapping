# Deploying Code.gs

This is the Google Sheets side of the databank — a Web App that the GitHub Action
talks to over HTTP. It lives *inside* the Google Sheet itself, not in this repo's
CI, so it needs to be pasted in and deployed by hand once, and re-deployed by hand
whenever `Code.gs` changes.

## First-time setup

1. Create (or open) the Google Sheet you want as your databank.
2. **Extensions → Apps Script.**
3. Delete whatever's in the default `Code.gs` and paste in this folder's `Code.gs`.
4. **Project Settings (gear icon) → Script Properties → Add script property:**
   - Name: `SHARED_SECRET`
   - Value: any long random string — e.g. generate one with `openssl rand -hex 32`.
     This is what the GitHub Action authenticates with. Never hardcode it in the
     script itself.
5. **Deploy → New deployment:**
   - Type: **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone**
6. Click **Deploy**, then copy the URL ending in `/exec`.
7. In your GitHub repo: **Settings → Secrets and variables → Actions**, add:
   - `APPS_SCRIPT_URL` = the `/exec` URL from step 6
   - `APPS_SCRIPT_SECRET` = the same value you set in step 4

That's it. The Sheet is otherwise empty at this point — every tab (`Batter`,
`Pitcher`, `Catcher`, `BatterGameLog`, `PitcherGameLog`, and the `_SyncState*`
bookkeeping tabs) gets created automatically the first time the Action pushes
data. Nothing to build by hand.

## Updating after a code change

Saving the file in the Apps Script editor is **not enough** — a deployed Web App
keeps serving whatever code was live at its last deployment, even after you save
new changes. You have to explicitly redeploy:

1. Paste the updated `Code.gs` into the Apps Script editor. Save (Ctrl/Cmd+S).
2. **Deploy → Manage deployments.**
3. Click the pencil (edit) icon on the existing deployment.
4. **Version → New version → Deploy.**

This keeps the same `/exec` URL, so `APPS_SCRIPT_URL` in GitHub doesn't need to
change. Only pick **"New deployment"** instead of editing the existing one if you
specifically want a fresh URL (e.g. rotating access) — in that case, update the
`APPS_SCRIPT_URL` secret in GitHub afterward too, or the Action will keep hitting
the old (now-stale) URL.

## Sanity-checking a deployment

Paste the `/exec` URL into a browser with `?action=state&secret=YOUR_SECRET&kind=season`
appended. You should get back JSON like `{"ok":true,"completed_seasons":[]}` —
not an HTML login/error page. An HTML response usually means "Who has access" isn't
set to **Anyone**, or you're not looking at the latest deployment.
