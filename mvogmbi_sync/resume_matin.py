"""Résumé du matin (demande du propriétaire du 2026-10-29) : ajouté en tête du courriel du traitement de nuit.

Indicateurs : ventes nettes Clover d'hier contre le même jour de la semaine passée, marge d'hier (articles reliés à
Sage, au CUMP), solde du compte de dépôt dans Sage, factures fournisseurs à payer dans les 7 jours (échéance =
date + jours nets de la facture, retards compris). Alertes : ruptures parmi les articles de classe A (80 % des
ventes des 90 derniers jours), articles à commander (règle des prévisions, 14 jours), produits qui périment dans le
mois avec du stock. Chaque partie est calculée à part : une erreur n'empêche ni les autres ni le courriel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

CENT = Decimal("0.01")
JOURS_A_PAYER = 7


@dataclass
class ResumeMatin:
    jour: date
    ventes: Decimal | None = None
    ventes_semaine_passee: Decimal | None = None
    marge: Decimal | None = None          # % des ventes nettes des articles dont le coût est connu
    solde_banque: Decimal | None = None
    a_payer: Decimal | None = None
    factures_a_payer: int = 0
    en_retard: int = 0
    ruptures_a: list[str] = field(default_factory=list)
    a_commander: int | None = None
    peremption: list[str] = field(default_factory=list)
    alertes: list[str] = field(default_factory=list)   # retenues à remettre, caisse non comptée ou en écart
    infos: list[str] = field(default_factory=list)     # jours fériés et congés des 7 prochains jours
    especes_hier: Decimal | None = None                 # espèces nettes attendues d'hier (caisse.py)
    erreurs: list[str] = field(default_factory=list)

    @property
    def variation(self) -> Decimal | None:
        if self.ventes is None or not self.ventes_semaine_passee:
            return None
        return ((self.ventes - self.ventes_semaine_passee) / self.ventes_semaine_passee * 100).quantize(Decimal("1"))


def argent(v: Decimal | None) -> str:
    return "—" if v is None else f"{v:,.2f} $".replace(",", " ").replace(".", ",")


def marge_du_jour(ventes: dict, liens: dict[str, str], couts: dict) -> Decimal | None:
    """Marge (%) des ventes nettes dont le coût Sage (CUMP) est connu ; `ventes` : ID Clover -> VenteArticle."""
    from .statistiques_clover import SEUIL_CUMP_DOUTEUX

    nettes, cout = Decimal(0), Decimal(0)
    for cle, v in ventes.items():
        c = couts.get(liens.get(cle, ""))
        if not c or not c.cump or v.quantite <= 0 or v.nettes <= 0:
            continue
        if c.cump > SEUIL_CUMP_DOUTEUX * (v.nettes / v.quantite):
            continue  # valeur de stock douteuse dans Sage
        nettes += v.nettes
        cout += c.cump * v.quantite
    return ((nettes - cout) / nettes * 100).quantize(Decimal("0.1")) if nettes else None


def factures_a_payer(base, aujourdhui: date, jours: int = JOURS_A_PAYER) -> tuple[Decimal, int, int]:
    """(montant, nombre, nombre en retard) des factures fournisseurs ouvertes échues d'ici `jours` jours."""
    lignes = base.requete(
        "SELECT t.lId, t.dtDate, t.nNetDay, SUM(d.dAmount) s FROM tventr t JOIN tventrdt d ON d.lVenTrId = t.lId "
        "WHERE t.nTranType = 0 AND d.bReversed = 0 GROUP BY t.lId, t.dtDate, t.nNetDay")
    montant, nombre, retard = Decimal(0), 0, 0
    for l in lignes:
        solde = Decimal(str(l["s"] or 0)).quantize(CENT)
        if solde <= 0:
            continue
        jour = l["dtDate"].date() if hasattr(l["dtDate"], "date") else l["dtDate"]
        echeance = jour + timedelta(days=int(l["nNetDay"] or 0))
        if echeance <= aujourdhui + timedelta(days=jours):
            montant += solde
            nombre += 1
            retard += echeance < aujourdhui
    return montant, nombre, retard


def calculer(racine: Path, config_toml: dict, aujourdhui: date | None = None) -> ResumeMatin:
    from . import analyse_articles as aa
    from .__main__ import charger_config, lire_sage
    from .api_clover import ClientClover
    from .couts_sage import charger, correspondance
    from .peremption import articles_peremption
    from .previsions import articles_a_commander, ventes_par_article, ventes_par_jour
    from .statistiques_clover import lire

    racine = Path(racine)
    aujourdhui = aujourdhui or date.today()
    hier = aujourdhui - timedelta(days=1)
    r = ResumeMatin(hier)
    try:
        client = ClientClover(charger_config(racine / "config.toml"))
        debut = hier - timedelta(days=89)
        donnees = lire(client, debut, hier, racine / "donnees" / "cache_clover")
        articles = client.inventaire()
    except BaseException as exc:  # SystemExit compris (jeton absent)
        r.erreurs.append(f"Clover : {exc}")
        return r
    par_jour = ventes_par_jour(donnees)
    r.ventes = par_jour.get(hier, Decimal(0)).quantize(CENT)
    try:
        from .caisse import attendus

        attendu = attendus(donnees).get(hier)
        r.especes_hier = attendu.net if attendu else Decimal(0)
    except Exception:
        r.especes_hier = None
    r.ventes_semaine_passee = par_jour.get(hier - timedelta(days=7), Decimal(0)).quantize(CENT)
    ventes_90 = ventes_par_article(donnees, debut, hier)
    try:
        r.marge = marge_du_jour(ventes_par_article(donnees, hier, hier), correspondance(racine),
                                charger(racine, config_toml))
    except Exception as exc:
        r.erreurs.append(f"Marge : {exc}")
    try:
        lignes, _ = aa.pareto(aa.articles_clover(articles, ventes_90), aa.ventes_clover(ventes_90), 90)
        r.ruptures_a = [l[3] for l in lignes if l[1] == "A" and l[10] <= 0 and l[14] != "Supprimé ou renommé dans Clover"]
        r.a_commander = sum(1 for l in articles_a_commander(ventes_par_article(donnees, hier - timedelta(days=13),
                                                                               hier), articles)
                            if l[5] == "À commander")
        r.peremption = [f"{p.nom} ({p.peremption:%d/%m})" for p in articles_peremption(articles, aujourdhui)
                        if p.couleur == "rouge" and p.stock and p.stock > 0]
    except Exception as exc:
        r.erreurs.append(f"Articles : {exc}")
    try:
        from .encaissements import numero_compte_sage
        from .rapprochement import solde_sage

        compte = numero_compte_sage(str(config_toml.get("encaissements", {}).get("compte_depot", "1055")))
        r.solde_banque, (r.a_payer, r.factures_a_payer, r.en_retard) = lire_sage(
            config_toml, lambda b: (solde_sage(b, hier, compte), factures_a_payer(b, aujourdhui)),
            config_toml.get("sage_import", {}).get("fichier_entreprise"))
    except Exception as exc:
        r.erreurs.append(f"Sage : {exc}")
    try:  # remises des retenues à la source (retenues.suivi)
        from .retenues import alertes, suivi

        r.alertes += alertes(lire_sage(config_toml, lambda b: suivi(b, aujourdhui, 2),
                                       config_toml.get("sage_import", {}).get("fichier_entreprise")), aujourdhui)
    except Exception as exc:
        r.erreurs.append(f"Retenues : {exc}")
    try:  # jours fériés et congés des 7 prochains jours (conges.py)
        from . import conges as co
        from . import paie_temps as pt

        fin = aujourdhui + timedelta(days=7)
        registre_conges = co.Registre(racine)
        r.infos += [f"Jour férié le {j:%Y-%m-%d} : {n}" for j, n in co.feries_entre(aujourdhui, fin,
                                                                                     registre_conges.paques)]
        noms = {e.id: e.nom for e in pt.Registre(racine).employes}
        absents: dict[str, list[str]] = {}
        for c in registre_conges.conges:
            if aujourdhui.isoformat() <= c.jour <= fin.isoformat():
                absents.setdefault(noms.get(c.employe, c.employe), []).append(c.jour[5:])
        r.infos += [f"Congé : {nom} ({', '.join(sorted(jours))})" for nom, jours in sorted(absents.items())]
    except Exception as exc:
        r.erreurs.append(f"Congés : {exc}")
    try:  # caisse d'hier : comptée ? écart ? (caisse.py)
        from . import caisse as ca

        comptage = ca.Registre(racine).comptage(hier)
        if comptage is None:
            r.alertes.append(f"Caisse du {hier:%Y-%m-%d} non comptée (Comptabilité > Contrôle de la caisse)")
        elif r.especes_hier is not None:
            ecart = Decimal(comptage.compte) - (ca.fond_du_matin(ca.Registre(racine), hier, config_toml)
                                                + r.especes_hier)
            if abs(ecart) > ca.SEUIL_ECART:
                r.alertes.append(f"Écart de caisse du {hier:%Y-%m-%d} : {argent(ecart)}")
    except Exception as exc:
        r.erreurs.append(f"Caisse : {exc}")
    return r


def _liste(noms: list[str], maximum: int = 8) -> str:
    return ", ".join(noms[:maximum]) + (f" et {len(noms) - maximum} autre(s)" if len(noms) > maximum else "")


def texte(r: ResumeMatin) -> list[str]:
    from .langues import t

    variation = "" if r.variation is None else f" ({r.variation:+} % " + t("contre le même jour la semaine passée") + ")"
    lignes = [t("Résumé du {d}", d=f"{r.jour:%Y-%m-%d}"),
              "  " + t("Ventes d'hier : {v}", v=argent(r.ventes)) + variation,
              "  " + t("Marge : {m}", m="—" if r.marge is None else f"{r.marge} %".replace(".", ",")),
              "  " + t("Solde du compte de dépôt (Sage) : {s}", s=argent(r.solde_banque)),
              "  " + t("Factures fournisseurs à payer d'ici 7 jours : {m} ({n} facture(s), dont {e} en retard)",
                       m=argent(r.a_payer), n=r.factures_a_payer, e=r.en_retard)]
    if r.ruptures_a:
        lignes.append("  ● " + t("{n} rupture(s) parmi les articles A : {l}", n=len(r.ruptures_a), l=_liste(r.ruptures_a)))
    if r.a_commander:
        lignes.append("  ● " + t("{n} article(s) à commander (Fournisseur > Bons de commande)", n=r.a_commander))
    if r.peremption:
        lignes.append("  ● " + t("{n} produit(s) en stock périmé(s) ou qui périment dans le mois : {l}", n=len(r.peremption),
                                 l=_liste(r.peremption)))
    lignes += ["  ● " + a for a in r.alertes]
    lignes += ["  ○ " + x for x in r.infos]
    lignes += ["  " + t("Non calculé : {e}", e=e) for e in r.erreurs]
    return lignes


def html(r: ResumeMatin) -> str:
    import html as h

    from .langues import t

    e = h.escape
    variation = ""
    if r.variation is not None:
        couleur = "#1b7f3b" if r.variation >= 0 else "#b3261e"
        variation = f"<div style='color:{couleur};font-size:12px'>{r.variation:+} % {e(t('vs semaine passée'))}</div>"

    def carte(titre, valeur, dessous=""):
        return (f"<td style='background:#f1f5f2;border-radius:8px;padding:10px 14px;vertical-align:top'>"
                f"<div style='color:#5a6b60;font-size:12px'>{e(titre)}</div>"
                f"<div style='font-size:20px;font-weight:600'>{e(valeur)}</div>{dessous}</td>")

    cartes = ("<table cellspacing='8' style='margin-left:-8px'><tr>"
              + carte(t("Ventes d'hier"), argent(r.ventes), variation)
              + carte(t("Marge"), "—" if r.marge is None else f"{r.marge} %".replace(".", ","))
              + carte(t("Compte de dépôt"), argent(r.solde_banque))
              + carte(t("À payer (7 jours)"), argent(r.a_payer),
                      f"<div style='font-size:12px;color:#5a6b60'>{e(t('{n} facture(s), {e} en retard', n=r.factures_a_payer, e=r.en_retard))}</div>")
              + "</tr></table>")
    alertes = []
    if r.ruptures_a:
        alertes.append(("#b3261e", t("{n} rupture(s) parmi les articles A : {l}", n=len(r.ruptures_a),
                                     l=_liste(r.ruptures_a))))
    if r.a_commander:
        alertes.append(("#9a6700", t("{n} article(s) à commander (Fournisseur > Bons de commande)", n=r.a_commander)))
    if r.peremption:
        alertes.append(("#9a6700", t("{n} produit(s) en stock périmé(s) ou qui périment dans le mois : {l}", n=len(r.peremption),
                                     l=_liste(r.peremption))))
    alertes += [("#b3261e", a) for a in r.alertes]
    alertes += [("#1f5f99", x) for x in r.infos]
    alertes += [("#5a6b60", t("Non calculé : {e}", e=x)) for x in r.erreurs]
    return (f"<h3 style='margin:4px 0'>{e(t('Résumé du {d}', d=f'{r.jour:%Y-%m-%d}'))}</h3>{cartes}"
            + "".join(f"<div style='color:{c};margin:2px 0'>● {e(x)}</div>" for c, x in alertes)
            + "<hr style='border:none;border-top:1px solid #e2e8e4;margin:14px 0'>")
