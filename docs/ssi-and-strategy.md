# SSI and Content Strategy

This guide explains the LinkedIn Social Selling Index model used by the project and how scheduling, curation, and reporting are mapped to those SSI pillars. The README defines SSI as a daily 0–100 score with four equally weighted components worth 25 points each.

## SSI model

The four components are professional brand, finding the right people, engaging with insights, and building relationships. The README also states that LinkedIn’s own framing ties higher SSI to stronger visibility and more opportunities, and it cites an example claim that professionals above 70 SSI see 45% more opportunities than those below 30.

| Component                         | What it measures                                                           |
| --------------------------------- | -------------------------------------------------------------------------- |
| Establish your professional brand | Profile completeness, posting consistency, and saves or shares on content. |
| Find the right people             | Search visibility, connection acceptance, and audience reach.              |
| Engage with insights              | Reactions, shares, comments, and thought leadership signals.               |
| Build relationships               | Connection growth, response rate, and relationship depth.                  |

## Why automate

The README argues that SSI decays when activity becomes inconsistent, and that maintaining three posts per week plus curated commentary is difficult alongside full-time engineering work. The tool is positioned as handling repeatable publishing tasks while leaving final go-live decisions under user control.

## Calendar strategy

The content calendar is a four-week plan whose topics each carry an angle and SSI pillar label. This allows the scheduler to distribute output across the four SSI dimensions instead of over-indexing on one type of content such as brand-only posting.

## Scheduler behavior

The scheduler is CLI-triggered rather than a persistent background process. It uses `.env` focus weights to select topics across SSI pillars, then sends every selected post to Buffer without an explicit `scheduled_at` timestamp. Buffer owns queue placement, posting cadence, and publish times.

## SSI targets

The README includes a target table backed by `ssi_history.json` for tracking and `--report` for output. The targets shown in the source are 25 for establish brand, 20 for find right people, 25 for engage with insights, and 25 for build relationships, totaling 95.

| Component            | Target | Strategy                                 |
| -------------------- | -----: | ---------------------------------------- |
| Establish brand      |     25 | 3x/week posting via Buffer.              |
| Find right people    |     20 | Connect with commenters and join groups. |
| Engage with insights |     25 | Curated posts and daily commenting.      |
| Build relationships  |     25 | Reply to comments and DM connections.    |
| Total                |     95 | Combined target.                         |

## Weekly workflow

The recommended reporting cycle is to check `linkedin.com/sales/ssi`, save the four component scores with `--save-ssi`, and then inspect trends with `--report`. The report is described as showing progress bars, trend arrows, and the last five weekly snapshots.

## Focus tuning

Four `.env` percentages control how often each SSI pillar receives generated posts. The README recommends adjusting these weights toward lagging pillars so the scheduler adapts its emphasis without code changes.
