# ShirtClawd Marketing Strategy

This document defines the current go-to-market strategy for ShirtClawd.

It answers a simple question:

- how does ShirtClawd get attention before it has subscribers or meaningful follower counts?

The short version is:

- do not rely on raw posting volume
- use the bot to publish niche-native content, not generic product ads
- borrow attention from existing communities and creators
- capture owned audience as early as possible
- focus the first growth loop on one strong catalog lane instead of the whole store

## Core Thesis

ShirtClawd does not win by acting like an automated social scheduler.

It wins by acting like a niche publisher with a merch engine attached.

That means:

- content should entertain first and sell second
- the account should feel like it belongs to a specific subculture
- recurring series should matter more than isolated product posts
- distribution should come from communities, creators, and replies before it comes from algorithmic reach
- email or SMS capture should start early so growth is not trapped inside rented platforms

## Primary Beachhead

The first audience lane should be the `Coloradans Against` series.

This is the best current candidate because it has several traits that make audience-building easier:

- it is already a coherent series instead of a one-off joke
- it has a clear regional identity
- it is legible even to people who have not seen the full store
- it invites opinions, arguments, and playful tribal reactions
- it supports recurring formats instead of one-time promotion

Current examples in the catalog include:

- Coloradans Against Craft Beer
- Coloradans Against Fourteeners
- Coloradans Against Hiking
- Coloradans Against Triathlons

This lane gives ShirtClawd a clearer initial identity than a broad "funny shirts" strategy.

## Positioning

The account voice for this lane should feel like:

- local
- dry
- mildly antagonistic in a playful way
- anti-cliche rather than anti-Colorado

The joke is not "Colorado is bad."

The joke is "Colorado culture has sacred cows, and we are poking them."

That distinction matters because it keeps the brand in conversation with Colorado identity instead of outside it.

## Growth Strategy

### 1. Build around a repeatable content series

The first growth engine should be a recognizable editorial series, not isolated shirt posts.

For `Coloradans Against`, that means recurring formats like:

- "today's Colorado overhyped thing"
- "rank the most overrated Colorado personality trait"
- "Coloradans Against of the week"
- "pick your enemy: hiking, fourteeners, craft beer, or triathlons"
- "the group-chat argument starter"

The important part is recognizability. People should start to know what kind of post ShirtClawd makes before they know what product it sells.

### 2. Treat product posts as conversion assets, not top-of-funnel assets

Most early posts should create reactions, shares, and comments.

Only some posts should directly ask for the sale.

A healthy split for the first phase is:

- 70% conversation or entertainment posts
- 20% product-connected posts
- 10% direct promotion or offer posts

### 3. Borrow distribution instead of waiting for organic reach

Early exposure should come from audiences that already exist.

Priority channels:

- replies to Colorado meme and culture accounts
- outreach to Colorado micro-creators, podcasters, newsletter writers, and local humor pages
- giveaway or affiliate seeding to small creators with strong local audience trust
- posts designed to be repostable by Denver and Colorado community pages
- community-native participation in places where Colorado stereotype jokes already perform

The goal is not just impressions.

The goal is to get ShirtClawd seen in environments where the joke already makes sense.

### 4. Capture audience off-platform

Every profile and landing path should offer a simple reason to subscribe.

Recommended first capture message:

- get the best weird Colorado shirt drops
- vote on the next `Coloradans Against` release
- get a first-order discount on the next drop

The owned audience matters because:

- follower growth is slow
- platform reach is unstable
- recurring series become more valuable when people can opt in directly

## Platform Roles

ShirtClawd should not treat every platform as interchangeable.

### Instagram

Primary role:

- visual brand building
- shareable carousels and reels
- series recognition

Best use:

- recurring `Coloradans Against` visuals
- polls in captions and stories
- carousels with "choose your most overrated Colorado thing"
- line/set posts that show all four `Coloradans Against` shirt artworks together

### X

Primary role:

- replies
- quick arguments
- culture-joke distribution

Best use:

- punchy hot takes
- quote-worthy one-liners
- replies to larger Colorado accounts

### Bluesky

Primary role:

- early community building with niche humor audiences
- lower-stakes voice exploration

Best use:

- conversational posts
- testing new joke angles
- learning what phrasing sparks replies

### Email

Primary role:

- owned audience capture
- product conversion
- weekly digest of the best posts and newest shirts

Best use:

- one simple weekly roundup tied to the series

## 30-Day Plan

### Week 1: Establish the lane

- declare `Coloradans Against` as the primary growth series
- standardize voice, visual treatment, and recurring formats
- create a simple landing page or signup path tied to the series
- make sure all profiles point to the same CTA

Operationally, daily planning should use the `coloradans_against` campaign mode so the bot does not drift back into broad catalog rotation:

```bash
python plan_day.py \
  --campaign coloradans_against \
  --platform bluesky \
  --platform instagram \
  --platform facebook \
  --platform threads \
  --no-approval-required
```

The generated plan should include `campaign`, `series`, `audience_lane`, `content_goal`, `content_format`, and `cta_goal` fields so each post has a job beyond "show this shirt."

Sale context: ShirtClawd has 20% off all Spreadshirt orders from May 15 through May 19, 2026. Use this in direct-offer posts, but keep conversation posts focused on local reactions first.

Optional line posts: add `--include-campaign-set-post` to the daily plan, or set `CAMPAIGN_SET_POST=1` for `scripts/run_daily_workflow.sh`, to publish one extra multi-image set post on each selected platform for the four-shirt `Coloradans Against` lineup. Use `--campaign-set-platform instagram` or `CAMPAIGN_SET_PLATFORM=instagram` to narrow it to one platform.

### Week 2: Publish and participate

- post from the series every day
- spend as much effort on replies and outreach as on original posts
- identify a small list of Colorado meme, media, and creator accounts for daily interaction

### Week 3: Force discovery

- run one giveaway, collaboration, or creator seeding push
- offer creators discount codes or affiliate incentives
- package the series as something pages can repost, not just a shirt listing

### Week 4: Measure and narrow

- identify which content format gets the best mix of comments, shares, clicks, and follows
- cut weak formats quickly
- double down on the best-performing version of the `Coloradans Against` voice

## What ShirtClawd Should Build Next

The product already supports planning, generation, and some publishing. The next growth-supporting features should help with distribution and audience learning.

Priority additions:

- campaign and series metadata so posts can belong to a recurring editorial arc
- audience-lane tagging for shirts and generated posts
- CTA variants tied to growth goals like follow, signup, vote, or purchase
- creator outreach tracking and simple seeding workflows
- landing page or signup integration for owned audience capture
- performance logging by theme, platform, and series

## Success Criteria

In the first phase, success should not be defined only by direct shirt sales.

Early indicators that the strategy is working:

- replies and shares increase on series posts
- follower growth comes from Colorado-relevant audiences
- people recognize and reference the `Coloradans Against` format
- creator pages or community accounts repost the content
- email or SMS subscribers begin accumulating from social traffic

Sales matter, but they should be read as a lagging indicator behind attention, recognition, and audience capture.

## Decision Rule

When choosing what to build or post next, use this rule:

- prefer the option that makes ShirtClawd feel more like a recognizable niche publisher and less like an automated catalog feed

For now, that means the default strategic answer is:

- lead with `Coloradans Against`
- make the series easy to recognize
- grow through participation and collaboration
- convert attention into an owned audience
