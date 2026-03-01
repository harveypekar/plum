# Personal Tech Stack Audit

**Created:** 2026-03-01
**Purpose:** Inventory current setup, survey alternatives, and recommend changes.

---

## 1. Current Setup Inventory

### Infrastructure

| Item | Details | Cost |
|------|---------|------|
| VPS | DreamCompute — 2 vCPU, 1GB RAM, 30GB disk | ~€27/mo |
| Domain | 1 domain at Hover | ~$15/yr |
| VPS usage | Static HTML website only | — |

### Local Hardware

| Item | Details |
|------|---------|
| Desktop | AMD 3900XT, RTX 3070Ti, 64GB RAM |
| Storage (internal) | 1TB + 4TB NVMe |
| Storage (external) | 5TB external drive |
| Media | ~1TB photos, ~1TB music, ~3TB+ video |
| Other | Old Raspberry Pis (unused) |
| Backup | None — no redundancy anywhere |

### SaaS & Subscriptions

| Service | Provider | Cost (est.) |
|---------|----------|-------------|
| Email | Proton Mail | ~€5/mo |
| Passwords | LastPass | ~$3/mo |
| Calendar | Google Calendar | Free |
| References | Zotero | Free or ~$6/mo |
| Writing | Overleaf | Free or ~$10/mo |

### Dev Tools

| Tool | Cost |
|------|------|
| VS Code | Free |
| Claude Code (Max plan) | $100–200/mo |

### Monthly Cost Summary

| Category | Est. Monthly |
|----------|-------------|
| DreamCompute VPS | €27 |
| Proton Mail | €5 |
| LastPass | $3 |
| Claude Max | $100–200 |
| Hover domain | ~$1.25 |
| **Total (excl. Claude)** | **~€36 / ~$39** |

---

## 2. Analysis by Category

### A. VPS / Hosting — Biggest savings opportunity

**Current:** DreamCompute, 2 vCPU / 1GB RAM / 30GB, €27/mo. Used for a static HTML website only.

**Problem:** You're paying €27/month for a full VPS to serve static files. This is 8x what comparable VPS providers charge, and a VPS is overkill for static hosting.

#### Alternatives

**Free static hosting (no server to manage):**
*Verify: [Cloudflare Pages](https://pages.cloudflare.com/), [GitHub Pages](https://pages.github.com/), [Netlify](https://www.netlify.com/pricing/), [Vercel](https://vercel.com/pricing)*

| Provider | Price | Bandwidth | Custom domain | Deploy from Git |
|----------|-------|-----------|---------------|-----------------|
| Cloudflare Pages | Free | Unlimited | Yes + free SSL | Yes |
| GitHub Pages | Free | ~100GB/mo | Yes + free SSL | Yes |
| Netlify | Free | 100GB/mo | Yes + free SSL | Yes |
| Vercel | Free (Hobby) | 100GB/mo | Yes + free SSL | Yes |

**Budget VPS (if you need server-side capabilities for Plum services):**
*Verify: [Hetzner Cloud](https://www.hetzner.com/cloud/), [Vultr](https://www.vultr.com/pricing/), [DigitalOcean](https://www.digitalocean.com/pricing), [Oracle Cloud Free](https://www.oracle.com/cloud/free/)*

| Provider | Plan | Price | Specs |
|----------|------|-------|-------|
| Hetzner CAX11 (ARM) | Cheapest | €3.29/mo | 2 vCPU, 4GB RAM, 40GB NVMe |
| Hetzner CX22 | x86 | €3.29/mo | 2 shared vCPU, 2GB RAM, 20GB NVMe |
| Vultr | Cloud Compute | $3.50/mo | 1 vCPU, 1GB RAM, 25GB SSD |
| DigitalOcean | Basic | $6/mo | 1 vCPU, 1GB RAM, 25GB SSD |
| Oracle Cloud | Always Free | $0 | Up to 4 vCPU, 24GB RAM, 200GB |

#### Recommendation

**Move the static site to Cloudflare Pages (free).** If you still need a VPS for Plum services (#13, #14), get a **Hetzner CAX11 at €3.29/mo** — better specs than DreamCompute at 1/8 the price. Cancel DreamCompute.

**Savings: ~€24–27/month.**

---

### B. Backup Strategy — Biggest risk area

**Current:** ~5TB of irreplaceable media (photos, music, video) split across internal NVMe + external drive. Zero backups. One drive failure means permanent data loss.

**Problem:** This is a "when, not if" scenario. Drives fail. You have no redundancy.

#### Cloud Backup Options (for 5TB)
*Verify: [Backblaze Personal](https://www.backblaze.com/cloud-backup.html), [Backblaze B2](https://www.backblaze.com/cloud-storage/pricing), [iDrive](https://www.idrive.com/pricing), [Wasabi](https://wasabi.com/pricing), [CrashPlan](https://www.crashplan.com/pricing/)*

| Service | Monthly | Annual | Limit | Notes |
|---------|---------|--------|-------|-------|
| Backblaze Personal | ~$9 | ~$99 | Unlimited/1 PC | Windows/Mac only, 1-year deletion policy |
| iDrive 5TB | ~$7 | ~$80 | 5TB | Multi-device, NAS support, first year often discounted |
| iDrive 10TB | ~$8 | ~$100 | 10TB | Same as above with more room |
| Backblaze B2 | ~$30 | ~$360 | Pay per use | S3-compatible, best for programmatic backup |
| Wasabi | ~$35 | ~$420 | Pay per use | No egress fees, 90-day minimum |
| CrashPlan | ~$10 | ~$120 | Unlimited/1 device | Reliable, CPU-intensive |

#### Local Backup Options

| Option | Cost | Capacity | Notes |
|--------|------|----------|-------|
| External 8TB HDD | ~$140 | 8TB | Simple rsync mirror. Cheapest option. |
| Synology DS224+ (2x 8TB RAID 1) | ~$600 | 8TB usable | NAS with cloud sync, Synology Photos, media serving |
| Unraid on old PC + drives | ~$360 | Flexible | Reuse old hardware, mix drive sizes, parity protection |

#### 3-2-1 Strategy Options

**Budget (recommended start):**

| Copy | Where | Medium | Cost |
|------|-------|--------|------|
| Primary | Desktop drives | Internal NVMe | Already have |
| Local backup | External 8TB HDD | USB HDD | ~$140 one-time |
| Offsite | iDrive 10TB | Cloud | ~$100/year |

Total first year: ~$240. Ongoing: ~$100/year.

**Premium (if you want local NAS benefits):**

| Copy | Where | Medium | Cost |
|------|-------|--------|------|
| Primary | Desktop drives | Internal NVMe | Already have |
| Local backup | Synology DS224+ (RAID 1) | NAS + 2x 8TB | ~$600 one-time |
| Offsite | Backblaze B2 | Cloud | ~$360/year |

Total first year: ~$960. Ongoing: ~$360/year. You also get Synology Photos, media streaming, Docker on the NAS.

#### Recommendation

**Start with the budget 3-2-1:** external 8TB HDD ($140) + iDrive 10TB ($100/yr). Get protected now, cheaply. Upgrade to a Synology NAS later if you want the extra features. The critical thing is to get *any* offsite backup in place immediately.

---

### C. Password Manager — Security concern

**Current:** LastPass (~$3/mo).

**Problem:** LastPass had a major breach in 2022 where encrypted vaults and unencrypted metadata (URLs, emails) were stolen. Subsequent attacks targeted engineers, and millions in crypto theft have been linked to decrypted vaults. The company's slow disclosure eroded trust. The client is closed source.

#### Alternatives
*Verify: [Bitwarden](https://bitwarden.com/pricing/), [1Password](https://1password.com/pricing), [Proton Pass](https://proton.me/pass/pricing), [KeePassXC](https://keepassxc.org/)*

| | Bitwarden | 1Password | Proton Pass | KeePassXC |
|---|---|---|---|---|
| **Price** | Free / $10/yr premium | $2.99/mo | Free / included in Proton plans | Free |
| **Open source** | Yes (client + server) | No | Yes (clients) | Yes |
| **Security** | Zero-knowledge, AES-256, Argon2. Audited. | Zero-knowledge + Secret Key. Audited. | Zero-knowledge, Proton E2E encryption. Audited. | Local encryption, AES-256. No server. |
| **Self-host** | Yes (Vaultwarden) | No | No | Inherently local |
| **Sync** | Cloud or self-host | Cloud only | Proton cloud (Swiss) | Manual (Syncthing, etc.) |
| **Unique strength** | Best balance of features, openness, price | Best UX, Secret Key defense-in-depth | Integrates with your Proton Mail, email aliases | Zero cloud dependency |

#### Recommendation

**Bitwarden Premium ($10/year)** is the strongest choice: open source, audited, self-hostable, and practically free. If you want to stay in the Proton ecosystem, **Proton Pass** is solid too (may already be included in your plan). Either way, leave LastPass.

---

### D. Domain & Email — Minor optimizations

**Current:** Hover for domain (~$15/yr), Proton Mail for email (~€5/mo), Google Calendar (free).

This setup is fine. Minor optimizations:

- **Consider [Cloudflare as registrar](https://www.cloudflare.com/products/registrar/)** if you move hosting to Cloudflare Pages — at-cost domain pricing (no markup), and DNS + hosting in one place.
- **Proton Mail** is solid for privacy-focused email. No change needed.
- **Google Calendar** — if the Google dependency bothers you, Proton Calendar is included with your Proton plan. Otherwise, leave it.

#### Recommendation

**No urgent changes.** Optionally transfer domain to Cloudflare for simpler management if you adopt Cloudflare Pages.

---

### E. Dev Tools — Already solid

**Current:** VS Code (free) + Claude Max ($100–200/mo).

This is a strong setup. The Claude Max cost is high but presumably justified by heavy usage. No alternatives match Claude Code's capabilities for agentic coding workflows.

#### Recommendation

**No changes.** Monitor Claude pricing — if usage is consistently under the Max tier limits, consider whether Pro + API credits might be cheaper. But that's a usage analysis, not a stack change.

---

## 3. Prioritized Action Plan

### High Priority (do now)

| Action | Effort | Savings / Benefit |
|--------|--------|-------------------|
| Move static site to Cloudflare Pages | Low (1-2 hours) | €27/mo saved |
| Get a Hetzner CAX11 if you need a VPS for services | Low (30 min) | €24/mo cheaper than DreamCompute |
| Cancel DreamCompute | Low | €27/mo saved |
| Buy an 8TB external HDD + sign up for iDrive | Low (1 day initial backup) | Protect 5TB+ of irreplaceable media |
| Migrate from LastPass to Bitwarden or Proton Pass | Medium (1-2 hours) | Eliminate security risk |

### Medium Priority (do this quarter)

| Action | Effort | Benefit |
|--------|--------|---------|
| Transfer domain from Hover to Cloudflare | Low | Simpler management, at-cost pricing |
| Set up automated local backup (rsync cron to external HDD) | Low | Automated local redundancy |

### Low Priority (when you feel like it)

| Action | Effort | Benefit |
|--------|--------|---------|
| Get a Synology NAS for media management | Medium ($600) | Synology Photos, media streaming, better backup |
| Repurpose Raspberry Pis (Pi-hole, monitoring, etc.) | Medium | Use idle hardware |
| Evaluate Proton Calendar vs Google Calendar | Low | Reduce Google dependency |

### Estimated Monthly Impact

| Item | Before | After | Change |
|------|--------|-------|--------|
| Hosting | €27/mo | €0–3.29/mo | -€24 to -€27 |
| Backup | €0 | ~$8/mo (iDrive) | +$8 |
| Password manager | $3/mo | $0.83/mo (Bitwarden) or $0 (Proton Pass) | -$2 to -$3 |
| **Net change** | | | **~-€20/mo saved, plus data protection** |

---

*Pricing data sourced May 2025. Verify current prices at the links above before acting.*
