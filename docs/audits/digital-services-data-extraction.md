# Digital Services Data Extraction Audit

**Created:** 2026-03-01
**Issue:** #21
**Source:** Password manager URL export (~150 entries)

After deduplicating and filtering out defunct services, internal corporate systems, and one-time transaction pages, here are the services worth extracting data from, grouped by priority.

---

## Tier 1 — High Value (rich personal history, act on these)

### Last.fm — Listening History

**Why it matters:** Years or decades of scrobbled tracks with exact timestamps. This is a complete record of your music taste evolution. No other source has this data — once the account is gone, it's gone.

**What you get:**
- Every scrobbled track: artist, album, track name, timestamp
- Loved tracks list
- Total play counts per artist/album/track

**How to export:**
- **Web tool:** [lastfm-to-csv](https://benjaminbenben.com/lastfm-to-csv/) — enter username, downloads full history as CSV
- **API:** `user.getRecentTracks` endpoint, paginated (200 tracks/page). Free API key required.
- **CLI tool:** [lastexport](https://github.com/encukou/lastscrape-gui) — Python script, handles pagination

**Format:** CSV (artist, album, track, timestamp) or JSON via API
**Size:** ~10–50 MB for heavy users (tens of thousands of scrobbles)
**Automation:** Scriptable via API. Could add a `scripts/backup/lastfm-export.py` to Plum.

---

### Spotify — Streaming History & Library

**Why it matters:** Your complete music library (saved tracks, playlists) and streaming history. The "extended" export includes lifetime data with millisecond-precision timestamps.

**What you get:**
- **Basic export** (instant): playlists, saved library, search queries, streaming history (last ~1 year)
- **Extended export** (request, ~30 days): full lifetime streaming history including: track URI, timestamp, ms played, reason for start/end, shuffle/offline status

**How to export:**
1. Go to [spotify.com/account/privacy](https://www.spotify.com/account/privacy/)
2. Scroll to "Download your data"
3. Check "Extended streaming history" (this is the valuable one)
4. Click Request Data — wait ~30 days for email

**Format:** JSON files (one per ~10k entries)
**Size:** 50–500 MB depending on listening volume
**Automation:** Manual request only. Library can also be accessed via Spotify Web API (requires OAuth app).

---

### Google — Calendar, Search, Location

**Why it matters:** Calendar events are hard to reconstruct. Location history is a unique life log. Search history reveals research patterns.

**What you get:**
- Calendar: all events, attendees, recurrence rules
- Location History: GPS coordinates with timestamps (Timeline)
- Search History: every Google search query with timestamps
- YouTube: watch history, liked videos, subscriptions, comments
- Chrome: bookmarks, browsing history (if synced)
- Drive/Docs: all files

**How to export:**
1. Go to [takeout.google.com](https://takeout.google.com)
2. Deselect all, then select only what you want (Calendar, Location, Search, YouTube)
3. Choose delivery method (download link vs. Drive/Dropbox)
4. Choose frequency (one-time or scheduled every 2 months)

**Format:** ICS (calendar), JSON (location/search), CSV, HTML
**Size:** Calendar ~1 MB, Location ~100 MB–1 GB, full Takeout with Drive/Photos can be 50+ GB
**Automation:** Can schedule recurring exports. No API for bulk account data.

---

### GitHub — Repos, Stars, Issues, Contributions

**Why it matters:** Repos are already in git, but your stars list, issue discussions, PR reviews, and contribution graph are not. Stars in particular are a curated bookmark list that many people rely on.

**What you get:**
- All repositories (as git bundles)
- Issues and pull requests (with comments)
- Stars (the repos you starred)
- Gists
- SSH keys, GPG keys
- Profile information
- Followers/following

**How to export:**
- **Bulk:** Settings → Account → Export account data → Start export
- **API (granular):** `gh api /user/starred --paginate` for stars, `gh repo list --json` for repos
- **Stars specifically:** `gh api /user/starred --paginate --jq '.[].full_name'`

**Format:** JSON + git bundles in a tar.gz
**Size:** Depends on repo count. Text data ~10–100 MB. Repos can be GBs.
**Automation:** Fully scriptable via `gh` CLI. A `scripts/backup/github-stars.sh` would be simple.

---

### Twitter/X — Tweets, DMs, Bookmarks

**Why it matters:** DMs are private conversations that exist nowhere else. Tweets are a public thought log. Bookmarks are a hidden reading list.

**What you get:**
- All tweets (with media URLs)
- Direct messages (full conversation history)
- Likes, bookmarks
- Followers/following lists
- Profile information
- Ad targeting data

**How to export:**
1. Settings → Your Account → Download an archive of your data
2. Confirm identity (may require phone verification)
3. Wait ~24 hours for archive to generate
4. Download zip file

**Format:** JSON data files + an HTML viewer (`Your archive.html`) that lets you browse locally
**Size:** 10 MB – 1 GB+ depending on media
**Automation:** Manual request only. Twitter API is now paywalled (Basic tier $100/mo).

---

### LinkedIn — Professional Network

**Why it matters:** Your connections list (with dates) is a professional network map. Messages contain job-related conversations. Endorsements/recommendations are social proof.

**What you get:**
- Profile data (work history, education, skills)
- Connections (name, email, company, position, connected date)
- Messages (full inbox)
- Endorsements and recommendations received
- Job applications through LinkedIn
- Articles and posts
- Search history

**How to export:**
1. Settings & Privacy → Data Privacy → Get a copy of your data
2. Select categories (pick all for a complete archive)
3. Request archive — takes ~10 minutes for a fast archive, 24h for full

**Format:** CSV files (one per category)
**Size:** ~5–50 MB
**Automation:** Manual only. LinkedIn API requires company-level OAuth approval.

---

### Steam — Game Library & Playtime

**Why it matters:** Your complete game library with playtime stats is a gaming biography. Purchase history is useful for financial records.

**What you get:**
- Owned games list with playtime (hours per game)
- Achievements per game
- Friends list
- Purchase history (dates, amounts, payment methods)
- Chat history
- Community content (screenshots, reviews, workshop items)

**How to export:**
- **GDPR request:** [help.steampowered.com](https://help.steampowered.com) → Account → Data Related to Your Steam Account → Request
- **API (public data):** `IPlayerService/GetOwnedGames` — gives games + playtime as JSON
- **Purchase history:** Steam → Account Details → View purchase history (HTML page, save manually)

**Format:** JSON (GDPR), JSON (API), HTML (purchase history)
**Size:** ~10–50 MB
**Automation:** API is scriptable for public profile data. GDPR request is manual.

---

### Apple (iCloud) — Photos, Contacts, Health

**Why it matters:** Contacts and health data are critical. Photos may already be synced via iCloud for Windows, but contacts/health are harder to get.

**What you get:**
- iCloud Photos (all photos/videos)
- Contacts (vCards)
- Calendars (ICS)
- Reminders
- Notes
- Health data (workouts, steps, heart rate — if using Apple Watch/iPhone)
- iCloud Drive files

**How to export:**
1. Go to [privacy.apple.com](https://privacy.apple.com)
2. Sign in → Request a copy of your data
3. Select categories
4. Choose file size for splits (up to 25 GB per file)
5. Wait days–weeks depending on data volume

**Format:** VCF (contacts), ICS (calendars), JSON/CSV (health), media files
**Size:** 1 GB – 100+ GB (mainly photos)
**Automation:** Manual only. iCloud for Windows handles photos sync.

---

### Microsoft (Live/Outlook/Skype) — Mail & Chat History

**Why it matters:** Old Skype chat history (pre-Microsoft merger) and Outlook mail may contain important correspondence. Xbox achievements if you game.

**What you get:**
- Outlook/Hotmail email (full mailbox)
- Skype chat history and calls
- OneDrive files
- Xbox profile, achievements, game clips
- Bing search history
- Cortana data
- MSDN/Visual Studio subscription history

**How to export:**
1. Go to [account.microsoft.com/privacy](https://account.microsoft.com/privacy)
2. Click "Download your data"
3. Select categories
4. Submit request — ready within hours to days

**Format:** EML (email), JSON (chat/search), media files
**Size:** Varies widely — email can be GBs
**Automation:** Manual only.

---

## Tier 2 — Medium Value (useful personal data, do when convenient)

| Service | Data Available | Export Method | Format | Notes |
|---------|---------------|---------------|--------|-------|
| **Goodreads** | Books read, ratings, reviews, shelves, reading dates | Settings → Import/Export → Export Library | CSV | Single CSV with all books, ratings, dates. Easy. |
| **Stack Overflow** | Questions, answers, reputation, badges | GDPR export via settings; also [data.stackexchange.com](https://data.stackexchange.com) | JSON / SQL | Your public content is also in the Stack Exchange data dump. |
| **Reddit** | Posts, comments, saved items, upvotes, messages | Settings → Request your data | CSV / JSON | Saved posts are the most useful — often used as bookmarks. |
| **PayPal** | Full transaction history | Activity → Statements → Download | CSV, PDF | Can download per year. Useful for financial records / expense tracking. |
| **Coursera** | Course completions, certificates, grades | Settings → Data; also GDPR request | JSON, PDF (certificates) | Certificates are the main keepsake. |
| **edX** | Course completions, certificates, grades | Account Settings → Download your data | JSON | Similar to Coursera. |
| **Bitbucket** | Repos, issues, PRs, snippets | GDPR export; also `git clone` individual repos | Git bundles, JSON | If you have repos here not mirrored to GitHub, clone them. |
| **WordPress.com** | Blog posts, comments, media | Tools → Export (in WP admin) | WXR (WordPress XML) | Can import into any other WordPress instance. |
| **Runkeeper** | GPS tracks, workouts, distance, pace, calories | Settings → Export Data | GPX, CSV | GPX files are the gold — actual GPS traces of runs. |
| **Twitch** | Watch history, followed channels, subscriptions, chat logs | Settings → Privacy → Download your data | JSON | Followed channels list is most useful for rebuilding preferences. |
| **Kickstarter** | Backed projects, pledges, messages | Settings → Request my data (GDPR) | JSON | Record of all backed projects and pledge amounts. |

---

## Tier 3 — Low Value (niche or limited data, optional)

| Service | Data Available | Export Method | Format | Notes |
|---------|---------------|---------------|--------|-------|
| **Vimeo** | Uploaded videos, likes, watch history | Settings → Privacy → Request data | JSON, video files | Only interesting if you uploaded content. |
| **Patreon** | Creators supported, pledge history, messages | Settings → Privacy → Download your data | JSON | Financial record of who you supported. |
| **Battle.net / Blizzard** | Game data, characters, achievements, friends | [battle.net/account/data](https://account.blizzard.com) → Download your data | JSON | WoW character data if applicable. |
| **World of Tanks** | Battle stats, tanks, achievements | GDPR request via Wargaming support | JSON | Only if you care about preserving game stats. |
| **Imgur** | Uploaded images, albums, comments | Settings → Request your data | JSON, media files | Useful if you uploaded original photos there. |
| **HackerRank** | Solutions, contest scores, badges | No official bulk export; scrape solutions manually | HTML | Solutions are the useful part — your code submissions. |
| **Shadertoy** | Created shaders | No official export; copy from your profile | GLSL source | Only a few entries likely. Copy-paste the shader code. |
| **Freesound** | Uploaded sounds, bookmarks | Profile → download individual files | WAV/MP3 | Only useful if you uploaded original samples. |
| **AliExpress** | Order history | Account → Orders (no bulk export) | HTML / manual | No good export — screenshot or save order pages. |
| **Airbnb** | Trip history, reviews, messages | Settings → Privacy → Request personal data | JSON | Travel history record. |
| **Booking.com** | Booking history | GDPR request | JSON | Similar to Airbnb — travel records. |
| **Docker Hub** | Repos, images, organizations | No bulk export; `docker pull` individual images | Docker images | Only useful if you published images. |
| **PCPartPicker** | Saved builds, parts lists | No export; save manually | HTML | Copy your build lists if you want to keep them. |

---

## Skipped (defunct, corporate, or no useful data)

These appeared in the URL list but aren't worth pursuing:

- **Internal/corporate**: imgtec.com, codeplay.com, qualcomm.com, scedev.net, khronos.org (member portal)
- **Defunct services**: MyOpenID, Desura, Castle Story, Storynexus, Wurm Online forums, The Old Reader, Molyjam, Scrabbin
- **One-time transactions**: Booking.com individual bookings, easyJet, Just Eat individual orders, Shopify checkout, bol.com
- **No extractable data**: Hover (domain registrar), No-IP, Lebara, Telenet, TSB (banking — use bank's own export)
- **Games with minimal data**: Factorio, Picroma (Cube World), Star Citizen, SimCity, Pillars of Eternity, Torment — no meaningful export beyond save files
- **Superseded**: Origin → now EA App; Book Depository → absorbed by Amazon; Skype → folded into Microsoft

---

## Recommended Extraction Order

Start with the irreplaceable data and work down. Items marked "request now" have multi-day wait times — submit them first, then do the instant exports while waiting.

### Phase 1: Submit slow requests (day 1, ~15 minutes)

| # | Action | Wait Time |
|---|--------|-----------|
| 1 | Request **Spotify extended streaming history** | ~30 days |
| 2 | Request **Twitter/X archive** | ~24 hours |
| 3 | Request **Apple iCloud data** | days–weeks |
| 4 | Request **Steam GDPR export** | ~days |
| 5 | Request **Microsoft data export** | hours–days |

### Phase 2: Instant exports (day 1, ~1 hour)

| # | Action | Time |
|---|--------|------|
| 6 | **Last.fm** scrobbles via lastfm-to-csv | 2 min |
| 7 | **Goodreads** CSV export | 30 sec |
| 8 | **Google Takeout** — Calendar + Location + Search + YouTube | 5 min to set up, hours to generate |
| 9 | **GitHub** — `gh api /user/starred --paginate` + account export | 5 min |
| 10 | **LinkedIn** data export (fast archive) | 5 min |
| 11 | **PayPal** transaction CSV per year | 5 min |
| 12 | **Stack Overflow** GDPR request | 2 min |

### Phase 3: Tier 2 services (when convenient)

- Reddit, Coursera, edX, Bitbucket, WordPress, Runkeeper, Twitch, Kickstarter

### Phase 4: Pick up slow requests as they arrive

- Download Spotify, Twitter, Apple, Steam, Microsoft archives as emails arrive

---

## Automation Potential

These exports could become recurring Plum backup scripts:

| Service | Scriptable? | Approach |
|---------|-------------|----------|
| Last.fm | Yes | Python script using Last.fm API with pagination |
| GitHub stars | Yes | `gh api /user/starred --paginate` in a shell script |
| Google Takeout | Partial | Can schedule recurring exports (every 2 months) |
| Goodreads | No | Manual CSV download (no API for this) |
| Spotify library | Partial | OAuth app + Web API for library/playlists (not history) |
| PayPal | No | Manual CSV download per year |

Worth adding to Plum: `scripts/backup/lastfm-export.py` and `scripts/backup/github-stars.sh` as the two easiest wins. These could run on a cron alongside the existing backup infrastructure.

---

## Storage Estimate

| Category | Estimated Size |
|----------|---------------|
| Text data (all JSON/CSV exports combined) | < 1 GB total |
| Google Takeout — Calendar + Location + Search | ~100 MB – 1 GB |
| Google Takeout — with Drive/Photos | 10–100+ GB |
| Apple iCloud export — with Photos | 10–100+ GB |
| Spotify/Last.fm/Steam/LinkedIn/Twitter | < 500 MB combined |
| Media (Vimeo uploads, Imgur, Freesound) | Varies |

**Total without photos/video: ~2–5 GB.** Fits on any drive. The bulk comes from Google Photos or iCloud Photos — if you include those, expect 50–200 GB.

---

## Suggested Storage Layout

```
~/data-exports/
├── lastfm/
│   └── 2026-03-01-scrobbles.csv
├── spotify/
│   ├── basic-export/
│   └── extended-streaming-history/
├── google/
│   ├── calendar/
│   ├── location-history/
│   └── search-history/
├── github/
│   ├── stars.json
│   └── account-export/
├── twitter/
│   └── archive/
├── linkedin/
│   └── 2026-03-export/
├── steam/
│   └── gdpr-export/
├── goodreads/
│   └── goodreads-library.csv
├── paypal/
│   └── transactions-2024.csv
└── misc/
    ├── reddit/
    ├── stackoverflow/
    └── ...
```

Include this directory in your backup strategy (see tech-stack-audit.md § Backup Strategy).

---

*Verify export URLs and methods before acting — services update their privacy dashboards regularly.*
