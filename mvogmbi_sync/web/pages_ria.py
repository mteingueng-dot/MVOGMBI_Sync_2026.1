"""4e vague de l'application web (fin) : RIA (comme fenetre_ria) : opérations RIA (ajout, suppression, saisie dans
Sage par le journal général), états de compte RIA (PDF envoyé par le navigateur ou lu dans la boîte de courriel,
traités en opérations), comptes RIA (vérifiés dans le plan comptable).
"""

from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .consultations import Section, sections_html
from .pages import Contexte, Fonction, argent, csrf, page
from .pages_compta import _message
from .serveur import Reponse, echapper as e


def operations(ctx: Contexte) -> Reponse:
    from .. import ria
    from . import taches

    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            with ctx.app.ecriture:
                registre = ria.Registre(ctx.racine)
                if action == "Ajouter":
                    montant = Decimal(ctx.req.champ("montant").replace(",", ".").replace("$", "").replace(" ", ""))
                    o = registre.ajouter(ctx.req.champ("jour"), ctx.req.champ("genre"), montant,
                                         ctx.req.champ("description").strip(), auteur=ctx.u.nom)
                    registre.enregistrer()
                    message = _message(f"Opération {o.numero} ajoutée.")
                elif action == "Supprimer":
                    registre.supprimer(ctx.req.champ("numero"))
                    registre.enregistrer()
                    message = _message("Opération supprimée.")
            if action == "Saisir dans Sage":
                registre = ria.Registre(ctx.racine)
                if registre.comptes_manquants():
                    raise ValueError("Comptes à renseigner d'abord (Comptabilité > Comptes RIA) : "
                                     + ", ".join(registre.comptes_manquants()))
                if not registre.a_saisir():
                    raise ValueError("Aucune opération à saisir dans Sage.")

                def travail(journal):
                    b = taches.executer_sage(ctx.racine, ["journal-bureau"], journal)
                    return [f"{len(b.get('saisis', []))} écriture(s) enregistrée(s)."] + b.get("a_verifier", []) + \
                        ([b["erreur"]] if b.get("erreur") else [])

                return taches.lancer(ctx, f"Saisie de {registre.a_saisir()} opération(s) RIA", travail, "/ria",
                                     sage=True)
        except (ValueError, InvalidOperation, StopIteration) as erreur:
            message = _message(erreur=str(erreur) or "Montant invalide.")
    registre = ria.Registre(ctx.racine)
    lignes, bilan = [], ria.Bilan()
    for o in sorted(registre.operations, key=lambda o: o.jour, reverse=True):
        signe = -1 if o.genre == ria.ESPECES else 1
        lignes.append([o.numero, o.jour, o.genre, signe * Decimal(o.montant), o.description, o.etat, o.ecriture or "",
                       o.auteur])
        if o.genre == ria.ESPECES:
            bilan.paiements += Decimal(o.montant)
        elif o.genre == ria.ENVOI:
            bilan.depots += Decimal(o.montant)
        elif o.genre == ria.SURPLUS:
            bilan.surplus += Decimal(o.montant)
    manquants = registre.comptes_manquants()
    genres = "".join(f"<option>{e(g)}</option>" for g in (ria.ENVOI, ria.ESPECES, ria.SURPLUS))
    supprimables = [o for o in registre.operations if o.etat != ria.SAISIE]
    choix = "".join(f"<option>{e(o.numero)}</option>" for o in supprimables)
    corps = (message
             + (f"<p class='erreur'>Comptes à renseigner avant toute saisie : {e(', '.join(manquants))} "
                "(<a href='/comptes-ria'>Comptes RIA</a>).</p>" if manquants else "")
             + f"<div class='cartes'><div class='carte'><div class='t'>Envois reçus en espèces</div><div class='v'>"
               f"{argent(bilan.depots)}</div></div><div class='carte'><div class='t'>Surplus de dépôts</div>"
               f"<div class='v'>{argent(bilan.surplus)}</div></div><div class='carte'><div class='t'>Versements payés en "
               f"espèces</div><div class='v'>{argent(bilan.paiements)}</div></div><div class='carte'><div class='t'>"
               f"À saisir dans Sage</div><div class='v'>{registre.a_saisir()}</div></div></div>"
             + f"<form method='post' class='carte'>{csrf(ctx)}<h2>Nouvelle opération</h2><div class='ligne'>"
               f"<div><label>Date</label><input type='date' name='jour' value='{date.today()}' required></div>"
               f"<div><label>Opération</label><select name='genre'>{genres}</select></div><div><label>Montant</label>"
               "<input name='montant' size='9' required></div><div><label>Description</label><input name='description' "
               "size='30'></div></div><div class='boutons'><button name='action' value='Ajouter'>Ajouter</button></div>"
               "</form>"
             + sections_html([Section("Opérations RIA", ["N°", "Date", "Opération", "Montant", "Description", "État",
                                                         "Écriture", "Par"], lignes,
                                      "Mouvements RIA des relevés et surplus des dépôts d'espèces : voir aussi "
                                      "Rapprochement et Encaissements.")])
             + (f"<form method='post' class='ligne'>{csrf(ctx)}<div><label>Supprimer l'opération</label><select "
                f"name='numero'>{choix}</select></div><button class='second' name='action' value='Supprimer'>Supprimer"
                "</button></form>" if supprimables else "")
             + (f"<form method='post' class='boutons'>{csrf(ctx)}<button name='action' value='Saisir dans Sage'>Saisir "
                f"{registre.a_saisir()} opération(s) dans Sage</button></form>" if registre.a_saisir() else ""))
    return Reponse(corps=page(ctx, "Opérations RIA", corps))


def etats(ctx: Contexte) -> Reponse:
    from .. import ria_etats as re_
    from . import taches

    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if action == "Importer" and "etat" in ctx.req.fichiers:
            nom, contenu = ctx.req.fichiers["etat"]
            if not contenu.startswith(b"%PDF"):
                message = _message(erreur="Choisissez l'état de compte RIA en PDF (AgentBalanceReport).")
            else:
                try:
                    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
                        chemin = Path(dossier) / Path(nom).name
                        chemin.write_bytes(contenu)
                        with ctx.app.ecriture:
                            registre = re_.Registre(ctx.racine)
                            etat, nouveau = registre.importer(chemin)
                            registre.enregistrer()
                    message = _message(f"État {etat.agence} du {etat.debut} au {etat.fin} "
                                       + ("importé." if nouveau else "déjà présent."))
                except Exception as erreur:  # noqa: BLE001 — PDF illisible
                    message = _message(erreur=f"État illisible : {erreur}")
        elif action == "Lire le courriel":
            def lire(journal):
                with ctx.app.ecriture:
                    lus = re_.recuperer(ctx.racine, ctx.config)
                return [f"{len(lus)} nouvel(s) état(s) lu(s)."] + [f"{x.agence} : {x.debut} → {x.fin}" for x in lus]

            return taches.lancer(ctx, "Lecture des états RIA reçus par courriel", lire, "/etats-ria")
        elif action == "Traiter dans Sage":
            from ..rapprochement import RegistreReleves

            with ctx.app.ecriture:
                banque = [m for r in RegistreReleves(ctx.racine).lire() for m in r.mouvements]
                crees = re_.operations_des_etats(ctx.racine, banque)
            message = _message(f"{crees} opération(s) créée(s) : saisie par « RIA > Opérations RIA » > « Saisir dans "
                               "Sage ».")
        elif action == "Supprimer":
            with ctx.app.ecriture:
                registre = re_.Registre(ctx.racine)
                registre.supprimer(ctx.req.champ("cle"))
                registre.enregistrer()
            message = _message("État retiré.")
    registre = re_.Registre(ctx.racine)
    lignes = [[x.agence, x.debut, x.fin, Decimal(x.solde_precedent), Decimal(x.total), Decimal(x.commission_payee),
               x.mois_commission_payee, Decimal(x.commission_courue), len(x.lignes), "; ".join(x.remarques) or "✔"]
              for x in registre.etats]
    choix = "".join(f"<option value='{e(x.cle)}'>{e(x.agence)} {e(x.debut)} → {e(x.fin)}</option>"
                    for x in registre.etats)
    corps = (message
             + f"<form method='post' enctype='multipart/form-data' class='ligne'>{csrf(ctx)}<div><label>État de "
               "compte RIA (PDF)</label><input type='file' name='etat' accept='.pdf' required></div><button "
               "class='second' name='action' value='Importer'>Importer</button></form>"
             + f"<form method='post' class='boutons'>{csrf(ctx)}<button class='second' name='action' value='Lire le "
               "courriel'>Lire le courriel</button><button name='action' value='Traiter dans Sage'>Traiter dans Sage"
               "</button></form>"
             + sections_html([Section("États de compte RIA", ["Agence", "Du", "Au", "Solde précédent", "Total",
                                                              "Commission payée", "Mois", "Commission courue",
                                                              "Lignes", "Contrôle"], lignes,
                                      "Traiter : chaque envoi (espèces reçues pour RIA) et chaque versement payé en "
                                      "espèces devient une opération RIA ; un versement par virement Interac est "
                                      "laissé à la banque.")])
             + (f"<form method='post' class='ligne'>{csrf(ctx)}<div><label>Retirer l'état</label><select name='cle'>"
                f"{choix}</select></div><button class='second' name='action' value='Supprimer'>Retirer</button></form>"
                if registre.etats else ""))
    return Reponse(corps=page(ctx, "États de compte RIA", corps))


def comptes(ctx: Contexte) -> Reponse:
    from .. import ria
    from ..plan_comptable import comptes_connus, problemes

    message = ""
    registre = ria.Registre(ctx.racine)
    if ctx.req.methode == "POST":
        for cle in ria.COMPTES:
            registre.comptes[cle] = ctx.req.champ(cle).strip()
        try:
            erreurs = problemes([registre.comptes[c] for c in ria.COMPTES], comptes_connus(ctx.racine, ctx.config))
        except (Exception, SystemExit):  # noqa: BLE001 — plan illisible : rien n'est bloqué (règle de l'application)
            erreurs = []
        if erreurs:
            message = _message(erreur=" ; ".join(erreurs) + ". Créez-le dans « Comptabilité > Plan comptable ».")
        else:
            with ctx.app.ecriture:
                frais = ria.Registre(ctx.racine)
                frais.comptes.update({c: registre.comptes[c] for c in ria.COMPTES})
                frais.enregistrer()
            message = _message("Comptes RIA enregistrés.")
    champs = "".join(f"<div><label>{e(libelle)}</label><input name='{cle}' value='{e(registre.comptes.get(cle, ''))}' "
                     "size='8'></div>" for cle, libelle in ria.COMPTES.items())
    corps = (message + f"<form method='post' class='carte'>{csrf(ctx)}<div class='ligne'>{champs}</div>"
             "<div class='boutons'><button name='action' value='Enregistrer'>Enregistrer</button></div></form>"
             "<p class='note'>Chaque compte doit exister dans le plan comptable de Sage.</p>")
    return Reponse(corps=page(ctx, "Comptes RIA", corps))


FONCTIONS = [
    Fonction("/ria", "Opérations RIA", "rapprochement", operations, "💱", "RIA", menu=False),
    Fonction("/etats-ria", "États de compte RIA", "rapprochement", etats, "📑", "Comptabilité", menu=False),
    Fonction("/comptes-ria", "Comptes RIA", "rapprochement", comptes, "🔢", "Comptabilité", menu=False),
]
WEB = {"Opérations RIA": "/ria", "États de compte RIA": "/etats-ria", "Comptes RIA": "/comptes-ria"}
