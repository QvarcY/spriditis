# Security Policy

Sprīdītis is a web crawler and research engine, so security boundaries around URLs, redirects, credentials, and external content are treated as part of the core design.

## Supported version

Sprīdītis is alpha software. Security fixes are targeted at the current `main` branch and the latest published alpha baseline.

Older development snapshots may not receive backported fixes.

## Reporting a vulnerability

Please do **not** publish exploit details, credentials, private URLs, or proof-of-concept payloads in a public issue.

Preferred reporting path:

1. Open the repository's **Security** tab and use **Report a vulnerability** if private vulnerability reporting is available.
2. If that option is unavailable, open a minimal public issue stating that you have a security concern and need a private contact channel. Do not include sensitive technical details in that issue.

Include, when possible:

- affected version or commit;
- affected component;
- reproduction conditions;
- expected vs actual behavior;
- security impact;
- whether the issue can expose credentials, reach private networks, bypass crawl restrictions, or corrupt stored data.

## High-priority areas

Security-sensitive findings include, but are not limited to:

- SSRF or access to localhost/private/link-local networks;
- unsafe redirect handling;
- bypass of blocked-host or URL-safety policy;
- credential or `.env` leakage;
- accidental storage of secrets in reports or logs;
- path traversal or unsafe file writes;
- injection through parsed web content;
- database migration corruption;
- dependency vulnerabilities with a practical impact on Sprīdītis;
- unintended bypass of crawler limits or access restrictions.

## Secret exposure

If an API key, password, token, cookie, or other credential is accidentally committed or shared:

1. revoke or rotate it immediately;
2. remove it from the current code/configuration;
3. treat Git history as potentially retaining the old value;
4. replace public examples with placeholders.

Removing a secret from the latest file does not make an already exposed credential safe again.

## Responsible crawling

Sprīdītis is intended for legitimate research on publicly accessible information.

Do not use the project to bypass authentication, paywalls, CAPTCHAs, access controls, or other technical restrictions. Users are responsible for applicable laws, site terms, and data-use requirements.

---

## Latviski

Drošības problēmas ar pilnām tehniskajām detaļām nevajadzētu publicēt publiskā issue.

Īpaši svarīgi ir ziņot par iespējām piekļūt privātiem tīkla resursiem, apiet URL/drošības filtrus, nopludināt piekļuves datus, sabojāt datubāzi vai apiet crawlera ierobežojumus.

Ja kāda API atslēga vai parole ir tikusi atklāta, tā nekavējoties jāatsauc vai jānomaina — ar izdzēšanu no jaunākās faila versijas vien nepietiek.
