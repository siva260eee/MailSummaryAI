from src.store import get_connection, get_content_items

conn = get_connection()
items = get_content_items(conn)
print(f'Total items in DB: {len(items)}')
for i, item in enumerate(items[:5], 1):
    print(f"{i}. {item['subject'][:80]}")
    print(f"   Content ID: {item.get('content_id', 'N/A')[:40]}")
    print(f"   Created: {item.get('created_at', 'N/A')}")
