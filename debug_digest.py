from src.store import get_connection, get_content_items
from src.pipeline import ensure_ai_cache_for_item
from src.roles import load_roles, get_role

conn = get_connection()
items = get_content_items(conn)
print(f'Total items: {len(items)}\n')

if items:
    item = items[0]
    print(f"Subject: {item['subject']}")
    print(f"Content ID: {item['content_id']}\n")
    
    # Get AI cache
    print("Getting AI cache...")
    ai_cache = ensure_ai_cache_for_item(item)
    print(f"Category: {ai_cache.get('category')}")
    print(f"Summary: {ai_cache.get('summary_md', '')[:200]}...")
    print(f"Topic tags: {ai_cache.get('topic_tags')}\n")
    
    # Check CTO role filtering
    roles = load_roles()
    cto_role = get_role("CTO", roles)
    print(f"CTO focus_categories: {cto_role.focus_categories}")
    print(f"CTO focus_topics: {cto_role.focus_topics}")
    
    # Check if item passes filters
    category_match = ai_cache.get('category') in cto_role.focus_categories
    print(f"\nCategory matches CTO filter: {category_match}")
    
    item_tags = [str(tag).lower() for tag in ai_cache.get('topic_tags', [])]
    focus_topics_lower = [t.lower() for t in cto_role.focus_topics]
    topic_match = any(tag in focus_topics_lower for tag in item_tags)
    print(f"Topic tags match CTO filter: {topic_match}")
    print(f"  Item tags: {item_tags}")
    print(f"  Focus topics: {focus_topics_lower}")
