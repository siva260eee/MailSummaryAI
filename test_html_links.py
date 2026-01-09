from bs4 import BeautifulSoup

# Test HTML with links
test_html = """
<html>
<body>
<h1><a href="https://example.com/article1">xAI leaked financials</a></h1>
<p>Some text with <a href="https://example.com/article2">Musk's xAI Burns</a> money.</p>
<a href="https://example.com/signup">Sign Up</a>
</body>
</html>
"""

soup = BeautifulSoup(test_html, "lxml")

print("Original HTML structure:")
print(soup.prettify()[:500])

print("\n\nFinding all anchor tags:")
for a_tag in soup.find_all('a', href=True):
    href = a_tag.get('href', '')
    text = a_tag.get_text(strip=True)
    print(f"  Link: '{text}' -> {href}")
    if href and href.startswith(('http://', 'https://')):
        a_tag.replace_with(f"{text} {href} ")

print("\n\nAfter replacement:")
text = soup.get_text(separator='\n', strip=True)
print(text)

print("\n\nSearching for URLs in text:")
import re
url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
urls = re.findall(url_pattern, text)
print(f"Found {len(urls)} URLs: {urls}")
