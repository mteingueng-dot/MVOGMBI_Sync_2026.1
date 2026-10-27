"""Captures d'écran de chaque page de MVOGMBI_Sync pour le manuel (documentation/captures/*.png).

L'application est ouverte sur une COPIE temporaire des données (config.toml + donnees/) : rien n'est modifié dans le
dossier d'origine, aucune lecture de boîte de courriel n'est lancée. Ensuite : python documentation/creer_manuel.py

    python documentation/capturer_ecrans.py [dossier de l'application installée] [--langue en]

En anglais, les captures vont dans documentation/captures/en/ (manuel anglais).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
SORTIE = ICI / "captures"
INSTALLEE = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "MVOGMBI_Sync"


def capturer(hwnd, chemin: Path) -> None:
    """Image d'une fenêtre par PrintWindow (même recouverte)."""
    from PIL import Image

    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    r = w.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    largeur, hauteur = r.right - r.left, r.bottom - r.top
    dc_ecran = u.GetDC(0)
    dc = g.CreateCompatibleDC(dc_ecran)
    bmp = g.CreateCompatibleBitmap(dc_ecran, largeur, hauteur)
    g.SelectObject(dc, bmp)
    u.PrintWindow(hwnd, dc, 2)  # PW_RENDERFULLCONTENT

    class BMI(ctypes.Structure):
        _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG), ("biPlanes", w.WORD),
                    ("biBitCount", w.WORD), ("biCompression", w.DWORD), ("biSizeImage", w.DWORD),
                    ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD),
                    ("biClrImportant", w.DWORD)]

    tampon = (ctypes.c_byte * (largeur * hauteur * 4))()
    bmi = BMI(ctypes.sizeof(BMI), largeur, -hauteur, 1, 32, 0, 0, 0, 0, 0, 0)
    g.GetDIBits(dc, bmp, 0, hauteur, tampon, ctypes.byref(bmi), 0)
    Image.frombuffer("RGBA", (largeur, hauteur), bytes(tampon), "raw", "BGRA").convert("RGB").save(chemin)
    g.DeleteObject(bmp)
    g.DeleteDC(dc)
    u.ReleaseDC(0, dc_ecran)


def choisir_langue(config: Path, langue: str) -> None:
    """Fixe [general] langue dans le config.toml de la copie."""
    texte = config.read_text(encoding="utf-8")
    if re.search(r"(?m)^langue\s*=", texte):
        texte = re.sub(r'(?m)^langue\s*=.*$', f'langue = "{langue}"', texte, count=1)
    elif "[general]" in texte:
        texte = texte.replace("[general]", f'[general]\nlangue = "{langue}"', 1)
    else:
        texte = f'[general]\nlangue = "{langue}"\n\n' + texte
    config.write_text(texte, encoding="utf-8")


def main(origine: Path, langue: str = "fr") -> None:
    global SORTIE
    if langue != "fr":
        SORTIE = SORTIE / langue
    copie = Path(tempfile.mkdtemp(prefix="mvogmbi_captures_"))
    shutil.copy2(origine / "config.toml", copie / "config.toml")
    choisir_langue(copie / "config.toml", langue)
    shutil.copytree(origine / "donnees", copie / "donnees")
    os.environ["MVOGMBI_RACINE"] = str(copie)
    sys.path.insert(0, str(ICI.parent))
    from mvogmbi_sync.utilisateurs import ADMIN, Registre

    comptes = Registre(copie)  # comptes fictifs, sur la copie seulement (page Utilisateurs)
    comptes.utilisateurs = []
    for nom, profil in (("Gérant", ADMIN), ("Comptable", "Comptable"), ("Caisse 1", "Employé")):
        comptes.ajouter(nom, profil, "exemple123")
    comptes.enregistrer()
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    sys.path.insert(0, str(ICI.parent))
    from mvogmbi_sync import interface, page_paiements
    from mvogmbi_sync.langues import t
    from mvogmbi_sync.paiements_fournisseurs import PROPOSE

    page_paiements.PagePaiements._premiere_lecture = lambda self: None  # pas de lecture de la boîte
    SORTIE.mkdir(exist_ok=True)
    app = interface.Application(copie)
    app.geometry("1320x980+0+0")
    etapes = []

    def suivant():
        if etapes:
            etapes.pop(0)()
        else:
            app.destroy()

    def page(index, nom, apres=None, delai=1800):
        def montrer():
            app.aller(index)
            if apres:
                apres()
            app.after(delai, lambda: (app.update(),
                                      capturer(ctypes.windll.user32.GetParent(app.winfo_id()), SORTIE / f"{nom}.png"),
                                      suivant()))
        etapes.append(montrer)

    def correspondance_tous():
        p = app.page_correspondance
        p.filtre_affiche.set(next(k for k, v in p.libelles_filtres.items() if v.startswith("Tous")))
        p.afficher()
        enfants = p.tableau.get_children()
        if len(enfants) > 3:
            p.tableau.selection_set(enfants[3])
            p.selectionner()

    def facture_ouverte():
        p = app.page_fournisseurs
        if p.liste.get_children():
            p.liste.selection_set(p.liste.get_children()[0])
            p.choisir_facture()
            if p.lignes.get_children():
                p.lignes.selection_set(p.lignes.get_children()[0])
                p.choisir_ligne()

    def virement_propose():
        p = app.page_paiements
        p.filtre.set(t("Tous"))
        p.afficher()
        cible = next((i for i, x in enumerate(p.registre.paiements) if x.etat == PROPOSE), None)
        if cible is not None and p.tableau.exists(str(cible)):
            p.tableau.selection_set(str(cible))
            p.choisir()

    i = interface
    for index, nom in ((i.ACCUEIL, "00_accueil"), (i.CLOVER, "01_clover"), (i.SAGE, "02_sage"),
                       (i.COURRIEL, "03_courriel"), (i.AUTOMATISATION, "04_automatisation")):
        page(index, nom)
    page(i.CORRESPONDANCE, "05_correspondance", correspondance_tous, delai=3000)
    page(i.TABLEAU, "06_tableau_de_bord", delai=2500)
    page(i.ENCAISSEMENTS, "07_encaissements")
    page(i.FOURNISSEURS, "08_factures_fournisseurs", delai=2500)
    page(i.FOURNISSEURS, "08b_facture_detail", facture_ouverte, delai=2500)
    page(i.PAIEMENTS, "09_paiements", virement_propose)
    page(i.RAPPROCHEMENT, "10_rapprochement", lambda: app.page_rapprochement.actualiser(), delai=12000)
    page(i.GUIDE, "11_guide")
    page(i.FAQ, "12_faq")
    page(i.UTILISATEURS, "13_utilisateurs")
    page(i.RAPPORTS, "14_rapports", lambda: app.page_rapports.actualiser(), delai=30000)
    app.after(2500, suivant)
    app.mainloop()
    shutil.rmtree(copie, ignore_errors=True)
    print("Captures :", ", ".join(sorted(p.name for p in SORTIE.glob("*.png"))))


if __name__ == "__main__":
    arguments = [a for a in sys.argv[1:] if not a.startswith("--")]
    langue = sys.argv[sys.argv.index("--langue") + 1] if "--langue" in sys.argv else "fr"
    arguments = [a for a in arguments if a != langue]
    main(Path(arguments[0]) if arguments else INSTALLEE, langue)
