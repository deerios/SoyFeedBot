# Setup

## 1. Create the Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**.
2. Under **Bot**, click **Reset Token** and copy it. This is your `DISCORD_TOKEN`.
3. No privileged intents are required (the bot only sends messages).
4. Under **OAuth2 → URL Generator**, select scope `bot`, permission `Send Messages`, open the generated URL, and invite it to your server.
5. In Discord, enable Developer Mode (User Settings → Advanced), right-click the target channel → **Copy Channel ID**. This is your `DISCORD_CHANNEL_ID`.

## 2. Get a YouTube Data API key

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create or select a project.
2. **APIs & Services → Library** → enable **YouTube Data API v3**.
3. **APIs & Services → Credentials → Create Credentials → API key**. This is your `YOUTUBE_API_KEY`.
4. Optionally restrict the key to the YouTube Data API v3.

## 3. Add repo secrets

In the repo: **Settings → Secrets and variables → Actions → New repository secret**. Add:

- `DISCORD_TOKEN`
- `DISCORD_CHANNEL_ID`
- `YOUTUBE_API_KEY`

## 4. Configure the channel list

Edit `YOUTUBE_CHANNELS` in `bot.py` with the `@handle` (or `UC...` channel ID) of each creator to track.

## 5. Create a fine-grained GitHub token (for external dispatch)

1. GitHub → **Settings → Developer settings → Fine-grained tokens → Generate new token**.
2. Resource owner: your account. Repository access: **only this repository** (`SoyFeedBot`).
3. Permissions → Repository permissions → **Actions: Read and write**.
4. Generate and copy the token. You won't see it again.

## 6. Set up cron-job.com to trigger the workflow

1. Create an account at [cron-job.com](https://cron-job.com).
2. Create a new cronjob:
   - **URL**: `https://api.github.com/repos/deerios/SoyFeedBot/actions/workflows/check.yml/dispatches`
   - **Method**: `POST`
   - **Schedule**: every 5 minutes
   - **Headers**:
     - `Authorization: Bearer YOUR_FINE_GRAINED_TOKEN`
     - `Accept: application/vnd.github+json`
     - `Content-Type: application/json`
   - **Body**: `{"ref":"main"}`
3. Save and enable the job.

A successful dispatch returns HTTP `204` with no body. Check the **Actions** tab in the repo to confirm runs are firing.

## 7. (Optional) Run locally for testing

```bash
pip install -r requirements.txt
DISCORD_TOKEN=... DISCORD_CHANNEL_ID=... YOUTUBE_API_KEY=... python bot.py
```

## Notes

- The workflow has no `schedule` trigger by design — cron-job.com is the sole trigger (see step 6).
- `youtube_state.json` is committed back to `main` after each run by the workflow to track already-seen video IDs; don't edit it manually while the job is active.
- YouTube Data API default quota is 10,000 units/day. At a 5-minute interval this supports roughly 34 channels before hitting the cap (see repo discussion for the math).
