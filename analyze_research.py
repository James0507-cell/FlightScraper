import re
from html import unescape

def analyze_html(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Remove tags to get text
    text = re.sub(r'<[^>]+>', ' ', html)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    print("--- TEXT CONTENT ---")
    print(text[:4000]) # First 4000 chars
    
    print("\n--- BUTTONS ---")
    buttons = re.findall(r'<button[^>]*aria-label="([^"]*)"[^>]*>', html)
    for btn in buttons:
        print(f"Button: {btn}")
        
    print("\n--- IMAGES/LOGOS ---")
    logos = re.findall(r'url\((https?://[^)]+)\)', html)
    for logo in list(set(logos)):
        print(f"Logo URL: {logo}")

if __name__ == "__main__":
    import os
    target = "amenities_research.html" if os.path.exists("amenities_research.html") else "expanded_card_research.html"
    analyze_html(target)
