# MarketDawn — setup guide

## 1. Subscribe to Kite Connect (₹500/month) — create an app

1. Go to **https://kite.trade** and log in with your Zerodha (Kite) account.
2. Click **Create new app** (you must create an app to get an API key).
3. **App type: choose `Connect`** — the ₹500/month plan that includes historical candles +
   realtime streaming. The free `Personal` plan does **not** include historical data, which
   MarketDawn needs.
4. Fill in:
   - **App name:** `MarketDawn` (any name)
   - **Redirect URL:** `https://127.0.0.1/` (placeholder is fine — we never place orders)
   - **Postback URL:** leave blank
   - **Description:** personal market analysis
5. **Create**, then confirm the **₹500/month** subscription.
6. Open the created app — you now have your **API key** and **API secret**.

> **About the SEBI static-IP notice on kite.trade:** it applies only to API **orders** from
> 1 Apr 2026. MarketDawn only *reads* data and never places orders, so this does **not**
> apply to us — you can ignore the static-IP step.

## 2. Collect the five secrets

| Secret | Where to find it |
| --- | --- |
| `KITE_API_KEY` | On the app page at kite.trade |
| `KITE_API_SECRET` | On the app page at kite.trade (click to reveal) |
| `KITE_USER_ID` | Your Zerodha client ID, e.g. `AB1234` |
| `KITE_PASSWORD` | Your Kite login password |
| `KITE_TOTP_SECRET` | The **TOTP secret** (base32 string) from your 2FA setup — *not* the 6-digit code. If you set up 2FA with an authenticator app, this is the key shown when you enabled it. If you only have the QR/app, you can re-enable external 2FA in Kite → Settings to reveal the secret. |

### What is the TOTP secret, and how do I get it?

**TOTP** = Time-based One-Time Password. There are **two different things** with similar
names — this is the #1 mix-up:

| | What it looks like | Use it? |
| --- | --- | --- |
| **Live 6-digit code** | `482913` — changes every 30 seconds | ❌ Never store this — it's already expired by the time it's used |
| **Secret key** (what we need) | `JBSW Y3DP EHPK 3PXP` — a long fixed base32 string, 16–32 letters/digits, shown **once** when you set up 2FA | ✅ This is `KITE_TOTP_SECRET` |

MarketDawn uses the fixed **secret key** to generate valid 6-digit codes itself, on demand,
so it can log in to Kite unattended each morning.

How to get it on Zerodha Kite:
1. Log in to **https://kite.zerodha.com** → click your profile (top-right) → **Settings**.
2. Open **Password & security** → find **External TOTP / App-based 2FA**.
3. Click **Enable** (or **Reset**, if already enabled but you never saved the key).
4. Kite shows a **QR code** and a **secret key** (often labelled "enter this key manually"
   / "setup key"). **Copy that secret key** — that is `KITE_TOTP_SECRET`.
5. Also scan the QR with an authenticator app (Google Authenticator / Authy) so you can
   still log in manually.

If you already use app-based 2FA but didn't save the key, just **Reset TOTP** in step 3 —
Kite will show a fresh QR + secret key to copy.

## 3. Store the secrets ENCRYPTED (no plaintext file)

Secrets are **not** kept in `.env`. Instead, run the secure setup command — it prompts for
each value with hidden input and saves it **encrypted in Windows Credential Manager**
(per-user, OS-encrypted). Nothing is written to disk in plaintext or committed to git.

```
.venv\Scripts\activate
python -m core.security.setup_credentials
```

- It asks for each secret one at a time (typing is hidden). Press Enter to skip an optional one.
- Check what's stored at any time (values are masked, never shown in full):

```
python -m core.security.setup_credentials --status
```

> Tell me once the required Kite secrets show ✓ and I'll run the data-accuracy gate to
> confirm every source is correct before building any signals on it.

## 4. Telegram alerts

1. In Telegram, message **@BotFather** → send `/newbot` → follow the prompts (pick a name
   and a username ending in `bot`) → it replies with a **bot token**
   (looks like `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
2. Search for your new bot by its username and send it **any message** (e.g. "hi") — this
   lets it know your chat, so it can message you back.
3. Run the secure setup and paste the token when prompted for `TELEGRAM_BOT_TOKEN`:
   ```
   .venv\Scripts\python.exe -m core.security.setup_credentials
   ```
4. To get your **chat id** for `TELEGRAM_CHAT_ID`, run:
   ```
   .venv\Scripts\python.exe -m core.alerts.get_chat_id
   ```
   (after step 2 — the bot needs at least one message from you first).
