"""Quick check: validate the Gemini key, list embedding/chat models, test one embed."""
import os
import sys

sys.stdout.reconfigure(errors="replace")

# load .env manually (no dependency)
_env_loaded = False
for _env_path in [Path(__file__).resolve().parent.parent / ".env", Path.cwd() / ".env"]:
    if _env_path.exists():
        for line in open(_env_path):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)
        _env_loaded = True
        break
if not _env_loaded:
    print("WARNING: .env not found")

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
