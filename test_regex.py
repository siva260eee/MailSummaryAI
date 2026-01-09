import re

# Test text from the actual email
text_with_refs = """[27] https://tldr.tech/tech/manage?email=shiva.yagreswara%40icloud.com
[4] https://links.tldrnewsletter.com/xaeHa5"""

# The regex from link_fetcher.py
bare_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'

urls = re.findall(bare_pattern, text_with_refs)
print(f"Found {len(urls)} URLs:")
for url in urls:
    print(f"  - {url}")

# Test with 4000 char truncation
long_text = "A" * 3900 + "\n[1] https://example.com/link1\n[2] https://example.com/link2"
truncated = long_text[:4000]
urls_in_truncated = re.findall(bare_pattern, truncated)
print(f"\nIn truncated text (4000 chars): Found {len(urls_in_truncated)} URLs")
