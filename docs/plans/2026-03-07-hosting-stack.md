# Hosting Stack Decision

**Created:** 2026-03-07

## Summary

Domain, VPS, backup storage, and email for Plum infrastructure. European providers preferred. Vendor diversity between compute and backup to mitigate account suspension risk. Email split by use case.

## Chosen Stack

| Layer | Provider | Plan | Price/mo | Notes |
|-------|----------|------|----------|-------|
| Domain | Infomaniak (CH) | .com | ~€1 (€12/yr) | Swiss jurisdiction, flat renewal, WHOIS/DNSSEC/SSL included |
| VPS | Hetzner (DE) | CX23 | €3.99 | 2 vCPU, 4 GB RAM, 40 GB NVMe, 20 TB traffic |
| Backup | Hetzner (DE) | BX21 Storage Box | €10.90 | 5 TB, SFTP/rsync/SCP/SMB/WebDAV, unlimited traffic |
| Insurance | Backblaze B2 (US/EU) | Free tier | €0 | 10 GB free, S3-compatible, critical config/secrets only |
| Email (personal) | Proton Mail Plus (CH) | Mail Plus | ~€4 (~€48/yr) | 1 address, E2E encrypted, Swiss, calendar/contacts |
| Email (all other) | MXRoute (US) | 10 GB | ~€4 ($49/yr) | Unlimited mailboxes, catch-all, 400/hr outgoing |
| **Total** | | | **~€23.89** | |

## Email Architecture

### Use cases

| Use case | Provider | Address(es) | Why |
|----------|----------|-------------|-----|
| Personal | Proton Mail Plus | me@personaldomain | Deliverability critical, E2E encryption, Swiss data, calendar/contacts included |
| Non-important (signups, newsletters) | MXRoute | junk@domain, catch-all | Receive-mostly, don't care if US-hosted, unlimited addresses |
| Coding LLMs (service accounts) | MXRoute | llm-cursor@domain, llm-claude@domain, etc. | Each gets a full separate IMAP mailbox with own login, unlimited |

### Why two providers

- Personal email needs reliability, deliverability, and privacy — Proton excels here
- Non-important and LLM accounts need volume (many addresses cheaply) — MXRoute excels here
- Two domains required since MX records can only point to one provider per domain

### Email: Proton Mail Plus (personal)

- Swiss company, end-to-end encrypted, zero-access encryption at rest [^15]
- 15 GB storage, 1 custom domain, catch-all, calendar/contacts
- IMAP via Proton Bridge for desktop clients
- ~€4/mo (annual billing)

### Email: MXRoute (non-important + LLM accounts)

- **Full separate IMAP mailboxes** per address, not just aliases — each address gets its own login credentials and independent inbox [^16]
- Unlimited mailboxes and domains, 10 GB shared storage pool
- Catch-all support for routing unmatched addresses
- 400 outgoing emails/hr per address (9,600/day) [^17]
- Strong deliverability — own IP pool, MailChannels integration [^18]
- $49/yr, community favourite on LowEndTalk and HN

**Rejected email alternatives:**

- **Migadu Micro (CH, $19/yr):** 20 outgoing/day limit — too restrictive [^19]
- **Migadu Mini (CH, $90/yr):** 100 outgoing/day limit — too restrictive [^19]
- **Migadu Standard (CH, $290/yr):** 500 outgoing/day — meets threshold but 6x the price of MXRoute for same functionality
- **Purelymail (US, $10/yr):** One-person operation, multiple recent outages (EC2 failure Nov 2025, DKIM issues Jan 2026), price increase planned [^20] [^21]
- **Mailbox.org (DE, €3/mailbox/mo):** Per-mailbox pricing kills it at scale. Reports of broken custom domain alias functionality [^22]
- **Fastmail (AU, $6/user/mo):** Premium experience but premium price ($720/yr for 10 users). Non-EU data
- **Infomaniak Mail (CH, €1.50/mailbox/mo):** Per-mailbox pricing, no catch-all
- **Self-hosted (docker-mailserver on CX23):** Free but eats 300-512 MB RAM, deliverability is a constant battle, maintenance burden. CX23 only has 4 GB total — too tight alongside other services [^23]

## Rationale

### Domain: Infomaniak

- Swiss company, GDPR+ jurisdiction, no exposure to US CLOUD Act [^1]
- Flat €12/yr renewal for .com — no year-1 bait pricing [^2]
- WHOIS privacy, DNSSEC, SSL certificate included at no extra cost
- No upselling, clean interface
- Includes 1 free kSuite mailbox (15 GB) — not used since Proton handles personal email

**Rejected alternatives:**

- **IONOS (DE):** Cheap first year (~€1) but renewal jumps to ~€20/yr. Heavy upselling [^3]
- **Gandi (FR):** Post-acquisition by TWS: .com renewal hiked to ~€38/yr, 72h transfer lock added, free email removed [^4] [^5]

### VPS: Hetzner CX23

- Best performance/€ in Europe even after the April 2026 price hike (€2.99 -> €3.99) [^6] [^7]
- Excellent API and tooling: hcloud CLI, Terraform provider, cloud-init support
- Hourly billing — can spin up/down test servers cheaply
- Locations: Germany (Falkenstein, Nuremberg), Finland (Helsinki)

**Rejected alternatives:**

- **Netcup VPS 200 (DE):** Cheaper at €3.25/mo but only 2 GB RAM (tight). Old-school UI, slow support. No hourly billing [^8]
- **OVHcloud VPS-1 (FR):** Best raw specs for the price (4 vCPU, 8 GB, €4.49/mo) but weaker uptime track record and the 2021 Strasbourg datacenter fire still affects trust [^9]

### Backup: Hetzner Storage Box BX21

- 5 TB for €10.90/mo is ~3x cheaper than any S3-compatible alternative at this volume [^10]
- Native SFTP/rsync support — ideal for borg/restic backups without S3 overhead
- Unlimited traffic, no egress fees
- Same provider as VPS (risk accepted, mitigated by B2 insurance tier below)

**Why not a different provider for backup?**

At 5 TB the price gap is too large to justify vendor diversity alone:

| Provider | 5 TB/mo | Protocol |
|----------|---------|----------|
| Hetzner BX21 | €10.90 | SFTP/rsync |
| Backblaze B2 | ~€27.60 ($30) | S3 |
| Hetzner Object Storage | €30.45 | S3 |
| Scaleway One Zone | €37.60 | S3 |
| Cloudflare R2 | ~€69.00 ($75) | S3 |

### Insurance: Backblaze B2 Free Tier

- 10 GB free forever — enough for encrypted config, secrets, SSH keys, database dumps [^11]
- S3-compatible, EU storage region available
- Separate US-based provider: if Hetzner suspends the account, B2 is unaffected
- Acts as disaster recovery for the most critical data only

## Known Risks

### Hetzner account suspension

Hetzner has aggressive automated verification. Multiple reports of accounts suspended without warning, data deleted with no recovery [^12] [^13]. Mitigations:

- Keep B2 insurance backup current (automated daily sync of critical data)
- Maintain clean account: proper ID verification, no abuse-adjacent workloads
- Keep local copies of irreplaceable data

### Single-provider concentration

VPS and primary backup are both on Hetzner. If the account is suspended, both are lost simultaneously. The B2 insurance tier limits blast radius to the most critical assets. Full 5 TB redundancy would cost ~€17/mo extra (B2) — not justified for the current risk profile.

### Hetzner price trajectory

April 2026 saw a 30-37% cloud price hike driven by DRAM/NAND costs from AI infrastructure demand [^14]. Further increases are possible. The stack remains competitive even with another 30% hike (~€27/mo total).

### MXRoute is a small US company

No GDPR commitment, US-only servers [^24]. Acceptable for non-important and LLM accounts where privacy isn't a concern. Personal email is on Proton (Swiss, encrypted) specifically to avoid this risk.

## References

[^1]: [European Domain Registrars — GDPR Compliant](https://domaindetails.com/registrars/european) — 2025
[^2]: [Infomaniak Pricing 2026](https://infoswitch.fr/en/blog/infomaniak-pricing-2026-all-services) — Jan 2026
[^3]: [IONOS Domain Prices](https://www.ionos.com/domains/domain-name-prices) — Mar 2026
[^4]: [Gandi .com renewal price up 60% — Hacker News](https://news.ycombinator.com/item?id=41615851) — 2025
[^5]: [Gandi price hikes & transfer annoyances](https://www.bidon.ca/random/2025-02-23-gandi-registrar-is-evil/) — Feb 2025
[^6]: [Hetzner Price Adjustment Statement](https://www.hetzner.com/pressroom/statement-price-adjustment/) — Feb 2026
[^7]: [PriceTimeline — Hetzner Cloud Price Increase](https://pricetimeline.com/news/211) — Feb 2026
[^8]: [Netcup VPS Plans — VPSBenchmarks](https://www.vpsbenchmarks.com/hosters/netcup) — 2026
[^9]: [OVHcloud Review — WebsitePlanet](https://www.websiteplanet.com/web-hosting/ovh/) — 2026
[^10]: [Hetzner Storage Box BX21 — €10.90/mo](https://www.whtop.com/plans/hetzner.com/128270) — 2025
[^11]: [Backblaze B2 Pricing](https://www.backblaze.com/cloud-storage/pricing) — Mar 2026
[^12]: [LowEndTalk — Hetzner Account Deactivation Concerns](https://lowendtalk.com/discussion/188943/want-to-use-hetzner-at-work-worried-about-all-these-reports-of-account-deactivation) — 2025
[^13]: [WebHostingTalk — Hetzner Suspension](https://www.webhostingtalk.com/showthread.php?t=1865649) — 2025
[^14]: [Tom's Hardware — Hetzner 37% Price Hike](https://www.tomshardware.com/tech-industry/hetzner-to-raise-prices-by-up-to-37-percent-from-april-1) — Feb 2026
[^15]: [Proton Mail Pricing](https://proton.me/mail/pricing) — Mar 2026
[^16]: [LowEndTalk — MXRoute plus addressing creates separate mailboxes](https://lowendtalk.com/discussion/197897/does-mxroute-allow-using-the-sign-to-basically-have-unlimited-alias-for-a-mailbox) — 2025
[^17]: [MXRoute — Outbound Limits](https://docs.mxroute.com/docs/presales/limits.html) — 2025
[^18]: [MXRoute Review — WPJohnny](https://wpjohnny.com/mxroute-email-hosting-review/) — 2025
[^19]: [Migadu Pricing](https://migadu.com/pricing/) — Mar 2026
[^20]: [Purelymail EC2 Failure](https://news.purelymail.com/posts/status/2025-11-23-ec2-failure-in-s3-client.html) — Nov 2025
[^21]: [Purelymail DKIM Issues](https://news.purelymail.com/posts/updates/2026-01-29-dkim-public-record-issues.html) — Jan 2026
[^22]: [Mailbox.org Custom Domain Issues — CyberInsider](https://cyberinsider.com/email/reviews/mailbox-org/) — 2026
[^23]: [docker-mailserver FAQ — 512MB RAM minimum](https://docker-mailserver.github.io/docker-mailserver/latest/faq/) — 2025
[^24]: [MXRoute GDPR Considerations](https://docs.mxroute.com/docs/general/gdpr.html) — 2025
