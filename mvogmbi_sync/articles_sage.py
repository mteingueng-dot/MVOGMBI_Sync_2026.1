"""Lecture de la liste des articles exportée de Sage 50 (fichier texte, Windows-1252).

Format observé (« donnees/Article.txt ») : une ligne d'en-tête « 33101,3,Inventory », puis une ligne par article :
numéro, description, type (Inventory / Service), unité, prix, prix, compte d'actif,
compte de revenus, compte CPV, compte d'écart, description 2, unité de vente.

L'export de Sage n'est pas un CSV valide : les guillemets dans les descriptions ne sont pas doublés
(« Kids 28" 04 ») et une description peut contenir un retour à la ligne. On reconnaît donc chaque
article par sa structure (« ","Inventory","Chaque", » puis les nombres) plutôt qu'avec un lecteur CSV.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ARTICLE = re.compile(
    r'^"(?P<numero_description>.*)","(?P<type>Inventory|Service)","(?P<unite>[^"]*)",'
    r'(?P<nombres>[-\d.,]*),"(?P<description2>.*)","(?P<unite_vente>[^"]*)",\s*$'
)
FIN_ARTICLE = re.compile(r'","[^"]*",\s*$')


@dataclass(frozen=True)
class ArticleSage:
    numero: str
    description: str
    type: str
    compte_revenus: str


def reparer_texte(texte: str) -> str:
    """Corrige les accents abîmés par une double conversion (« DepulpÃ© » -> « Depulpé »)."""
    if "Ã" not in texte and "Â" not in texte:
        return texte
    try:
        return texte.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texte


def _enregistrements(texte: str):
    """Regroupe les lignes physiques en articles (une description peut s'étendre sur plusieurs lignes)."""
    tampon: list[str] = []
    for ligne in texte.splitlines():
        if not tampon and not ligne.startswith('"'):
            continue  # en-tête « 33101,3,Inventory » ou ligne vide
        tampon.append(ligne)
        if FIN_ARTICLE.search(ligne) and re.search(r'","(Inventory|Service)","', " ".join(tampon)):
            yield " ".join(l.strip() for l in tampon)
            tampon = []


def ecrire_copie(articles: list[ArticleSage], chemin: Path) -> None:
    """Copie locale de la liste des articles Sage (pour choisir un article quand Sage est fermé)."""
    import csv

    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["numero", "description", "type", "compte_revenus"])
        w.writerows((a.numero, a.description, a.type, a.compte_revenus) for a in articles)


def lire_copie(chemin: Path) -> list[ArticleSage]:
    import csv

    if not chemin.exists():
        return []
    with chemin.open(encoding="utf-8", newline="") as f:
        lignes = list(csv.reader(f, delimiter=";"))
    return [ArticleSage(*r[:4]) for r in lignes[1:] if len(r) >= 4]


def lire_articles_sage(chemin: Path) -> list[ArticleSage]:
    texte = chemin.read_text(encoding="cp1252")
    articles = []
    for enregistrement in _enregistrements(texte):
        m = ARTICLE.match(enregistrement)
        if not m:
            continue
        numero, _, description = m["numero_description"].partition('","')
        numero = " ".join(numero.split())
        nombres = m["nombres"].split(",")
        if not numero or numero == ".":
            continue
        articles.append(ArticleSage(
            numero=numero,
            description=reparer_texte(" ".join(description.split())),
            type=m["type"],
            compte_revenus=nombres[3] if len(nombres) > 3 else "",
        ))
    return articles
