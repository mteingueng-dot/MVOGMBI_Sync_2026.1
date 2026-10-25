"""Lecture directe des données de Sage 50 (Édition canadienne) par sa base MySQL locale.

Sage 50 expose ses données aux logiciels tiers par une base MySQL (« simply ») servie par le
« Gestionnaire de connexion de base de données » sur le port 13540, pendant que le fichier
d'entreprise est ouvert. L'accès exige un utilisateur Sage dont le droit « Accès par des tiers »
est en lecture seule ; ses identifiants sont dans config.toml (section [sage_base]).

Les noms de tables et de colonnes sont découverts à la connexion (ils varient selon les versions) :
la table des articles est celle qui contient le numéro d'article (« sPartCode ») et la description.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymysql

from .articles_sage import ArticleSage, reparer_texte


LONGUEUR_COMPTES = 4  # comptes affichés sur 4 chiffres dans Sage (4023), stockés sur 8 (40230000)


def numero_compte(valeur) -> str:
    """40230000 -> « 4023 » (numéro tel qu'affiché dans Sage)."""
    texte = str(valeur or "").strip()
    if not texte or texte == "0":
        return ""
    return texte[:LONGUEUR_COMPTES] if len(texte) == 8 else texte


@dataclass
class ConfigSageBase:
    utilisateur: str
    mot_de_passe: str
    hote: str = "127.0.0.1"
    port: int = 13540
    base: str = "simply"


PORTS_SAGE = range(13540, 13560)  # une base MySQL par fichier ouvert dans Sage, à partir de 13540


def port_du_fichier(fichier_sai: Path, config: "ConfigSageBase") -> int:
    """Port de la base servant ce fichier d'entreprise (son dossier .SAJ), parmi les bases Sage ouvertes.

    Les ports dépendent de l'ordre d'ouverture des fichiers : on les parcourt et on compare le dossier
    de données de chaque base avec celui du fichier visé.
    """
    cible = str(Path(fichier_sai).with_suffix(".SAJ")).rstrip("\\/").lower()
    for port in PORTS_SAGE:
        try:
            connexion = pymysql.connect(host=config.hote, port=port, user=config.utilisateur,
                                        password=config.mot_de_passe, database=config.base, connect_timeout=1)
        except pymysql.err.MySQLError:
            continue
        try:
            with connexion.cursor() as curseur:
                curseur.execute("SHOW VARIABLES LIKE 'datadir'")
                dossier = str(curseur.fetchone()[1]).rstrip("\\/").lower()
        finally:
            connexion.close()
        if dossier == cible:
            return port
    raise LookupError(f"Le fichier {Path(fichier_sai).name} n'est pas ouvert dans Sage "
                      "(aucune base Sage ne le sert) : ouvrez-le dans Sage 50.")


class BaseSage:
    def __init__(self, config: ConfigSageBase):
        if not config.utilisateur:
            raise ValueError("Utilisateur Sage absent de config.toml (section [sage_base]).")
        self.connexion = pymysql.connect(
            host=config.hote, port=config.port, user=config.utilisateur, password=config.mot_de_passe,
            database=config.base, charset="utf8mb4", connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor,
        )

    def __enter__(self) -> "BaseSage":
        return self

    def __exit__(self, *exc) -> None:
        self.connexion.close()

    def requete(self, sql: str, parametres: tuple = ()) -> list[dict]:
        with self.connexion.cursor() as curseur:
            curseur.execute(sql, parametres)
            return list(curseur.fetchall())

    def tables(self) -> list[str]:
        return [next(iter(r.values())) for r in self.requete("SHOW TABLES")]

    def colonnes(self, table: str) -> list[str]:
        return [r["Field"] for r in self.requete(f"SHOW COLUMNS FROM `{table}`")]

    def facture_existe(self, numero: str, client: str) -> bool:
        """Une facture de ce numéro existe-t-elle déjà pour ce client (table des transactions clients) ?"""
        lignes = self.requete(
            "SELECT 1 FROM tcustr t JOIN tcustomr c ON c.lId = t.lCusId "
            "WHERE TRIM(t.sSource) = %s AND c.sName = %s LIMIT 1", (numero.strip(), client))
        return bool(lignes)

    def table_articles(self) -> tuple[str, dict[str, str]]:
        """Table des articles d'inventaire et correspondance de ses colonnes utiles."""
        tables = self.tables()
        # Les tables d'inventaire d'abord ; certaines tables internes sont interdites aux tiers.
        for table in sorted(tables, key=lambda t: ("invent" not in t.lower(), t)):
            try:
                cols = {c.lower(): c for c in self.colonnes(table)}
            except pymysql.err.MySQLError:
                continue
            if "spartcode" in cols and "sname" in cols:
                return table, cols
        raise LookupError("Table des articles introuvable dans la base Sage (colonne sPartCode).")

    def articles(self) -> list[ArticleSage]:
        table, cols = self.table_articles()
        champs = [f"`{cols['spartcode']}` AS numero", f"`{cols['sname']}` AS description"]
        compte = next((cols[c] for c in cols if "rev" in c and c.startswith("l")), None)
        if compte:
            champs.append(f"`{compte}` AS compte")
        lignes = self.requete(f"SELECT {', '.join(champs)} FROM `{table}`")
        resultat = []
        for r in lignes:
            numero = " ".join(str(r["numero"] or "").split())
            if not numero or numero == ".":
                continue
            resultat.append(ArticleSage(
                numero=numero,
                description=reparer_texte(" ".join(str(r["description"] or "").split())),
                type="Inventory",
                compte_revenus=numero_compte(r.get("compte")),
            ))
        return resultat
