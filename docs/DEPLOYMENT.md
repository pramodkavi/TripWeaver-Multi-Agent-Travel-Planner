# Deployment — Hugging Face Spaces + GitHub Actions

TripWeaver deploys as a single **Docker Space** on Hugging Face: one container
runs the two MCP servers, the FastAPI backend, and the Gradio UI, exposing only
the Gradio port (7860). A GitHub Actions workflow mirrors this repo to the Space
on every push to `main`; **Hugging Face builds the image remotely**, so you do
not need Docker installed anywhere.

```
push to main ──▶ GitHub Actions (.github/workflows/deploy-hf.yml)
                      │  git push --force to the Space repo
                      ▼
              Hugging Face Space (Docker)  ── builds image, runs start.sh ──▶ public URL
```

## One-time setup

### 1. Create the Hugging Face Space
1. Sign in at <https://huggingface.co> (free account).
2. **New → Space**. Set:
   - **Owner**: your username (e.g. `pramodkavi`)
   - **Space name**: e.g. `tripweaver`
   - **SDK**: **Docker** (blank template)
   - **Hardware**: CPU basic (free)
3. Create it. Note the URL: `https://huggingface.co/spaces/<user>/tripweaver`.
   The public app will be at `https://<user>-tripweaver.hf.space`.

### 2. Add the app's secret to the Space
In the Space: **Settings → Variables and secrets → New secret**:
- `OPENAI_API_KEY` = your key.
- (Optional) `OPENAI_MODEL`, `TRAVEL_SERVICE_BASE_URL`.

These become environment variables in the container. The app reads them via
`os.getenv`; nothing is committed.

### 3. Create a Hugging Face access token
**Profile → Settings → Access Tokens → New token**, role **Write**. Copy it.

### 4. Add GitHub repository secrets
In GitHub: **Settings → Secrets and variables → Actions → New repository secret**:
- `HF_TOKEN` = the write token from step 3
- `HF_USERNAME` = your Hugging Face username
- `HF_SPACE` = the Space name (e.g. `tripweaver`)

## Deploy

Push to `main` (or run the workflow manually from the **Actions** tab →
*Deploy to Hugging Face Spaces* → *Run workflow*):

```bash
git push origin main
```

GitHub Actions force-pushes the repo to the Space; Hugging Face detects the
`Dockerfile` + the `sdk: docker` header in `README.md`, builds the image, and
runs `start.sh`. Watch progress on the Space's **Logs** tab. First build takes a
few minutes; subsequent builds are cached.

## After the first successful deploy
- Open `https://<user>-tripweaver.hf.space` and test a query.
- Put that URL in the README (**Live demo**) and in the LMS submission form's
  **Deployed Project Link** field.

## How it maps to the container
`start.sh` launches the MCP servers and backend on `localhost` inside the
container, waits for the backend health check, then runs the Gradio UI in the
foreground on port 7860 (the port Hugging Face exposes via `app_port`). Because
everything shares localhost, the default env values already wire the pieces
together — only `OPENAI_API_KEY` must be supplied.

## Troubleshooting
- **Build fails**: check the Space **Logs**; confirm `Dockerfile` and the
  `README.md` header are present at the repo root.
- **App loads but every query errors**: `OPENAI_API_KEY` is missing/invalid in
  the Space secrets (the UI will still load and show a friendly error).
- **Actions job fails on push**: verify `HF_TOKEN` (Write), `HF_USERNAME`,
  `HF_SPACE`, and that the Space already exists.
- **Free Space sleeps** after ~48h idle; the next visit wakes it (~30s).
