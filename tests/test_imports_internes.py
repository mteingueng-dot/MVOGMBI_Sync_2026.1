"""Chaque « from .module import nom » de l'application (aussi ceux écrits dans les fonctions) désigne un nom qui
existe : un import faux dans une fonction n'apparaît qu'à l'exécution (constat du 2026-11-06 : le traitement de nuit
s'arrêtait sur « cannot import name 'Registre' from paiements_fournisseurs », sans courriel ni archivage)."""
import ast
import importlib
from pathlib import Path

import mvogmbi_sync

RACINE = Path(mvogmbi_sync.__file__).parent


def test_tous_les_imports_internes_existent():
    fautes = []
    for fichier in RACINE.rglob("*.py"):
        paquet = "mvogmbi_sync" + "".join("." + p for p in fichier.parent.relative_to(RACINE).parts)
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if not isinstance(noeud, ast.ImportFrom) or not noeud.level:
                continue
            base = paquet.rsplit(".", noeud.level - 1)[0] if noeud.level > 1 else paquet
            cible = f"{base}.{noeud.module}" if noeud.module else base
            try:
                module = importlib.import_module(cible)
            except Exception as exc:
                fautes.append(f"{fichier.name}:{noeud.lineno} {cible} : {exc}")
                continue
            for alias in noeud.names:
                if alias.name == "*" or hasattr(module, alias.name):
                    continue
                try:
                    importlib.import_module(f"{cible}.{alias.name}")
                except ImportError:
                    fautes.append(f"{fichier.name}:{noeud.lineno} {cible}.{alias.name} introuvable")
    assert not fautes, "\n".join(fautes)
