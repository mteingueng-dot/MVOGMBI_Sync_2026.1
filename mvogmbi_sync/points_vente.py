"""Points de vente Clover et dépôts Sage (demande du propriétaire du 2026-10-28, en prévision d'autres magasins).

Règles du propriétaire :
- chaque point de vente Clover (un identifiant marchand et son jeton) est un dépôt (emplacement d'inventaire) dans
  Sage ;
- une facture par point de vente, avec son propre client Sage et son préfixe de numéro (« Vente 2026-10-23/25 »,
  « V2 2026-10-23/25 ») ; mêmes comptes de produits (ceux des articles) ; dépôts bancaires dans le même compte ;
- on traite un point de vente choisi, ou tous à la suite.

Le point de vente n° 1 est celui de la section [clover] (réglages d'avant : client « Vente Hebdomadaire », préfixe
« Vente », « Emplacement par défaut », fichiers de donnees/ inchangés). Les suivants sont décrits dans config.toml :

    [[points_vente]]
    code = "2"                        # court, unique
    nom = "Magasin 2"
    merchant_id = "XXXXXXXXXXXXX"     # jeton dans le coffre-fort Windows (« clover_jeton_2 »)
    client_sage = "Vente Magasin 2"
    depot_sage = "Magasin 2"          # emplacement d'inventaire Sage
    prefixe = "V2"                    # 5 caractères au plus (n° de facture Sage limité à 20)
    actif = true

Leurs fichiers (correspondance des articles, articles à relier) sont dans donnees/points_vente/<code>/ : les articles
Clover d'un autre marchand ont d'autres identifiants.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import coffre

PRINCIPAL = "1"
TOUS = "tous"
CLIENT_PRINCIPAL = "Vente Hebdomadaire"
PREFIXE_PRINCIPAL = "Vente"
DEPOT_DEFAUT = "Emplacement par défaut"
LONGUEUR_PREFIXE = 5  # « Vente Septembre 2026 » = 20 caractères, le maximum de Sage


@dataclass
class PointDeVente:
    code: str
    nom: str
    merchant_id: str
    client_sage: str = CLIENT_PRINCIPAL
    depot_sage: str = DEPOT_DEFAUT
    prefixe: str = PREFIXE_PRINCIPAL
    actif: bool = True

    @property
    def principal(self) -> bool:
        return self.code == PRINCIPAL

    @property
    def cle_jeton(self) -> str:
        """Clé du jeton Clover dans le coffre-fort Windows."""
        return coffre.CLOVER_JETON if self.principal else f"{coffre.CLOVER_JETON}_{self.code}"

    @property
    def libelle(self) -> str:
        return f"{self.code} — {self.nom}"

    @property
    def depot_par_defaut(self) -> bool:
        return self.depot_sage.strip().lower() in ("", DEPOT_DEFAUT.lower())

    def dossier(self, donnees: Path) -> Path:
        """Dossier des fichiers propres au point de vente (donnees/ pour le n° 1)."""
        return donnees if self.principal else donnees / "points_vente" / self.code

    def fichier(self, donnees: Path, nom: str) -> Path:
        return self.dossier(donnees) / nom


def points_de_vente(config_toml: dict, actifs: bool = False) -> list[PointDeVente]:
    """N° 1 (section [clover]) puis ceux de [[points_vente]], dans l'ordre de config.toml."""
    c = config_toml.get("clover", {})
    liste = [PointDeVente(PRINCIPAL, str(c.get("nom") or "Point de vente principal"), str(c.get("merchant_id", "")),
                          str(c.get("client_sage") or CLIENT_PRINCIPAL), str(c.get("depot_sage") or DEPOT_DEFAUT),
                          PREFIXE_PRINCIPAL, True)]
    for p in config_toml.get("points_vente", []) or []:
        code = str(p.get("code", "")).strip()
        if not code or code == PRINCIPAL:
            continue
        liste.append(PointDeVente(code, str(p.get("nom") or f"Point de vente {code}"), str(p.get("merchant_id", "")),
                                  str(p.get("client_sage") or ""), str(p.get("depot_sage") or DEPOT_DEFAUT),
                                  str(p.get("prefixe") or f"V{code}"), bool(p.get("actif", True))))
    return [p for p in liste if p.actif] if actifs else liste


def choisir(config_toml: dict, code: str | None) -> list[PointDeVente]:
    """Points de vente à traiter : « tous » (ou rien) = tous les actifs ; sinon le code, ou plusieurs codes
    séparés par des virgules (« 1,3 » : les points de vente permis à un profil)."""
    if not code or code == TOUS:
        return points_de_vente(config_toml, actifs=True)
    codes = [c.strip() for c in str(code).split(",") if c.strip()]
    tous = {p.code: p for p in points_de_vente(config_toml)}
    if inconnus := [c for c in codes if c not in tous]:
        raise ValueError(f"Point de vente inconnu : {', '.join(inconnus)}")
    return [tous[c] for c in codes]


def permis(config_toml: dict, codes: set[str] | None, actifs: bool = True) -> list[PointDeVente]:
    """Points de vente qu'un utilisateur peut voir (`codes` du profil ; None = tous)."""
    return [p for p in points_de_vente(config_toml, actifs) if codes is None or p.code in codes]


def point_de_vente(config_toml: dict, code: str | None = None) -> PointDeVente:
    return choisir(config_toml, code or PRINCIPAL)[0]


def problemes_configuration(points: list[PointDeVente]) -> list[str]:
    """Réglages incohérents : codes, préfixes ou clients en double, préfixe trop long, champ manquant."""
    problemes = []
    for attribut, libelle in (("code", "code"), ("prefixe", "préfixe"), ("client_sage", "client Sage"),
                              ("merchant_id", "identifiant marchand")):
        vus: dict[str, str] = {}
        for p in points:
            valeur = getattr(p, attribut).strip().lower()
            if not valeur:
                if attribut != "merchant_id" or p.actif:
                    problemes.append(f"Point de vente {p.libelle} : {libelle} manquant.")
            elif valeur in vus:
                problemes.append(f"Points de vente {vus[valeur]} et {p.libelle} : même {libelle}.")
            else:
                vus[valeur] = p.libelle
    for p in points:
        if len(p.prefixe) > LONGUEUR_PREFIXE or " " in p.prefixe:
            problemes.append(f"Point de vente {p.libelle} : préfixe « {p.prefixe} » de {LONGUEUR_PREFIXE} caractères "
                             "au plus, sans espace (le n° de facture Sage est limité à 20 caractères).")
    return problemes


# --------------------------------------------------------------------------------------------- aides (2026-10-29)
def client(racine: Path, pv: "PointDeVente | None" = None):
    """Connexion Clover du point de vente (n° 1 par défaut)."""
    from .__main__ import charger_config
    from .api_clover import ClientClover

    return ClientClover(charger_config(Path(racine) / "config.toml", pv))


def cache_clover(racine: Path, pv: "PointDeVente | None" = None) -> Path:
    """Cache des jours Clover du point de vente (donnees/cache_clover pour le n° 1)."""
    donnees = Path(racine) / "donnees"
    return (pv.dossier(donnees) if pv else donnees) / "cache_clover"


def fichier_correspondance(racine: Path, pv: "PointDeVente | None" = None) -> Path:
    donnees = Path(racine) / "donnees"
    return (pv.dossier(donnees) if pv else donnees) / "correspondance_articles.xlsx"


def visibles(widget, config_toml: dict) -> list["PointDeVente"]:
    """Points de vente que la personne connectée peut traiter (Application.points_visibles), sinon tous les actifs."""
    app = widget.nametowidget(".")
    return app.points_visibles() if hasattr(app, "points_visibles") else points_de_vente(config_toml, actifs=True)
