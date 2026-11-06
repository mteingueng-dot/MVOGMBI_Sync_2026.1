"""4e vague de l'application web (fin) : RIA (comme fenetre_ria) : opérations RIA (ajout, suppression, saisie dans
Sage par le journal général), états de compte RIA (PDF envoyé par le navigateur ou lu dans la boîte de courriel,
traités en opérations), comptes RIA (vérifiés dans le plan comptable).
"""

from __future__ import annotations

import tempfile
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .consultations import Section, sections_html, tableau_section
from .pages import Contexte, Fonction, argent, csrf, page
from .pages_compta import _message, action_permise
from .serveur import Reponse, echapper as e


def _lignes_ria(ctx: Contexte, du: date, au: date, forcer: bool = False):
    """Comme FenetreRia.actualiser + _afficher : mouvements RIA des relevés (rapprochés de Sage), dépôts d'espèces
    (surplus), opérations ; gardé 5 min."""
    import time

    from .. import ria
    from ..ria_etats import Registre as RegistreEtats, commissions_reconnues
    from .consultations import lire_ou_vide

    cle = ("ria", du, au)
    gardee = ctx.app.memoire.get(cle)
    if gardee and not forcer and time.time() - gardee[0] < 300:
        mouvements, depots, absents = gardee[1]
        ctx.absents.update(absents)
    else:
        from ..__main__ import charger_config
        from ..api_clover import ClientClover
        from ..encaissements import calculer, numero_compte_sage
        from ..points_vente import points_de_vente
        from ..rapprochement import RegistreReleves, mouvements_sage, periode_des, rapprocher

        def lire(base):
            releves = RegistreReleves(ctx.racine).lire()
            bornes = periode_des(releves)
            if not bornes:
                return [], []
            banque = [m for r in releves for m in r.mouvements]
            rapprocher(banque, mouvements_sage(base, bornes[0] - timedelta(days=7), bornes[1] + timedelta(days=7)))
            mouvements = [m for m in banque if ria.est_ria(m) and du <= date.fromisoformat(m.date) <= au]
            depots = []
            try:
                pdv = next(p for p in points_de_vente(ctx.config, actifs=True) if p.principal)
                client = ClientClover(charger_config(ctx.racine / "config.toml", pdv))
                compte = numero_compte_sage(ctx.config.get("encaissements", {}).get("compte_depot", "1055"))
                depots = calculer(client, base, pdv.client_sage, compte, du, au, racine=ctx.racine,
                                  prefixe=pdv.prefixe)
            except (Exception, SystemExit):  # noqa: BLE001 — Clover illisible : mouvements du relevé seulement
                ctx.absents.add("Clover")
            return mouvements, depots

        mouvements, depots = lire_ou_vide(ctx, lire)
        # Sage absent : lecture vide gardée 45 s seulement (même délai que la surveillance de Sage), sinon 5 min
        ctx.app.memoire[cle] = (time.time() - (255 if "Sage" in ctx.absents else 0),
                                (mouvements, depots, set(ctx.absents)))
    with ctx.app.ecriture:
        registre = ria.Registre(ctx.racine)
        nouvelles = [c for c in commissions_reconnues(mouvements, RegistreEtats(ctx.racine).etats)
                     if c not in registre.commissions]
        if nouvelles:  # dépôt égal à la commission payée d'un état de compte : « Commission » d'office
            registre.commissions += nouvelles
            registre.enregistrer()
    return registre.lignes(mouvements, depots, du, au)


def operations(ctx: Contexte) -> Reponse:
    """Comme fenetre_ria.FenetreRia : Du … au, « 🔄 Actualiser », « ✔ Confirmer le surplus », « 💵 Commission »,
    « ➕ Paiement en espèces… », « 🗑 Supprimer », « 🔢 Comptes… », « 📒 Saisir dans Sage », « 📑 États de compte RIA… » ;
    ligne d'état ; 6 cartes (dépôts, surplus, retraits, paiements, commissions, solde dû à RIA) ; tableau coloré
    (bleu : surplus à confirmer, jaune : à saisir, gris : fait)."""
    from .. import ria
    from ..rapprochement import A_SAISIR as ABSENT, CONFIRME, RegistreReleves
    from . import taches

    def jour(cle, defaut):
        try:
            return date.fromisoformat(ctx.req.query.get(cle) or ctx.req.champ(cle))
        except (TypeError, ValueError):
            return defaut

    du, au = jour("du", date.today() - timedelta(days=45)), jour("au", date.today())
    retour = f"/ria?du={du}&au={au}"
    message = ""
    lignes, bilan = _lignes_ria(ctx, du, au, forcer=bool(ctx.req.query.get("actualiser")))
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        choisies = [lignes[int(k)] for k in ctx.req.champs("ligne") if k.isdigit() and int(k) < len(lignes)]
        try:
            with ctx.app.ecriture:
                registre = ria.Registre(ctx.racine)
                if action == "Confirmer le surplus":
                    choix = [l for l in choisies if l["sorte"] == "surplus"]
                    if not choix:
                        raise ValueError("Choisissez une ou plusieurs lignes « surplus » dans la liste.")
                    for l in choix:
                        d = l["depot"]
                        registre.ajouter(d.date.isoformat(), ria.SURPLUS, d.ria, d.origine, d.cle, ctx.u.nom)
                elif action == "Commission":
                    choix = [l for l in choisies if l["sorte"] == "releve" and l["montant"] > 0]
                    if not choix:
                        raise ValueError("Choisissez un dépôt de RIA du relevé dans la liste.")
                    for l in choix:
                        c = l["mouvement"].cle
                        (registre.commissions.remove if c in registre.commissions else registre.commissions.append)(c)
                elif action == "Paiement en espèces":
                    from ..design import montant_saisi

                    registre.ajouter(ctx.req.champ("jour").strip(), ria.ESPECES, montant_saisi(ctx.req.champ("montant")),
                                     ctx.req.champ("description").strip(), auteur=ctx.u.nom)
                elif action == "Supprimer":
                    if not action_permise(ctx, "Supprimer"):
                        raise ValueError("Votre profil n'a pas le droit « Supprimer ».")
                    choix = [l for l in choisies if l["sorte"] == "operation"]
                    if not choix:
                        raise ValueError("Choisissez une ou plusieurs opérations dans la liste.")
                    for l in choix:
                        registre.supprimer(l["operation"].numero)
                elif action == "Saisir dans Sage":
                    if not action_permise(ctx, "Saisir les dépenses dans Sage"):
                        raise ValueError("Votre profil n'a pas le droit « Saisir les dépenses dans Sage ».")
                    manquants = registre.comptes_manquants()
                    if manquants:
                        raise ValueError("Comptes à renseigner (« Comptes… ») : " + ", ".join(manquants))
                    a_saisir = [l for l in lignes if l["sorte"] == "releve" and l["mouvement"].etat in (ABSENT, CONFIRME)]
                    operations_ = registre.mouvements_a_saisir()
                    if not a_saisir and not operations_:
                        raise ValueError("Rien à saisir dans Sage.")
                    releves = RegistreReleves(ctx.racine)
                    for l in a_saisir:
                        m = l["mouvement"]
                        m.compte = registre.comptes["commissions" if l["genre"] == ria.COMMISSION else "ria"]
                        m.etat = CONFIRME
                        releves.retenir(m)
                    releves.enregistrer()
                    n = len(a_saisir) + len(operations_)

                    def travail(journal):
                        b = taches.executer_sage(ctx.racine, ["journal-bureau"], journal)
                        ctx.app.memoire.pop(("ria", du, au), None)
                        return [f"{len(b.get('saisis', []))} écriture(s) enregistrée(s)."] + b.get("a_verifier", []) \
                            + ([b["erreur"]] if b.get("erreur") else [])

                    return taches.lancer(ctx, f"Saisie de {n} écriture(s) RIA", travail, retour, sage=True)
                registre.enregistrer()
            lignes, bilan = _lignes_ria(ctx, du, au)
        except (ValueError, InvalidOperation) as erreur:
            message = _message(erreur=str(erreur) or "Montant ou date invalide.")
    registre = ria.Registre(ctx.racine)
    from .consultations import Section, tableau_section

    def couleur(l) -> str:
        if l["sorte"] == "surplus":
            return "etat-ria"
        return "termine" if l["etat"] in ("Dans Sage", ria.SAISIE) else "etat-a-saisir"

    rangees = [[f"<input type='checkbox' name='ligne' value='{n}'>", e(l["date"]), e(l["genre"]), e(l["description"]),
                argent(l["montant"]), e(l["etat"])] for n, l in enumerate(lignes)]
    manquants = registre.comptes_manquants()
    etat = f"{len(lignes)} opération(s). Bleu : surplus à confirmer ; jaune : à saisir dans Sage." + (
        f" ⚠ Comptes à renseigner (« Comptes… ») : {', '.join(manquants)}" if manquants else "")
    cartes = "".join(f"<div class='carte-total'><div class='t'>{titre}</div><div class='v'>{argent(v)}</div></div>"
                     for titre, v in (("Dépôts de RIA", bilan.depots), ("Surplus de dépôts", bilan.surplus),
                                      ("Retraits par RIA", bilan.retraits), ("Paiements", bilan.paiements),
                                      ("Commissions", bilan.commissions), ("Solde dû à RIA", bilan.solde)))
    paiement = ""
    if ctx.req.query.get("op") == "paiement":
        paiement = (f"<form method='post' class='carte'>{csrf(ctx)}<input type='hidden' name='du' value='{du}'>"
                    f"<input type='hidden' name='au' value='{au}'><h2>Paiement en espèces</h2><div class='ligne'><div>"
                    f"<label>Date du paiement :</label><input type='date' name='jour' value='{date.today()}' required>"
                    "</div><div><label>Montant payé en espèces :</label><input name='montant' size='10' required></div>"
                    "<div class='large'><label>Description (facultatif) :</label><input name='description' size='30'>"
                    "</div><button name='action' value='Paiement en espèces'>✔ Ajouter</button></div></form>")
    corps = (message + paiement
             + f"<form method='get' class='barre-onglet'><div><label>Du</label><input type='date' name='du' value='{du}'>"
               f"</div><div><label>au</label><input type='date' name='au' value='{au}'></div><button name='actualiser' "
               "value='1'>🔄 Actualiser</button></form>"
             + f"<form method='post'>{csrf(ctx)}<input type='hidden' name='du' value='{du}'><input type='hidden' "
               f"name='au' value='{au}'><div class='barre-onglet'><button class='second' name='action' value='Confirmer "
               "le surplus'>✔ Confirmer le surplus</button><button class='second' name='action' value='Commission'>💵 "
               f"Commission</button><a class='ouvrir' href='/ria?du={du}&amp;au={au}&amp;op=paiement'>➕ Paiement en "
               "espèces…</a><button class='danger' name='action' value='Supprimer'>🗑 Supprimer</button><a "
               "class='ouvrir' href='/comptes-ria'>🔢 Comptes…</a><button class='accent' name='action' value='Saisir "
               "dans Sage'>📒 Saisir dans Sage</button><a class='ouvrir' href='/etats-ria'>📑 États de compte RIA…</a>"
               f"</div><p class='{'erreur-texte' if manquants else 'note'}'>{e(etat)}</p>"
               f"<div class='cartes-six'>{cartes}</div>"
             + tableau_section(Section("Opérations RIA", ["", "Date", "Opération", "Description", "Montant", "État"],
                                       rangees, classes=[couleur(l) for l in lignes], html=set(range(6))))
             + "</form>")
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
    etats_ = registre.etats
    choisi = ctx.req.query.get("cle") or (etats_[0].cle if etats_ else "")
    x_choisi = next((x for x in etats_ if x.cle == choisi), None)
    if ctx.req.query.get("op") == "voir" and x_choisi is not None:  # « 👁 Voir l'état » : le PDF
        chemin = ctx.racine / "donnees" / "etats_ria" / x_choisi.fichier
        if chemin.exists():
            return Reponse(corps=chemin.read_bytes(), type="application/pdf", entetes={"Content-Disposition": "inline"})
    lignes = [[f"<input type='radio' name='cle' value='{e(x.cle)}'{' checked' if x.cle == choisi else ''}>",
               e(x.debut), e(x.fin), e(x.agence), argent(Decimal(x.solde_precedent)), argent(Decimal(x.debits)),
               argent(Decimal(x.credits)), argent(Decimal(x.total)), argent(Decimal(x.commission_payee)),
               argent(Decimal(x.commission_courue)),
               e(f"{x.dernier_depot} — {x.montant_dernier_depot} $" if x.dernier_depot else ""),
               "✔" if not x.remarques else e("⚠ " + " ".join(x.remarques))] for x in etats_]
    detail = [[l.jour, l.activite, l.reference, l.description, Decimal(l.montant), Decimal(l.frais),
               Decimal(l.commission), Decimal(l.mouvement), Decimal(l.solde)]
              for l in (x_choisi.lignes if x_choisi else [])]
    corps = (message
             + f"<form method='post' enctype='multipart/form-data' class='barre-onglet'>{csrf(ctx)}<input type='file' "
               "name='etat' accept='.pdf'><button name='action' value='Importer'>📥 Importer des états…</button><button "
               "class='second' name='action' value='Lire le courriel'>📧 Lire le courriel</button><button class='second' "
               "form='liste-etats' name='op' value='voir' formtarget='_blank'>👁 Voir l'état</button><button "
               "class='danger' name='action' value='Supprimer' form='supprimer-etat'>🗑 Supprimer</button><button "
               "class='accent' name='action' value='Traiter dans Sage'>📒 Traiter dans Sage</button></form>"
             + f"<p class='note'>{len(etats_)} état(s). Solde négatif : RIA doit au marché ; positif : le marché doit à "
               "RIA. La commission payée reconnaît son dépôt dans le relevé de la caisse.</p>"
             + "<form method='get' id='liste-etats'>"
             + tableau_section(Section("États de compte RIA", ["", "Du", "au", "Agence", "Solde précédent",
                                                              "Envois (débits)", "Versements (crédits)", "Solde",
                                                              "Commission payée", "Commission courue",
                                                              "Dernier dépôt RIA", "Contrôle"], lignes,
                                       html=set(range(12))))
             + "<button class='second'>Afficher les opérations de l'état choisi</button></form>"
             + f"<form method='post' id='supprimer-etat'>{csrf(ctx)}<input type='hidden' name='cle' value='{e(choisi)}'>"
               "</form>"
             + tableau_section(Section("Opérations de l'état choisi", ["Date", "Opération", "Réf.", "Description",
                                                                      "Montant", "Frais", "Commission",
                                                                      "Débit / crédit", "Solde"], detail)))
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
