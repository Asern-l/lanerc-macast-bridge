from pathlib import Path

from PIL import Image, ImageDraw


root = Path(__file__).resolve().parents[1]
target = root / "lanerc_assets" / "app.ico"
size = 256
image = Image.new("RGBA", (size, size), (18, 49, 71, 255))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((5, 5, 250, 250), radius=58, fill=(18, 49, 71, 255))
draw.rounded_rectangle((58, 64, 198, 163), radius=8, outline=(239, 251, 255, 255), width=14)
draw.line((92, 197, 164, 197), fill=(239, 251, 255, 255), width=14)
draw.line((128, 163, 128, 197), fill=(239, 251, 255, 255), width=14)
draw.arc((69, 91, 145, 167), 270, 360, fill=(47, 184, 178, 255), width=12)
draw.arc((69, 68, 169, 168), 270, 360, fill=(47, 184, 178, 255), width=12)
image.save(target, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(target)
