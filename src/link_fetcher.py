import re
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup


# URL patterns to exclude (ads, tracking, social, etc.)
# Add more patterns here as you discover them to continuously improve filtering
EXCLUDE_URL_PATTERNS = [
    # Advertising & sponsorship
    r"advertise\.tldr\.tech",
    r"advertise\.",
    r"/ads?/",
    r"/sponsor",
    # Job postings
    r"jobs\.ashbyhq\.com",
    r"/jobs/",
    r"/careers/",
    # Newsletter management
    r"/unsubscribe",
    r"/manage\?",
    r"/preferences",
    r"/settings",
    # Referral & tracking
    r"refer\.tldr\.tech",
    r"/refer/",
    r"/referral",
    r"hub\.sparklp\.co",
    r"a\.tldrnewsletter\.com/web-version",
    r"a\.tldrnewsletter\.com/unsubscribe",
    # Social media profiles (usually not valuable article content)
    r"twitter\.com/",
    r"x\.com/",
    r"linkedin\.com/in/",
    r"linkedin\.com/feed/",
    # Generic sign-up pages
    r"/signup",
    r"/sign-up",
    r"/register",
]


def is_valuable_url(url: str) -> bool:
    """Check if URL is valuable content (not ads, tracking, social profiles, etc.)."""
    url_lower = url.lower()

    for pattern in EXCLUDE_URL_PATTERNS:
        if re.search(pattern, url_lower):
            return False

    return True


def extract_links(text: str) -> List[str]:
    """Extract HTTP/HTTPS URLs from text."""
    bracket_pattern = r"\[?(https?://[^\s<>\"{}|\\^`\[\]]+)\]?"
    bare_pattern = r"https?://[^\s<>\"{}|\\^`\[\]]+"

    urls = re.findall(bracket_pattern, text)
    if not urls:
        urls = re.findall(bare_pattern, text)

    seen = set()
    unique_urls = []
    filtered_count = 0

    for url in urls:
        url = url.rstrip(".,;:!?)]").lstrip("[")
        if url not in seen and url.startswith(("http://", "https://")):
            if is_valuable_url(url):
                seen.add(url)
                unique_urls.append(url)
            else:
                filtered_count += 1

    if filtered_count > 0:
        print(f"    Filtered out {filtered_count} ad/tracking/social links to save tokens")

    return unique_urls


def fetch_url_content(url: str, timeout: int = 5) -> Optional[str]:
    """Fetch and extract text content from a URL."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            )
        }
        response = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type.lower():
            return None

        soup = BeautifulSoup(response.text, "lxml")

        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
            tag.decompose()

        main_content = soup.find("main") or soup.find("article") or soup.find("body")

        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines)

        return None
    except Exception as exc:
        print(f"  Warning: Failed to fetch {url[:60]}... - {str(exc)[:50]}")
        return None


def select_links_to_fetch(
    links: List[str],
    subject: str,
    max_links: int = 10,
    interactive: bool = True,
) -> List[str]:
    if not links:
        return []

    total_links = len(links)
    print(f"  Found {total_links} link(s) in '{subject}'")

    if interactive and total_links > max_links:
        print(
            f"  This email has {total_links} links. Fetch all {total_links} links? "
            f"(y/n, default=fetch {max_links}): ",
            end="",
        )
        try:
            response = input().strip().lower()
            if response in {"y", "yes"}:
                return links
            if response in {"n", "no"}:
                print("  Skipping link fetching for this email")
                return []
            print(f"  Fetching first {max_links} links...")
        except (EOFError, KeyboardInterrupt):
            print(f"\n  Fetching first {max_links} links...")
        return links[:max_links]

    return links[:max_links]


def fetch_links_content(
    links_to_fetch: List[str],
    max_chars_per_link: int = 1000,
) -> Dict[str, str]:
    link_contents: Dict[str, str] = {}
    for i, url in enumerate(links_to_fetch, 1):
        print(f"    Fetching link {i}/{len(links_to_fetch)}: {url[:60]}...")
        content = fetch_url_content(url)
        if content:
            if len(content) > max_chars_per_link:
                content = content[:max_chars_per_link] + "..."
            link_contents[url] = content
    return link_contents


def fetch_links_interactive(
    links: List[str],
    subject: str,
    max_links: int = 10,
    max_chars_per_link: int = 1000,
    interactive: bool = True,
) -> Dict[str, str]:
    links_to_fetch = select_links_to_fetch(
        links, subject=subject, max_links=max_links, interactive=interactive
    )
    if not links_to_fetch:
        return {}

    link_contents = fetch_links_content(
        links_to_fetch, max_chars_per_link=max_chars_per_link
    )
    if link_contents:
        skipped = len(links) - len(links_to_fetch)
        if skipped > 0:
            print(f"  - Enriched with {len(link_contents)} link(s), skipped {skipped}")
        else:
            print(f"  - Enriched with {len(link_contents)} link(s)")
    return link_contents


def enrich_email_with_links(
    parsed: Dict[str, str],
    max_links: int = 10,
    max_chars_per_link: int = 1000,
    interactive: bool = True,
) -> Dict[str, str]:
    """
    Extract links from email, fetch their content, and add to the body.

    Args:
        parsed: Parsed email dict with 'subject', 'body', etc.
        max_links: Maximum number of links to fetch
        max_chars_per_link: Max characters to include from each link
        interactive: If True, prompt user when many links are found

    Returns:
        Updated parsed dict with link content appended to body
    """
    body_for_links = parsed.get("full_body", parsed.get("body", ""))
    body = parsed.get("body", "")
    subject = parsed.get("subject", "Unknown")[:60]
    links = extract_links(body_for_links)

    safe_subject = subject.encode("ascii", errors="ignore").decode("ascii")
    print(f"  Checking links in '{safe_subject}'")

    if not links:
        print("    No HTTP/HTTPS URLs found")
        return parsed

    link_contents = fetch_links_interactive(
        links,
        subject=subject,
        max_links=max_links,
        max_chars_per_link=max_chars_per_link,
        interactive=interactive,
    )

    if link_contents:
        appended = []
        for url, content in link_contents.items():
            appended.append(f"\n\n--- Content from {url} ---\n{content}")
        parsed["body"] = body + "".join(appended)

    return parsed
