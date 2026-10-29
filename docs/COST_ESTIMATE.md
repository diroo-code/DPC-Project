# Cost Estimate and Hosting Comparison

Date: 2026-10-29
All provider figures were read from the official pricing pages on this date and are cited at the end.
Prices are in US dollars as published. No exchange rate is asserted here; a MYR conversion depends on the
rate on the billing date.

## 1. Verified free-tier limits

| Service | Free tier | Limit that matters most here |
|---|---|---|
| Supabase | $0 | 500 MB database, 1 GB file storage, 5 GB egress, 50,000 monthly active users, 2 active projects. **Projects pause after one week of inactivity** |
| Cloudflare Pages | $0 | 500 builds per month, 1 concurrent build, 20,000 files per site, 100 projects |
| Render web service | $0 compute, Hobby workspace $0 | 512 MB RAM, shared CPU. Free instances are suspended when idle and cold start on the next request |

## 2. What this application actually consumes

| Resource | Driver | This project's realistic use |
|---|---|---|
| Database | 5 tables of metadata plus indexes | Well under 50 MB for thousands of photos and comments |
| File storage | Photos at up to 5 MB each | 1 GB holds roughly 200 photos at the maximum size |
| Egress | Signed image downloads plus API JSON | Dominated by images: 100 photos at 2 MB viewed ten times is about 2 GB |
| Compute | FastAPI, 512 MB is sufficient for a coursework load | One small instance |
| Builds | Frontend rebuild on each push | A few dozen at most |

## 3. Three scenarios

| Scenario | Assumptions | Monthly cost |
|---|---|---|
| **A. Demonstration and grading** | 3 to 5 users, 60 photos total at about 2 MB, normal browsing, single Render instance | **$0**, inside every free tier |
| **B. Course maximum** | 5 users uploading 20 photos a day for 14 days at 5 MB, 1,400 photos, about 7 GB | **Exceeds free storage.** Either cap uploads, delete after demonstration, or move to Supabase Pro at $25/month |
| **C. Comfortable paid baseline** | No cold starts, no pause, backups, room to grow | About **$32 per month**: Supabase Pro $25 plus Render compute $7 for 512 MB. A custom domain is extra |

Scenario A is the target. Scenario B is the one that silently breaks a free project, and it is worth
knowing before the demonstration rather than during it.

## 4. Paid tiers, if ever needed

| Item | Published price | When it becomes relevant |
|---|---|---|
| Supabase Pro | From $25/month | More than 500 MB of data, more than 1 GB of files, or no pausing and daily backups |
| Supabase compute, Small | $15/month | More connections or RAM than the free shared instance |
| Render, 512 MB paid instance | $7/month | Removing cold starts |
| Render, 2 GB instance | $25/month | Heavier concurrency |
| Render key-value (Redis) | $10/month | Shared rate-limit counters across multiple instances |
| Custom domain | Registrar price plus, on Supabase, $10/month per domain add-on | Almost certainly not needed for this assignment |

## 5. Cost control built into the application

| Control | Effect |
|---|---|
| 5 MB per image | Caps the worst case per upload |
| 20 uploads per user per day | Caps storage growth per account |
| 60 second signed URLs | Limits how long a leaked URL can consume egress |
| Rate limiting on uploads and comments | Reduces accidental or hostile volume |
| Private bucket | No anonymous or search-engine traffic on images |

These are not only security measures; they are the reason scenario A stays at zero.

## 6. Hosting comparison

Only options whose published terms were checked are compared. Anything not checked is marked as such
rather than guessed.

| Option | Fits this stack | Free tier | Verdict |
|---|---|---|---|
| Cloudflare Pages | React build, static | Yes, generous | **Chosen for the frontend.** No cold starts, global edge, free HTTPS |
| Render | Python web service | Yes, 512 MB, idles | **Chosen for the backend.** Config is simple and the free tier fits |
| Supabase | Postgres, Auth, Storage | Yes, 1 GB files, pauses after a week | **Chosen for data.** One project covers all three data needs |
| Cloudflare Workers | Cannot run a long-lived FastAPI process without rewriting | Yes | Not suitable without porting the API |
| Fly.io | Could host the container | Free allowance has changed repeatedly | Not evaluated in detail; would need a fresh check before use |
| Railway | Could host the container | Trial credit rather than a standing free tier | Not suitable for an indefinite RM0 target |

## 7. Honest cost statement

The project can plausibly run at **$0** for the demonstration window, inside the published free tiers.
That is not a guarantee of zero cost. The three ways it becomes non-zero are: exceeding the 1 GB storage
allowance, exceeding 5 GB of egress, or needing no cold starts and no pausing. Supabase, Cloudflare and
Render all revise their terms, so the limits above must be re-read on the day of deployment rather than
trusted from this document.

The assignment budget target is RM0 in additional hosting charges. On the free tiers that target is
reachable; the report must still say that the cost is zero *because the free tiers were sufficient*, not
because the application is incapable of incurring cost.

## 8. Shutdown checklist

1. Stop the Render service, or delete it after grading.
2. Delete or pause the Supabase project, after exporting the schema and a data dump.
3. Delete the Cloudflare Pages project if no longer needed.
4. Revoke any personal access token used for the push.
5. Confirm no card on file is attached to a paid plan.

## 9. Sources

- Supabase pricing, https://supabase.com/pricing, read 2026-10-29
- Cloudflare Pages limits, https://developers.cloudflare.com/pages/platform/limits/, read 2026-10-29
- Render pricing, https://render.com/pricing, read 2026-10-29
