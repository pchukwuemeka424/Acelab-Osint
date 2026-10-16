# Data sources

| Source | When it runs | Notes |
| --- | --- | --- |
| demonstration | `DEMO_MODE=true`, or no live source is enabled | For a domain, URL, address, or fingerprint, stores the submitted indicator only. No infrastructure is invented. |
| dns | Live mode and the DNS source is enabled | Resolver answers only. Non-public answers are stored and not contacted. |
| rdap | Live mode and RDAP is enabled | `https://rdap.org` only. The Whois tab stores the published registrar, dates, status, nameservers, and contacts. A field the registry withholds is labelled not published. |
| ct | Live mode and certificate transparency is enabled | `https://crt.sh` JSON. Free endpoints are rate limited and sometimes slow. |
| ripe | Live mode and RIPEstat is enabled | `https://stat.ripe.net` prefix, ASN, holder, and country for up to eight current public addresses. This is the network announcing the address now, not a history of past DNS answers. |
| wayback | Live mode and Wayback is enabled | `https://web.archive.org` capture dates only. Archived pages are not downloaded. |
| page | Live mode and the page source is enabled | One request to the submitted host, then up to 12 linked pages on that same host. Each response contributes the title, description, server header, technology hints, SEO fields, contacts, linked files, attribution text, and image URLs. A recorded logo is fetched when the Logo tab is opened. |
| profiles | A full-name investigation | A public web search. A page is kept when it contains that name. A match is a lead, not proof of who operates the site. Generic pages and mail-provider sites are not stored. No API key. These checks run even when demonstration mode is on. |
| urlhaus | Live mode and URLHaus is enabled | `https://urlhaus-api.abuse.ch`. Enable only if you accept that provider's terms. A malware-family label is not an actor name. |
| openrouter | Report narration when a key is set and the source is enabled | Chat completions only. The key is an environment variable. |

Public DNS, RDAP, certificate transparency, RIPEstat, Wayback, and the single page request do not need an API key. They do not provide paid passive-DNS address history, backlinks, or search rankings. Demonstration mode ignores the live infrastructure toggles even if an administrator enables them. A full name still runs the public page check. Connectors time out, do not follow redirects to other hosts, and refuse destinations that resolve to a blocked address. The page request may contact only the submitted host.

Cached live results are kept in the worker process for a few minutes. There is no separate observation cache in Redis in this version. Redis is the job broker.
