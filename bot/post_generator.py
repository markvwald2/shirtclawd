import json
import random
from datetime import datetime
from data_loader import load_inventory

# Load shirts
shirts = load_inventory()

# Load content formats
with open("config/content_formats.json") as f:
    formats = json.load(f)

# Choose random shirt
shirt = random.choice(shirts)

# Choose random format
fmt = random.choice(formats)

# Build caption
caption = fmt["template"].format(
    sub_theme=shirt.get("sub_theme", shirt.get("theme"))
)

post = {
    "generated_at": datetime.utcnow().isoformat(),
    "shirt_id": shirt["shirt_id"],
    "shirt_name": shirt.get("shirt_name"),
    "post_type": fmt["type"],
    "caption": caption,
    "image_url": shirt.get("image_url"),
    "product_url": shirt.get("product_url")
}

# Write to queue
try:
    with open("marketing_queue.json") as f:
        queue = json.load(f)
except FileNotFoundError:
    queue = []

queue.append(post)

with open("marketing_queue.json", "w") as f:
    json.dump(queue, f, indent=2)

print("Post added to queue:")
print(post)