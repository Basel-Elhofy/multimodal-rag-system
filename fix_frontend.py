"""Fix the frontend query call to send JSON body instead of URL param."""
from pathlib import Path

frontend_file = Path(__file__).resolve().parent / "frontend" / "app.js"
content = frontend_file.read_text()

# Replace the old fetch call with JSON body version
old_line = "const response = await fetch(`${API_BASE}/api/query?question=${encodeURIComponent(question)}`, {"
new_line = "const response = await fetch(`${API_BASE}/api/query`, {"

if old_line in content:
    content = content.replace(old_line, new_line)
    # Also replace the method line to add headers and body
    old_method = "            method: 'POST'\n        });"
    new_method = "            method: 'POST',\n            headers: { 'Content-Type': 'application/json' },\n            body: JSON.stringify({ question })\n        });"
    content = content.replace(old_method, new_method)
    frontend_file.write_text(content)
    print("Fixed: query now sends JSON body")
else:
    print("Pattern not found")
    # Show lines around the query call
    for i, line in enumerate(content.split('\n')):
        if 'api/query' in line or 'method' in line.lower() and 'POST' in line:
            print(f"  Line {i+1}: {repr(line)}")
