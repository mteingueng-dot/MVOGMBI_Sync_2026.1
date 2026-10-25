"""Crée l'icône de l'application (installation/MVOGMBI_Sync.ico) : deux flèches Clover -> Sage sur fond vert."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

taille = 256
image = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
d = ImageDraw.Draw(image)
d.rounded_rectangle((8, 8, taille - 8, taille - 8), radius=48, fill=(22, 115, 70))
try:
    police = ImageFont.truetype("segoeuib.ttf", 92)
except OSError:
    police = ImageFont.load_default()
d.text((taille / 2, 96), "MS", fill="white", font=police, anchor="mm")
# flèche de synchronisation
d.line((60, 180, 196, 180), fill=(255, 214, 102), width=16)
d.polygon([(196, 156), (232, 180), (196, 204)], fill=(255, 214, 102))
sortie = Path(__file__).with_name("MVOGMBI_Sync.ico")
image.save(sortie, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(sortie)
