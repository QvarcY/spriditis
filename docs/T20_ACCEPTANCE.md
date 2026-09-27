# T20 Public Research Quality Acceptance — Closeout

Status: **CLOSED / ACCEPTED**  
Closed: **2026-09-27**

T20 is considered complete. The real public browser-to-result acceptance passed, the accepted core changes are on `main`, the WEB/API production content is represented on `main`, and no further T20 functional test cycle is required.

## Final accepted state

### Core — QvarcY/spriditis

- Accepted production content commit: `78777b7ae9ed25bfb45e2e796fb42d1ae52ed822`
- Main merge commit: `2e316a5107823d6020d0fdc3b7422d5e9cfd9cdd`
- The accepted content commit and merge commit have the same tree.
- T20 core promotion was merged through PR #7.

### WEB/API — QvarcY/spriditis-web

- Running immutable API release: `5ae3443f46f581ca3eab88685954b5b106c17797`
- Accepted integration candidate: `96ef1316359d1db91e56b40d4f05b104716a079c`
- Main merge commit: `1c256dc74dca0e9686304140600f385bc5a48090`
- Accepted production tree / merged main tree: `e2c8fa9032d5427c26772ba4b12cda9d4bc3505b`
- WEB/API promotion was merged through PR #6.
- A new immutable release for the merge SHA is not required because the merged main tree is identical to the already accepted running production tree.

## Final real public acceptance

Acceptance job:

`e54d61a19e25abd824894542dd6459c9`

Observed result:

- public POST accepted with HTTP 202;
- job completed;
- 9 pages visited;
- 15 domains observed;
- 3 domains crawled;
- 2 search queries issued;
- 7 unique search results;
- 4 extracted entities;
- 2 entities survived the final relevance and hard-criteria gate;
- both accepted entities had structured prices;
- both accepted entities had verified required evidence;
- generated report returned HTTP 200;
- report contained 2 relevant result cards;
- session ownership boundary returned HTTP 404 without the owning cookie;
- API, worker and nginx remained healthy.

The acceptance query intentionally exercised real discovery and source extraction rather than a synthetic-only path.

## Product defects found and fixed during T20

### 1. Mandatory constraints were lost in discovery queries

A later generated discovery query dropped required evidence terms, allowing broad results to dominate the search.

Fixed by:

`17ba26f` — `search: preserve hard constraints in discovery queries`

The planner now preserves hard research constraints in discovery queries.

### 2. ss.lv was not recognized by the SS classifieds adapter

Real Latvian SS listings appeared under `ss.lv`, while the source adapter only recognized the `ss.com` form.

Fixed by:

`3e2d2df` — `sources: support ss.lv classified listings`

The same first-class classifieds extraction path now supports the Latvian hostname.

### 3. Real listing detail pages were not prioritized strongly enough

The crawler could remain on category/archive pages instead of following evidence-rich `/msg/` listing detail pages.

Fixed by:

`77fac73` — `crawler: prioritize evidence-rich detail links`

Detail-link priority and useful row context were added so actual listing evidence reaches extraction sooner.

### 4. Domain budget was consumed before later query results were compared globally

Earlier broad-query domains could consume `max_domains` before a later hard-constraint query returned a stronger source such as SS.

Fixed by:

`78777b7` — `crawler: allocate search domain budget globally`

Search hits are now collected and ranked globally before activating domains.

## Other quality improvements included in the accepted T20 chain

The accepted T20 core chain also improved:

- grouped explicit money parsing;
- OpenGraph price recovery;
- first-class SS classifieds extraction;
- explicit evidence constraints in project schema;
- fallback relevance enforcement for required evidence;
- answer-first report structure;
- report card alignment and collapsed crawler diagnostics;
- listing field labels in constraint evidence;
- authoritative SS adapter precedence.

These are quality improvements rather than the four root-cause blockers listed above.

## Deployment and operations lessons captured during T20

### Execution lock permissions

An early deployment command attempted to open `/run/spriditis/execution.lock` before entering the privileged context and failed with permission denied.

Use the lock from the privileged deployment context, for example with a read/write descriptor and `flock`.

### Static frontend deployment configuration must not be reused for API releases

`/etc/spriditis-web/deploy.env` and `/usr/local/sbin/spriditis-web-update` belong to the static frontend deployment path.

They must not be sourced or reused by the API release process. API releases use explicit, separate paths under `/opt/spriditis-web-api`.

### Read-only staging must not run write-producing compile checks

`compileall` attempted to create `__pycache__` inside a root-owned read-only staging tree.

For deployment validation of a read-only staging file, use a non-writing syntax check such as Python `compile(source, path, "exec")`.

### GitHub deploy keys are repository-specific

The VPS uses separate write-enabled deploy keys for the core and WEB/API repositories.

A deploy key attached to the wrong repository can authenticate successfully to GitHub but still fail repository access. Verify the repository identity before relying on the key.

### spriditis-web fetch refspec tracked only dev

The API repository had:

`+refs/heads/dev:refs/remotes/origin/dev`

Therefore a normal `git fetch origin --prune` did not refresh `origin/main`.

When main is required, either use an explicit main refspec or deliberately broaden the configured fetch refspec. Do not assume `origin/main` is current merely because a generic fetch succeeded.

### Immutable API release directories are not Git working trees

A release under `/opt/spriditis-web-api/releases/<sha>` does not contain `.git`.

Do not run `git rev-parse` from the release directory to validate deployed content.

### git archive is not a valid whole-repository comparison for the API package

The repository archive used for the static site does not represent the API release package: archive/export rules omit API payload content that exists in the separately built immutable API release.

Therefore a root-level `git archive` versus API-release `diff` is not a valid production-content test. Validate API releases with the API packaging/release manifest or direct source/package comparisons appropriate to the release process.

## Known residual behavior

### Generic lexical candidate can still be discovered and then rejected

A Motorfy page containing generic wording such as technical-description language could still become a search/crawl candidate.

The final entity evidence gate correctly rejected it because the required research evidence was absent. This is a possible future semantic-ranking improvement, but it did not block T20 acceptance and is **not recorded as fixed**.

### External source blocking is not a Sprīdītis defect

One source returned HTTP 403 during the real acceptance work. The crawler failed that source gracefully. External anti-bot or access policy behavior is not treated as a T20 product defect.

## Regression coverage added

T20 added regression coverage for the blockers, including:

- required-evidence discovery query preservation;
- ss.lv source support;
- evidence-rich detail-link priority;
- global search-domain budget allocation.

The WEB/API integration candidate also passed **62 API/worker tests**. Frontend files were unchanged in that integration.

## Closure rule

T20 is closed because the production acceptance goal was met in a real public flow and the root-cause bugs discovered while reaching that goal were fixed and promoted.

Further crawler, ranking, semantic relevance, source coverage, packaging cleanup or deployment tooling improvements belong to later work. They must not reopen T20 unless a regression invalidates the accepted behavior documented here.
