# Market Validation Experiment

## Objective

Validate paid demand for a founder-friendly launch QA service before investing in a SaaS product. Compliments, waitlist signups, and free-pilot interest do not count as validation. The primary success event is a completed paid audit.

## Ideal customer profile

A qualified prospect:

- is an independent founder or a team of roughly two to five people;
- built a web application with Lovable, Bolt, Replit, Cursor, or a comparable AI coding tool;
- has a public or staging build and a recent or upcoming launch;
- has at least one meaningful user flow such as authentication, onboarding, checkout, data entry, or account state;
- can fix or prioritize findings after the audit;
- is not seeking security certification, penetration testing, performance engineering, or regulatory compliance.

## Founding pilot offer

### 24-Hour AI App Launch QA — $199 prepaid

The founding pilot is limited to three customers. It includes:

- scope confirmation before payment;
- up to five critical user flows;
- full Chromium desktop coverage;
- critical mobile and Firefox/WebKit smoke coverage where applicable;
- manual UX and error-handling exploration;
- accessibility, network, and console smoke checks;
- severity-ranked findings with reproduction steps and evidence;
- a launch-readiness score and launch recommendation;
- self-contained HTML and PDF reports;
- a 20-minute findings walkthrough;
- one focused verification pass within seven days.

Security, load, compliance, source-code review, API contract testing, and implementation work are excluded. If access or scope makes the agreed audit impossible before work starts, payment is refunded rather than publishing an incomplete or invented result.

After three completed pilots, test a standard price of **$399** with the same base scope. Larger or higher-risk products require a custom quote.

## Pricing rationale

The pilot intentionally sits inside the observed market for human-reviewed fixed-scope QA while remaining accessible to bootstrapped founders. Current reference points include a $199 QA Day audit and $299 senior audit from [DayQA](https://dayqa.io/pricing), a $495 launch audit from [Proper Pete](https://properpete.com/website-launch-audit.html), and expert audit services starting at $499 from [ReleaseLens](https://releaselens.org/). Automated reports priced from $9–$59 demonstrate why the offer must lead with verified flows, human judgment, evidence, and a launch decision rather than a generic scan.

## Campaign design

### Cohort

- 28 publicly identified maker prospects
- first batch: 10 high-priority prospects
- second batch: 10 prospects after message review
- final batch: 8 prospects after incorporating response data
- one initial message and one follow-up after three to four days
- no scraped private email addresses and no automated mass messaging

### Primary call to action

Ask whether the founder wants a short scope check for a current build. Do not ask for a meeting by default. An asynchronous reply or URL is a lower-friction first step.

### Success thresholds

| Metric | Minimum success threshold |
| --- | ---: |
| Messages successfully delivered | 25 |
| Positive or substantive reply rate | 20% |
| Qualified scope conversations | 3 |
| Paid founding pilots | 1 |
| Completed pilot audits | 1 |
| Outcome-focused testimonial or usable feedback | 1 |

The milestone is validated only when at least one prospect pays and the audit is completed. A testimonial without payment is useful evidence but does not validate the business model.

## Decision rules

- Fewer than two substantive replies after the first 15 messages: revise targeting and the opening sentence before continuing.
- Replies but no scope conversations: simplify the call to action and strengthen relevance.
- Scope conversations but no payment: investigate trust, timing, scope, and price separately; do not immediately discount.
- One paid pilot but little use of the findings: improve the deliverable and walkthrough before increasing outreach.
- One paid and completed pilot with acted-on findings: finish the three-pilot price test, then test $399.

## Pilot feedback

Ask within 24 hours of the walkthrough:

1. Which finding changed what you planned to do before launch?
2. What part of the report was easiest or hardest to act on?
3. What did you expect that was missing?
4. Would you pay for this again before another release? Why or why not?
5. May we use a short outcome-focused quote with your name and product?

## Tracking rules

`outreach/prospects.csv` is the source of truth. Record every contact attempt, reply, qualification outcome, price objection, pilot result, and next action. Never infer a rejection from silence until the single planned follow-up has passed.

No external message may be sent until the campaign owner approves the prospect batch and final copy.
