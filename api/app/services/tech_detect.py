from __future__ import annotations

# Tech names that are genuine age markers — not merely "old" CMS, but dead/EOL technology.
# WordPress, jQuery (generic), Bootstrap etc. are detected separately but are NOT here
# because their current versions are maintained. Only include a tech when its *presence*
# alone (without version context) proves obsolescence (dead standard) OR when a
# version-specific pattern pinpoints an EOL release.
OBSOLESCENCE_SIGNALS: frozenset[str] = frozenset({
    "jQuery 1.x",       # EOL 2016 — jQuery 1.x branch
    "jQuery 2.x",       # EOL 2016 — jQuery 2.x branch
    "Font Awesome 4",   # superseded by FA5 in 2017; FA4 CDN path is a firm marker
    "Flash",            # dead standard; Chrome disabled NPAPI/Flash in 2020
    "Prototype.js",     # abandoned ~2010
    "Scriptaculous",    # depends on Prototype.js, same era
    "MooTools",         # last release 2016, considered abandoned
    "FrontPage",        # Microsoft FrontPage discontinued in 2003
})

_HEADER_RULES: list[tuple[str, str, str]] = [
    ("Server", "nginx", "Nginx"),
    ("Server", "apache", "Apache"),
    ("Server", "iis", "IIS"),
    ("Server", "litespeed", "LiteSpeed"),
    ("X-Powered-By", "php", "PHP"),
    ("X-Powered-By", "asp.net", "ASP.NET"),
    ("X-Powered-By", "express", "Express"),
    ("CF-Ray", "", "Cloudflare"),
    ("X-Shopify-Stage", "", "Shopify"),
    ("X-Wix-Request-Id", "", "Wix"),
    ("X-Squarespace-Id", "", "Squarespace"),
]

_HTML_RULES: list[tuple[str, str]] = [
    # ── CMS ──────────────────────────────────────────────────────────────────
    ("wp-content", "WordPress"),
    ("wp-includes", "WordPress"),
    ("/sites/default/files", "Drupal"),
    ("joomla", "Joomla"),
    ("prestashop", "PrestaShop"),
    ("shopify.com/s/files", "Shopify"),
    ("cdn.wix.com", "Wix"),
    ("webflow.com", "Webflow"),
    ("elementor", "Elementor"),           # Elementor page builder (WordPress)
    ("woocommerce", "WooCommerce"),
    ("typo3", "TYPO3"),
    ("magento", "Magento"),
    ("opencart", "OpenCart"),
    # ── JS frameworks ─────────────────────────────────────────────────────────
    ("jquery", "jQuery"),                 # generic — any version; see versioned rules below
    ("react", "React"),
    ("vue.js", "Vue.js"),
    ("angular", "Angular"),
    ("next.js", "Next.js"),
    ("nuxt", "Nuxt"),
    # ── CSS / UI ──────────────────────────────────────────────────────────────
    ("bootstrap", "Bootstrap"),
    ("tailwind", "Tailwind"),
    # ── Analytics / tracking ──────────────────────────────────────────────────
    ("gtag/js", "Google Analytics"),
    ("google-analytics.com", "Google Analytics"),
    ("googletagmanager.com", "Google Tag Manager"),
    ("matomo.js", "Matomo"),
    ("piwik.js", "Matomo"),               # legacy Matomo script name
    # ── Icons (generic — FA5 / FA6 paths, or fontawesome package name) ────────
    ("font-awesome", "Font Awesome"),
    ("fontawesome", "Font Awesome"),
    # ── Obsolescence markers (versioned / dead standards) ─────────────────────
    # jQuery 1.x / 2.x — CDN paths like jquery-1.12.4.min.js or jquery/1.12/
    ("jquery-1.", "jQuery 1.x"),
    ("jquery/1.", "jQuery 1.x"),
    ("jquery-2.", "jQuery 2.x"),
    ("jquery/2.", "jQuery 2.x"),
    # Font Awesome 4 — CDN paths like /font-awesome/4.7.0/ or /fontawesome/4.
    ("/font-awesome/4.", "Font Awesome 4"),
    ("/fontawesome/4.", "Font Awesome 4"),
    # Adobe Flash
    ("x-shockwave-flash", "Flash"),
    ("flashplayer", "Flash"),
    # Pre-jQuery JS libraries (2000s era)
    ("prototype.js", "Prototype.js"),
    ("scriptaculous", "Scriptaculous"),
    ("mootools", "MooTools"),
    # Microsoft FrontPage generator meta tag
    ("microsoft frontpage", "FrontPage"),
]


def detect_tech(page: dict) -> list[str]:
    found: set[str] = set()
    headers = {k.lower(): v for k, v in page.get("headers", {}).items()}
    html_lower = page.get("html", "").lower()

    for header, keyword, tech in _HEADER_RULES:
        val = headers.get(header.lower(), "")
        if keyword == "" and val:
            found.add(tech)
        elif keyword and keyword in val.lower():
            found.add(tech)

    for pattern, tech in _HTML_RULES:
        if pattern.lower() in html_lower:
            found.add(tech)

    return sorted(found)
