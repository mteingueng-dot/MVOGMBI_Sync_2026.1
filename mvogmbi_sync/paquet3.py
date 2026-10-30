"""Paquet 3 des fonctions ajoutées le 2026-10-29 : inventaire tournant, promotions datées dans Clover, relances des
clients professionnels, tableau du gérant pour le téléphone.

- Inventaire tournant : les catégories d'articles sont réparties sur [inventaire] semaines_cycle semaines (8 par
  défaut, ordre alphabétique) ; chaque semaine on compte ses catégories : feuille de comptage = export d'inventaire
  (inventaire.py) réduit à ces catégories, saisie ensuite comme tout inventaire (Articles > Inventaire > Saisir).
- Promotions : prix promotionnel d'un article Clover du … au … ; le traitement de nuit (ou « Appliquer maintenant »)
  met le prix promo le premier jour et remet le prix normal après le dernier (seulement si personne ne l'a changé
  entre-temps) ; effet = ventes (quantité, ventes nettes) pendant la promo contre la même durée juste avant.
- Clients professionnels : factures ouvertes des clients de Sage (hors clients des ventes Clover), limite de crédit
  (tcustomr.dCrLimit), dépassement, retards ; lettre de relance (PDF) envoyée au seul client (courriel.envoyer_a) ;
  journal donnees/relances.json.
- Tableau du gérant : page HTML légère (téléphone) du résumé du matin et des alertes, écrite chaque nuit dans
  [tableau] dossier (OneDrive par défaut : consultable par l'application OneDrive du téléphone).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ZERO = Decimal(0)
CENT = Decimal("0.01")


# --------------------------------------------------------------------------------------------- inventaire tournant
def plan_tournant(categories: list[str], semaines: int = 8) -> list[list[str]]:
    """Catégories réparties sur `semaines` semaines (tour à tour, ordre alphabétique)."""
    plan: list[list[str]] = [[] for _ in range(max(1, semaines))]
    for i, c in enumerate(sorted({c for c in categories if c}, key=str.casefold)):
        plan[i % len(plan)].append(c)
    return plan


def semaine_du_cycle(jour: date, semaines: int = 8) -> int:
    return jour.isocalendar()[1] % max(1, semaines)


def feuille_tournante(racine: Path, config_toml: dict, jour: date) -> tuple[Path, list[str], int]:
    """Exporte la feuille de comptage des catégories de la semaine ; (fichier, catégories, nombre de lignes)."""
    from .inventaire import ecrire, lire

    semaines = int(config_toml.get("inventaire", {}).get("semaines_cycle", 8))
    lignes = lire(racine, config_toml)
    plan = plan_tournant([l.categorie for l in lignes], semaines)
    choisies = plan[semaine_du_cycle(jour, semaines)]
    a_compter = [l for l in lignes if l.categorie in choisies]
    chemin = Path(racine) / "sortie" / "inventaire" / f"Inventaire_tournant_{jour.isoformat()}.xlsx"
    return ecrire(a_compter, chemin), choisies, len(a_compter)


# --------------------------------------------------------------------------------------------- promotions
PREVUE, EN_COURS, TERMINEE, ANNULEE = "Prévue", "En cours", "Terminée", "Annulée"


@dataclass
class Promotion:
    numero: str
    id_clover: str
    nom: str
    prix_promo: str
    du: str
    au: str
    prix_normal: str = ""      # lu dans Clover au début de la promotion
    etat: str = PREVUE
    messages: list[str] = field(default_factory=list)
    auteur: str = ""
    point_vente: str = ""      # code du point de vente (n° 1 si vide) : son Clover


class Promotions:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "promotions.json"
        donnees = json.loads(self.chemin.read_text(encoding="utf-8")) if self.chemin.exists() else []
        self.liste = [Promotion(**p) for p in donnees]

    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self.chemin.write_text(json.dumps([asdict(p) for p in self.liste], ensure_ascii=False, indent=1),
                               encoding="utf-8")

    def ajouter(self, id_clover: str, nom: str, prix_promo: Decimal, du: date, au: date, auteur: str = "",
                point_vente: str = "") -> Promotion:
        if au < du:
            raise ValueError("La fin précède le début.")
        if prix_promo <= 0:
            raise ValueError("Prix promotionnel invalide.")
        if any(p.id_clover == id_clover and (p.point_vente or "1") == (point_vente or "1")
               and p.etat in (PREVUE, EN_COURS) and not (au.isoformat() < p.du or
                                                                                du.isoformat() > p.au)
               for p in self.liste):
            raise ValueError("Une promotion de cet article couvre déjà ces dates.")
        n = len(self.liste) + 1
        p = Promotion(f"PR-{n:04d}", id_clover, nom, str(prix_promo), du.isoformat(), au.isoformat(), auteur=auteur,
                      point_vente=point_vente)
        self.liste.append(p)
        self.enregistrer()
        return p


def _prix_clover(client, id_clover: str) -> Decimal:
    r = client._get(f"items/{id_clover}")
    r.raise_for_status()
    return Decimal(int(r.json().get("price") or 0)) / 100


def appliquer_promotions(racine: Path, client, aujourdhui: date | None = None, code: str | None = None) -> list[str]:
    """Début et fin des promotions du jour dans le Clover `client` ; `code` : seulement celles de ce point de vente
    (toutes si None). Renvoie ce qui a été fait."""
    aujourdhui = aujourdhui or date.today()
    registre, faits = Promotions(racine), []
    for p in registre.liste:
        if code is not None and (p.point_vente or "1") != code:
            continue
        try:
            if p.etat == PREVUE and p.du <= aujourdhui.isoformat() <= p.au:
                p.prix_normal = str(_prix_clover(client, p.id_clover))
                client.regler_prix(p.id_clover, Decimal(p.prix_promo))
                p.etat = EN_COURS
                p.messages.append(f"{aujourdhui} : prix {p.prix_normal} -> {p.prix_promo}")
            elif p.etat in (PREVUE, EN_COURS) and aujourdhui.isoformat() > p.au:
                if p.etat == EN_COURS:
                    actuel = _prix_clover(client, p.id_clover)
                    if actuel == Decimal(p.prix_promo):
                        client.regler_prix(p.id_clover, Decimal(p.prix_normal))
                        p.messages.append(f"{aujourdhui} : prix normal remis ({p.prix_normal})")
                    else:
                        p.messages.append(f"{aujourdhui} : prix changé entre-temps ({actuel}) : laissé tel quel")
                p.etat = TERMINEE
            else:
                continue
            faits.append(f"{p.numero} {p.nom} : {p.etat}")
        except Exception as exc:
            p.messages.append(f"{aujourdhui} : erreur {exc}")
            faits.append(f"{p.numero} {p.nom} : erreur {exc}")
        registre.enregistrer()
    return faits


def effet(p: Promotion, ventes_pendant: dict, ventes_avant: dict) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """(quantité pendant, quantité avant, ventes nettes pendant, ventes nettes avant) de l'article."""
    a, b = ventes_pendant.get(p.id_clover), ventes_avant.get(p.id_clover)
    return (a.quantite if a else ZERO, b.quantite if b else ZERO, a.nettes if a else ZERO, b.nettes if b else ZERO)


# --------------------------------------------------------------------------------------------- clients professionnels
@dataclass
class ClientPro:
    nom: str
    courriel: str
    limite: Decimal
    solde: Decimal
    echu: Decimal
    plus_30: Decimal
    factures: list = field(default_factory=list)   # FactureOuverte

    @property
    def depasse(self) -> bool:
        return bool(self.limite) and self.solde > self.limite


def clients_pro(base, aujourdhui: date, exclus: set[str]) -> list[ClientPro]:
    from .comptabilite import factures_ouvertes

    fiches = {(r["n"] or "").strip(): r for r in base.requete(
        "SELECT TRIM(sName) n, sEmail e, dCrLimit l FROM tcustomr WHERE bInactive = 0")}
    par_client: dict[str, list] = {}
    for f in factures_ouvertes(base, "clients", aujourdhui):
        if f.tiers.casefold() not in {x.casefold() for x in exclus}:
            par_client.setdefault(f.tiers, []).append(f)
    resultat = []
    for nom, factures in par_client.items():
        fiche = fiches.get(nom, {})
        resultat.append(ClientPro(nom, (fiche.get("e") or "").strip(), Decimal(str(fiche.get("l") or 0)).quantize(CENT),
                                  sum((f.solde for f in factures), ZERO),
                                  sum((f.solde for f in factures if f.retard > 0), ZERO),
                                  sum((f.solde for f in factures if f.retard > 30), ZERO), factures))
    return sorted(resultat, key=lambda c: (-c.echu, c.nom.casefold()))


def lettre_relance(c: ClientPro, aujourdhui: date) -> tuple[list[str], list[list[str]], str]:
    """(en-têtes, lignes, sous-titre) de la lettre de relance (factures échues seulement)."""
    def argent(v):
        return f"{v:,.2f} $".replace(",", " ").replace(".", ",")

    lignes = [[f.numero, f.date.isoformat(), f.echeance.isoformat(), str(f.retard), argent(f.solde)]
              for f in c.factures if f.retard > 0]
    lignes.append(["Total échu", "", "", "", argent(c.echu)])
    sous = (f"{c.nom} — au {aujourdhui.isoformat()} : merci de régler les factures échues ci-dessous ou de nous "
            f"contacter.")
    return ["Facture", "Date", "Échéance", "Jours de retard", "Solde"], lignes, sous


def noter_relance(racine: Path, client: str, montant: Decimal, moyen: str) -> None:
    chemin = Path(racine) / "donnees" / "relances.json"
    liste = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else []
    liste.append({"client": client, "montant": str(montant), "moyen": moyen,
                  "le": datetime.now().isoformat(timespec="seconds")})
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(liste, ensure_ascii=False, indent=1), encoding="utf-8")


def derniere_relance(racine: Path) -> dict[str, str]:
    chemin = Path(racine) / "donnees" / "relances.json"
    liste = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else []
    return {r["client"]: r["le"][:10] for r in liste}


# --------------------------------------------------------------------------------------------- tableau téléphone
def dossier_tableau(racine: Path, config_toml: dict) -> Path:
    from .sauvegarde import dossier_par_defaut

    choisi = str(config_toml.get("tableau", {}).get("dossier", "")).strip()
    return Path(choisi) if choisi else dossier_par_defaut(racine).parent / "MVOGMBI_Sync_tableau"


def page_telephone(resume_html: str, alertes: list[str], quand: datetime) -> str:
    import html

    lignes = "".join(f"<li>{html.escape(a)}</li>" for a in alertes)
    return f"""<!doctype html><html lang='fr'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'><title>Tableau du gérant</title><style>
body {{ font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 14px; background: #f6faf7;
       color: #1f2d24; }}
h1 {{ font-size: 18px; margin: 0 0 4px; color: #13772d; }} .q {{ color: #6b7a70; font-size: 12px; margin-bottom: 12px; }}
table {{ width: 100% !important; }} td {{ display: block; margin: 0 0 8px !important; }}
ul {{ padding-left: 18px; }} li {{ margin: 4px 0; }}
</style></head><body><h1>Marché — tableau du gérant</h1><div class='q'>Mis à jour le {quand:%Y-%m-%d %H:%M}</div>
{resume_html}{f'<h3>Alertes</h3><ul>{lignes}</ul>' if lignes else ''}</body></html>"""


def ecrire_tableau(racine: Path, config_toml: dict, resume=None, alertes: list[str] | None = None) -> Path:
    from .resume_matin import calculer, html as html_resume

    resume = resume or calculer(racine, config_toml)
    cible = dossier_tableau(racine, config_toml)
    cible.mkdir(parents=True, exist_ok=True)
    chemin = cible / "tableau_du_gerant.html"
    chemin.write_text(page_telephone(html_resume(resume), alertes or [], datetime.now()), encoding="utf-8")
    return chemin
