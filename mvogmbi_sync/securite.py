"""Protections communes (analyse de sécurité du 2026-11-13, demande du propriétaire : « corrige tous les points de
sécurité »).

- Fichiers reçus (reçus de dépense, factures fournisseurs, états RIA) : seuls les PDF et les images sont acceptés,
  reconnus par leur CONTENU et pas seulement par leur nom ; un fichier ne s'ouvre jamais sous Windows s'il n'est pas
  l'un d'eux (un « reçu.exe » ouvert par « Voir le reçu » lançait un programme sur le serveur).
- Exports Excel et CSV : un texte venu de l'extérieur qui commence par « = » (Excel) ou par « = + - @ » (CSV) n'est
  jamais pris pour une formule.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# extension -> débuts de fichier possibles
SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".tif": (b"II*\x00", b"MM\x00*"),
    ".tiff": (b"II*\x00", b"MM\x00*"),
    ".bmp": (b"BM",),
    ".heic": (b"",),
    ".heif": (b"",),
}
DOCUMENTS = tuple(SIGNATURES)


class FichierRefuse(ValueError):
    """Fichier qui n'est ni un PDF ni une image (message à afficher tel quel)."""


def document_permis(nom: str, contenu: bytes) -> bool:
    """Le nom a une extension de document (PDF ou image) ET le contenu commence comme ce type de fichier."""
    extension = Path(nom or "").suffix.lower()
    debuts = SIGNATURES.get(extension)
    if not debuts:
        return False
    if extension == ".pdf":  # quelques octets avant « %PDF » sont tolérés par les lecteurs
        return b"%PDF" in contenu[:1024]
    if extension in (".heic", ".heif"):  # photo d'iPhone : « ftyp » + marque HEIF
        return contenu[4:8] == b"ftyp" and contenu[8:12] in (b"heic", b"heix", b"mif1", b"msf1", b"heif", b"hevc")
    return any(contenu.startswith(d) for d in debuts)


def verifier_document(nom: str, contenu: bytes) -> None:
    if not document_permis(nom, contenu):
        raise FichierRefuse(f"Fichier refusé ({Path(nom or '').name or 'sans nom'}) : seuls les PDF et les images "
                            "(JPEG, PNG, TIFF, BMP) sont acceptés.")


def verifier_fichier(chemin: Path) -> None:
    chemin = Path(chemin)
    try:
        with open(chemin, "rb") as f:
            debut = f.read(1024)
    except OSError as exc:
        raise FichierRefuse(f"Fichier illisible : {chemin.name} ({exc})") from exc
    verifier_document(chemin.name, debut)


def ouvrir_document(chemin: Path) -> None:
    """Ouvre un fichier REÇU (reçu, facture, état) dans son programme, seulement si c'est un PDF ou une image."""
    verifier_fichier(chemin)
    os.startfile(str(chemin))  # noqa: S606 — type vérifié juste avant


# --------------------------------------------------------------------------------------------- Excel et CSV
_NOMBRE = re.compile(r"^[-+]?[\d\s  .,]*\d[\d\s  .,]*\s*\$?%?$")


def texte_csv(valeur):
    """Valeur d'une cellule CSV : un texte qui commence par = + - @ (ou tabulation, retour) est précédé d'une
    apostrophe, sauf un vrai nombre (« -12,50 », « +3 »)."""
    if isinstance(valeur, str) and valeur[:1] in ("=", "+", "-", "@", "\t", "\r") and not _NOMBRE.match(valeur):
        return "'" + valeur
    return valeur


def proteger_excel() -> None:
    """openpyxl écrit tout texte qui commence par « = » comme une FORMULE : ici il reste du texte, partout dans
    l'application (aucun module n'écrit de formule exprès)."""
    from openpyxl.cell import cell as module

    _proteger(module)


class _Crochet:
    """Applique `proteger_excel` dès qu'openpyxl est chargé (l'importer d'office coûterait ~1 s au démarrage)."""

    @staticmethod
    def find_spec(nom, chemin=None, cible=None):
        if nom != "openpyxl.cell.cell":
            return None
        import sys

        try:
            for chercheur in sys.meta_path:
                if chercheur is _Crochet:
                    continue
                spec = getattr(chercheur, "find_spec", lambda *a: None)(nom, chemin, cible)
                if spec is not None and spec.loader is not None:
                    spec.loader = _Chargeur(spec.loader)  # chargeur d'origine jamais modifié (commun dans l'exe)
                    return spec
        except Exception:  # noqa: BLE001 — le crochet ne doit jamais empêcher openpyxl de se charger
            return None
        return None


class _Chargeur:
    """Chargeur d'origine, puis la protection appliquée au module chargé."""

    def __init__(self, origine):
        self._origine = origine

    def create_module(self, spec):
        return self._origine.create_module(spec)

    def exec_module(self, module):
        self._origine.exec_module(module)
        try:
            _proteger(module)
        except Exception:  # noqa: BLE001
            pass

    def __getattr__(self, nom):
        return getattr(self._origine, nom)


def _proteger(module) -> None:
    if getattr(module.Cell, "_mvogmbi_protege", False):
        return
    origine = module.Cell._bind_value

    def _bind_value(self, value):
        origine(self, value)
        if self.data_type == "f" and isinstance(value, str):
            self.data_type = "s"

    module.Cell._bind_value = _bind_value
    module.Cell._mvogmbi_protege = True


def installer_protections() -> None:
    import sys

    if "openpyxl.cell.cell" in sys.modules:
        _proteger(sys.modules["openpyxl.cell.cell"])
    elif _Crochet not in sys.meta_path:
        sys.meta_path.insert(0, _Crochet)
