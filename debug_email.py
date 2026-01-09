"""Debug script to examine raw email content."""
import os
from dotenv import load_dotenv
from src.icloud_imap import fetch_messages
from src.email_parse import parse_email

# Load environment
load_dotenv()

# Fetch emails
raw_messages = fetch_messages(
    search_query=os.getenv("IMAP_SEARCH", "UNSEEN"),
    mark_seen=False
)

print(f"\n=== Fetched {len(raw_messages)} emails ===\n")

if raw_messages:
    # Parse first email with 4000 char limit (default)
    parsed_4000 = parse_email(raw_messages[0], max_body_chars=4000)
    parsed_10000 = parse_email(raw_messages[0], max_body_chars=10000)
    
    if parsed_4000:
        print(f"Subject: {parsed_4000['subject']}\n")
        print(f"Body length with 4000 char limit: {len(parsed_4000['body'])} characters")
        print(f"Body length with 10000 char limit: {len(parsed_10000['body'])} characters\n")
        
        # Search for URLs in both
        import re
        urls_4000 = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', parsed_4000['body'])
        urls_10000 = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', parsed_10000['body'])
        
        print(f"URLs found in 4000-char body: {len(urls_4000)}")
        print(f"URLs found in 10000-char body: {len(urls_10000)}\n")
        
        if len(urls_4000) < len(urls_10000):
            print(f"⚠️ ISSUE FOUND: {len(urls_10000) - len(urls_4000)} URLs were cut off by 4000-char truncation!")
            print("\nURLs that were lost:")
            lost_urls = set(urls_10000) - set(urls_4000)
            for url in list(lost_urls)[:5]:
                print(f"  - {url}")
