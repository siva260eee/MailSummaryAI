import re
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup


def extract_links(text: str) -> List[str]:
    """Extract HTTP/HTTPS URLs from text."""
    # Regex pattern for URLs
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        # Clean up URL (remove trailing punctuation)
        url = url.rstrip('.,;:!?)')
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    return unique_urls


def fetch_url_content(url: str, timeout: int = 5) -> Optional[str]:
    """Fetch and extract text content from a URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
        response.raise_for_status()
        
        # Only process HTML content
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type.lower():
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Remove unwanted elements
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript']):
            tag.decompose()
        
        # Try to find main content area
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        
        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return '\n'.join(lines)
        
        return None
    except Exception as e:
        print(f"  Warning: Failed to fetch {url[:60]}... - {str(e)[:50]}")
        return None


def enrich_email_with_links(parsed: Dict[str, str], max_links: int = 10, max_chars_per_link: int = 1000, interactive: bool = True) -> Dict[str, str]:
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
    body = parsed.get('body', '')
    subject = parsed.get('subject', 'Unknown')[:60]
    links = extract_links(body)
    
    # Encode subject safely for console output
    safe_subject = subject.encode('ascii', errors='ignore').decode('ascii')
    print(f"  Checking links in '{safe_subject}' - Body length: {len(body)}")
    
    if not links:
        print(f"  No HTTP links found in this email")
        return parsed
    
    total_links = len(links)
    print(f"  Found {total_links} link(s) in '{subject}'")
    
    # If more links than max_links, ask user
    if interactive and total_links > max_links:
        print(f"  This email has {total_links} links. Fetch all {total_links} links? (y/n, default=fetch {max_links}): ", end='')
        try:
            response = input().strip().lower()
            if response == 'y' or response == 'yes':
                links_to_fetch = links
            elif response == 'n' or response == 'no':
                print(f"  Skipping link fetching for this email")
                return parsed
            else:
                # Default: use max_links
                links_to_fetch = links[:max_links]
                print(f"  Fetching first {max_links} links...")
        except (EOFError, KeyboardInterrupt):
            links_to_fetch = links[:max_links]
            print(f"\n  Fetching first {max_links} links...")
    else:
        links_to_fetch = links[:max_links]
    
    link_contents = []
    for i, url in enumerate(links_to_fetch, 1):
        print(f"    Fetching link {i}/{len(links_to_fetch)}: {url[:60]}...")
        content = fetch_url_content(url)
        if content:
            # Truncate content
            if len(content) > max_chars_per_link:
                content = content[:max_chars_per_link] + "..."
            link_contents.append(f"\n\n--- Content from {url} ---\n{content}")
    
    if link_contents:
        parsed['body'] = body + ''.join(link_contents)
        skipped = total_links - len(links_to_fetch)
        if skipped > 0:
            print(f"  ✓ Enriched with {len(link_contents)} link(s), skipped {skipped}")
        else:
            print(f"  ✓ Enriched with {len(link_contents)} link(s)")
    
    return parsed
