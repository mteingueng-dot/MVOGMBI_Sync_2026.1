"""Fin d'emploi et préparation du relevé d'emploi (RE) — demande du propriétaire du 2026-10-29.

Le RE se produit dans RE Web de Service Canada (ou par Sage) dans les 5 jours suivant l'arrêt de la rémunération ;
l'application prépare ses données (repères généraux, Service Canada fait foi) :
- heures assurables des 53 dernières semaines : heures pointées dans l'application (présences) ;
- rémunération assurable par période de paie : brut des paies de Sage de l'employé (écritures du module Paie), les 27
  dernières paies au plus (paie aux 2 semaines) ;
- premier et dernier jour travaillés, dernier jour payé, code de motif ; liste des choses à faire.
Concordance de fin d'année (T4 / Relevé 1) : brut, retenues par sorte et net des paies de Sage de l'année, à côté des
heures de l'application, par employé.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from . import paie as pa
from . import paie_temps as pt

ZERO = Decimal(0)
MOTIFS_RE = {"A": "Manque de travail / fin de contrat ou de saison", "D": "Maladie ou blessure",
             "E": "Départ volontaire", "F": "Congé de maternité", "G": "Retraite", "K": "Autre",
             "M": "Congédiement", "N": "Congé (absence autorisée)", "P": "Congé parental"}
A_FAIRE = ["Paie finale : heures dues, jours fériés, vacances accumulées (4 % ou 6 %) — Paie > Traitement de la paie",
           "Relevé d'emploi dans RE Web de Service Canada (ou par Sage) dans les 5 jours",
           "Désactiver l'employé dans l'application (poste de pointage) et dans Clover",
           "Retirer ses accès (comptes, clés, codes)"]


def heures_assurables(registre: pt.Registre, employe: pt.Employe, dernier_jour: date) -> tuple[Decimal, date | None]:
    """(heures des 53 semaines terminées au dernier jour, premier jour travaillé connu)."""
    liste, _ = pt.presences(registre.valides(employe.id))
    debut = dernier_jour - timedelta(weeks=53) + timedelta(days=1)
    total = sum((p.heures for p in liste if debut <= p.jour <= dernier_jour), ZERO)
    premier = min((p.jour for p in liste), default=None)
    return total.quantize(Decimal("0.01")), premier


def remunerations(paies: list[pa.PaieSage], nom_sage: str, dernier_jour: date, n: int = 27) -> list[tuple[date, Decimal]]:
    """Brut des paies de l'employé, de la plus récente à la plus ancienne, jusqu'au dernier jour (n au plus)."""
    siennes = sorted((p for p in paies if pa._simple(p.employe) == pa._simple(nom_sage) and p.jour <= dernier_jour
                      + timedelta(days=14)), key=lambda p: p.jour, reverse=True)
    return [(p.jour, p.brut) for p in siennes[:n]]


def preparation_re(registre: pt.Registre, employe: pt.Employe, paies: list[pa.PaieSage], dernier_jour: date,
                   code: str) -> tuple[list[list[str]], str]:
    """(lignes du document, sous-titre) de la préparation du RE."""
    heures, premier = heures_assurables(registre, employe, dernier_jour)
    remus = remunerations(paies, employe.numero_sage or employe.nom, dernier_jour)
    lignes = [["Employé", employe.nom], ["Employé Sage", employe.numero_sage or "(non relié)"],
              ["Premier jour travaillé (pointages)", premier.isoformat() if premier else "inconnu"],
              ["Dernier jour travaillé", dernier_jour.isoformat()],
              ["Code de motif", f"{code} — {MOTIFS_RE.get(code, '')}"],
              ["Heures assurables (53 dernières semaines)", pa.heures(heures)],
              ["Paies trouvées dans Sage", str(len(remus))],
              ["Rémunération assurable totale", pa.argent(sum((b for _j, b in remus), ZERO))]]
    lignes += [[f"   Paie du {j.isoformat()}", pa.argent(b)] for j, b in remus]
    lignes += [["À FAIRE", ""]] + [["   ☐ " + x, ""] for x in A_FAIRE]
    return lignes, f"{employe.nom} — dernier jour {dernier_jour.isoformat()} — motif {code}"


def concordance(paies: list[pa.PaieSage], registre: pt.Registre, annee: int) -> list[list]:
    """Par employé Sage : paies, heures de l'application, brut, retenues par sorte, net, contrôle."""
    employes = registre.employes
    par_nom: dict[str, list[pa.PaieSage]] = {}
    for p in paies:
        if p.jour.year == annee:
            par_nom.setdefault(p.employe, []).append(p)
    sortes = ["RRQ", "Assurance-emploi", "RQAP", "Impôt du Québec", "Impôt fédéral"]
    lignes = []
    for nom, liste in sorted(par_nom.items(), key=lambda x: x[0].casefold()):
        brut = sum((p.brut for p in liste), ZERO)
        net = sum((p.net for p in liste), ZERO)
        retenues = {s: sum((p.retenues.get(s, ZERO) for p in liste), ZERO) for s in sortes}
        autres = sum((p.total_retenues for p in liste), ZERO) - sum(retenues.values(), ZERO)
        e = pa.employe_de(liste[0], employes)
        heures = ZERO
        if e:
            liste_p, _ = pt.presences(registre.valides(e.id))
            heures = sum((x.heures for x in liste_p if x.jour.year == annee), ZERO)
        controle = []
        if abs(brut - sum(retenues.values(), ZERO) - autres - net) > Decimal("0.05"):
            controle.append("brut ≠ retenues + net")
        if not e:
            controle.append("employé non relié")
        elif not heures:
            controle.append("aucune heure pointée")
        lignes.append([nom, len(liste), pa.heures(heures), brut, *[retenues[s] for s in sortes], autres, net,
                       " ; ".join(controle) or "✔"])
    return lignes


ENTETES_CONCORDANCE = ["Employé", "Paies", "Heures (application)", "Brut", "RRQ", "Assurance-emploi", "RQAP",
                       "Impôt du Québec", "Impôt fédéral", "Autres retenues", "Net", "Contrôle"]
