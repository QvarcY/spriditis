# Sprīdītis — drošības politika / Security Policy

---

# Latviski

Sprīdītis ir web crawler un pētniecības dzinējs, tāpēc URL, redirect, credentials un ārējā satura drošības robežas ir daļa no kodola arhitektūras.

## Atbalstītā versija

Drošības labojumi tiek mērķēti uz aktuālo `main` un jaunāko publicēto alpha bāzi. Vecākiem development snapshot labojumi var netikt backportēti.

## Kā ziņot par ievainojamību

**Nepublicē** exploit detaļas, credentials, privātus URL vai proof-of-concept payload publiskā issue.

Vēlamais ceļš:
1. GitHub repozitorija **Security** sadaļā izmanto **Report a vulnerability**, ja private vulnerability reporting ir pieejams;
2. ja nav, atver minimālu publisku issue ar norādi, ka vajadzīgs privāts saziņas kanāls, bez sensitīvām detaļām.

Ja iespējams, norādi:
- versiju/commit;
- komponenti;
- reproducēšanas nosacījumus;
- expected vs actual;
- ietekmi;
- vai iespējama credentials noplūde, private-network piekļuve, crawl restriction bypass vai datu bojājums.

## Augstas prioritātes zonas

- SSRF / localhost / private / link-local access;
- unsafe redirects;
- blocked-host/URL-safety bypass;
- `.env` vai credentials leakage;
- secrets reports/logs;
- path traversal / unsafe file writes;
- injection caur parsētu saturu;
- DB migration corruption;
- dependency ievainojamības ar praktisku ietekmi;
- crawler limit/access restriction bypass.

## Ja atklāts noslēpums

Ja API key, parole, token, cookie vai cits credential ir publicēts:
1. nekavējoties revoke/rotate;
2. izņem no aktuālā koda/config;
3. pieņem, ka Git history var saglabāt veco vērtību;
4. publiskos piemēros izmanto placeholders.

Vienkārša izdzēšana no jaunākā faila nepadara credential atkal drošu.

## Atbildīga pārmeklēšana

Sprīdītis paredzēts likumīgai publiski pieejamas informācijas izpētei. To nedrīkst izmantot authentication, paywall, CAPTCHA, access controls vai citu tehnisku ierobežojumu apiešanai.

---

# English

Sprīdītis is a web crawler and research engine, so security boundaries around URLs, redirects, credentials and external content are part of the core design.

## Supported version

Security fixes target the current `main` branch and latest published alpha baseline. Older development snapshots may not receive backports.

## Reporting a vulnerability

Do **not** publish exploit details, credentials, private URLs or proof-of-concept payloads in a public issue.

Preferred path:
1. use **Report a vulnerability** in the repository **Security** tab if private vulnerability reporting is available;
2. otherwise open a minimal public issue asking for a private contact channel, without sensitive details.

Include when possible:
- affected version/commit;
- component;
- reproduction conditions;
- expected vs actual behavior;
- impact;
- whether it can expose credentials, reach private networks, bypass crawl restrictions or corrupt data.

## High-priority areas

- SSRF / localhost / private / link-local access;
- unsafe redirects;
- blocked-host/URL-safety bypass;
- `.env` or credential leakage;
- secrets in reports/logs;
- path traversal / unsafe file writes;
- injection through parsed content;
- DB migration corruption;
- dependencies with practical security impact;
- crawler limit/access restriction bypass.

## Secret exposure

If an API key, password, token, cookie or other credential is exposed:
1. revoke/rotate it immediately;
2. remove it from current code/config;
3. assume Git history may retain the old value;
4. replace public examples with placeholders.

Removing it from the latest file does not make the exposed credential safe again.

## Responsible crawling

Sprīdītis is intended for legitimate research on publicly accessible information. Do not use it to bypass authentication, paywalls, CAPTCHAs, access controls or other technical restrictions.
