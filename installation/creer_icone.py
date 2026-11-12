"""Prépare les images de l'application à partir du logo du Marché MVOG-MBI.

Entrées : mvogmbi_sync/ressources/logo.png (logo complet carré : emblème + « MARCHÉ MVOG-MBI SHERBROOKE »)
          mvogmbi_sync/ressources/embleme.png (emblème seul : Afrique, feuille d'érable, M et panier)
Sorties : installation/MVOGMBI_Sync.ico          icône du programme, du raccourci et de l'installateur (emblème)
          installation/assistant_grand.bmp       image latérale de l'assistant d'installation (164 x 314)
          installation/assistant_petit.bmp       petite image en haut de l'assistant (55 x 55)
"""
from pathlib import Path

from PIL import Image

ici = Path(__file__).resolve().parent
logo = Image.open(ici.parent / "mvogmbi_sync" / "ressources" / "logo.png").convert("RGBA")
fond_blanc = Image.new("RGBA", logo.size, "white")
logo_plein = Image.alpha_composite(fond_blanc, logo).convert("RGB")


def carre(image: Image.Image, cote: int, marge: float = 0.06) -> Image.Image:
    """Image centrée sur un carré blanc."""
    interieur = int(cote * (1 - 2 * marge))
    copie = image.copy()
    copie.thumbnail((interieur, interieur), Image.LANCZOS)
    fond = Image.new("RGB", (cote, cote), "white")
    fond.paste(copie, ((cote - copie.width) // 2, (cote - copie.height) // 2))
    return fond


# Emblème seul (sans le texte, illisible en petit) pour les petites icônes
embleme = Image.open(ici.parent / "mvogmbi_sync" / "ressources" / "embleme.png").convert("RGBA")
chariot = Image.alpha_composite(Image.new("RGBA", embleme.size, "white"), embleme).convert("RGB")
icone = carre(chariot, 256, 0.02)
tailles = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
icone.save(ici / "MVOGMBI_Sync.ico", sizes=tailles)
# la même pour la fenêtre de l'application et la barre des tâches
icone.save(ici.parent / "mvogmbi_sync" / "ressources" / "MVOGMBI_Sync.ico", sizes=tailles)

# Assistant d'installation : logo complet sur fond blanc
grand = Image.new("RGB", (164, 314), "white")
copie = logo_plein.copy()
copie.thumbnail((150, 290), Image.LANCZOS)
grand.paste(copie, ((164 - copie.width) // 2, (314 - copie.height) // 2))
grand.save(ici / "assistant_grand.bmp")
carre(chariot, 55, 0.02).save(ici / "assistant_petit.bmp")
print("Images créées dans", ici)
