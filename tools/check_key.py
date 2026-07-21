"""Quick check: validate the Gemini key, list embedding/chat models, test one embed."""
import os
import sys

sys.stdout.reconfigure(errors="replace")

# load .env manually (no dependency)
for line in open(os.path.join(os.path.dirname(__file__), "..", ".env")):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1)
        os.environ.setdefault(k, v)

from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

print("--- models containing 'embed' or 'flash' ---")
for m in client.models.list():
    name = m.name.lower()
    if "embed" in name or "flash" in name:
        print(m.name)

print("\n--- test embedding ---")
r = client.models.embed_content(
    model="gemini-embedding-001",
    contents="ból zęba po wypełnieniu",
)
print("dims:", len(r.embeddings[0].values))
