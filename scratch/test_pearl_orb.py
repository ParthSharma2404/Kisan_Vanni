import math
from PIL import Image, ImageDraw, ImageFilter

W, H = 240, 240
cx, cy = W // 2, H // 2
R = 72

# Create RGBA image with dark background
img = Image.new("RGBA", (W, H), (14, 10, 12, 255))
draw = ImageDraw.Draw(img)

# 1. Outer ambient warm glow
halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
halo_draw = ImageDraw.Draw(halo)
for r in range(int(R * 1.55), int(R * 0.7), -2):
    t = (r - R * 0.7) / (R * 0.85)
    alpha = int((1.0 - t) * 60)
    halo_draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(180, 80, 70, alpha))
img = Image.alpha_composite(img, halo)

# 2. Sphere mask
sphere_mask = Image.new("L", (W, H), 0)
mask_draw = ImageDraw.Draw(sphere_mask)
mask_draw.ellipse((cx - R, cy - R, cx + R, cy + R), fill=255)

# 3. Inside sphere - Mesh gradient blobs
sphere_content = Image.new("RGBA", (W, H), (210, 185, 235, 255)) # base lilac
s_draw = ImageDraw.Draw(sphere_content)

# Layer blobs
blobs = [
    # (x_off, y_off, radius, color_rgba)
    (-R*0.25, R*0.05, int(R*0.95), (245, 158, 11, 230)),   # Amber Gold
    (R*0.35, R*0.12, int(R*0.85), (225, 29, 72, 210)),    # Sunset Coral
    (R*0.15, -R*0.35, int(R*0.95), (168, 85, 247, 210)),  # Lavender Violet
    (-R*0.05, R*0.35, int(R*0.75), (251, 146, 60, 200)),  # Warm Peach
    (0, 0, int(R*0.55), (255, 250, 220, 160)),            # Center Pearlescent
]

blob_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
b_draw = ImageDraw.Draw(blob_layer)
for bx, by, br, color in blobs:
    b_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(b_img)
    x = cx + bx
    y = cy + by
    bd.ellipse((x - br, y - br, x + br, y + br), fill=color)
    b_img = b_img.filter(ImageFilter.GaussianBlur(radius=28))
    blob_layer = Image.alpha_composite(blob_layer, b_img)

sphere_content = Image.alpha_composite(sphere_content, blob_layer)

# Milky pearl rim vignette
vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
v_draw = ImageDraw.Draw(vignette)
for r in range(int(R * 0.65), R):
    t = (r - R * 0.65) / (R * 0.35)
    alpha = int(t * 190)
    v_draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(225, 210, 248, alpha), width=2)
vignette = vignette.filter(ImageFilter.GaussianBlur(radius=2))
sphere_content = Image.alpha_composite(sphere_content, vignette)

# Composite sphere onto image using mask
img.paste(sphere_content, (0, 0), sphere_mask)

# 4. Center 7-ring Rosette
rosette_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
r_draw = ImageDraw.Draw(rosette_layer)
r_ring = 5.5
dist = 10.5

# 7 rings (1 center + 6 outer)
ring_centers = [(cx, cy)]
for i in range(6):
    angle = i * (math.pi / 3)
    rx = cx + math.cos(angle) * dist
    ry = cy + math.sin(angle) * dist
    ring_centers.append((rx, ry))

for rx, ry in ring_centers:
    r_draw.ellipse((rx - r_ring, ry - r_ring, rx + r_ring, ry + r_ring), outline=(255, 245, 235, 210), width=2)

rosette_glow = rosette_layer.filter(ImageFilter.GaussianBlur(radius=2))
img = Image.alpha_composite(img, rosette_glow)
img = Image.alpha_composite(img, rosette_layer)

# 5. Crisp glass outer edge line
edge_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
e_draw = ImageDraw.Draw(edge_layer)
e_draw.ellipse((cx - R, cy - R, cx + R, cy + R), outline=(255, 255, 255, 120), width=1)
img = Image.alpha_composite(img, edge_layer)

output_path = r'C:\Users\Lenovo\.gemini\antigravity\brain\8817b2f8-65ea-4b6d-9168-28aa829d19c5\scratch\test_pearl_orb.png'
img.save(output_path)
print('Saved test image to:', output_path)

