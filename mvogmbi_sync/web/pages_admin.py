"""8e vague de l'application web : rubrique Administration (comme les pages 1 à 4 de interface.py, fenetre_sauvegarde
et page_utilisateurs). Réglages Clover, Sage 50, Courriel, Automatisation : config.toml (interface.ecrire_config) et
secrets dans le coffre-fort de Windows du serveur (jamais réaffichés : « enregistré » seulement) ; sauvegarde des
données ; utilisateurs, profils et droits par fonction (administrateurs seulement).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .pages import Contexte, Fonction, csrf, page, tableau
from .pages_compta import _message, action_permise
from .serveur import Reponse, echapper as e

ENREGISTRER = "Enregistrer la configuration"


def _ecrire(ctx: Contexte, modifier) -> None:
    """Relit config.toml, applique `modifier(config)`, l'écrit, puis met à jour la configuration du serveur."""
    from ..interface import ecrire_config, lire_config

    chemin = ctx.racine / "config.toml"
    with ctx.app.ecriture:
        config = lire_config(chemin)
        modifier(config)
        ecrire_config(chemin, config)
        ctx.app.config.clear()
        ctx.app.config.update(config)


def _secret(nom: str, libelle: str, cle_coffre: str) -> str:
    from .. import coffre

    try:
        present = coffre.present(cle_coffre)
    except Exception:  # noqa: BLE001
        present = False
    etat = "enregistré dans le coffre-fort" if present else "à saisir"
    return (f"<div><label>{e(libelle)} ({etat})</label><input type='password' name='{nom}' autocomplete='new-password' "
            "placeholder='inchangé si vide' size='20'></div>")


def _garder_secrets(ctx: Contexte, couples) -> None:
    from .. import coffre

    for champ, cle in couples:
        valeur = ctx.req.champ(champ)
        if valeur:
            coffre.ecrire(cle, valeur)


def _champ(nom: str, libelle: str, valeur, taille: int = 24, type_: str = "text") -> str:
    return (f"<div><label>{e(libelle)}</label><input type='{type_}' name='{nom}' value='{e(valeur or '')}' "
            f"size='{taille}'></div>")


def _refus_config(ctx: Contexte) -> str:
    return "" if action_permise(ctx, ENREGISTRER) else _message(erreur=f"Votre profil n'a pas le droit « {ENREGISTRER} ».")


# --------------------------------------------------------------------------------------------- Clover
def clover(ctx: Contexte) -> Reponse:
    from .. import coffre
    from . import taches

    message = ""
    if ctx.req.methode == "POST":
        if ctx.req.champ("action") == "Tester":
            def tester(journal):
                from ..points_vente import client

                return f"Connecté à « {client(ctx.racine).marchand().get('name', '?')} »."

            return taches.lancer(ctx, "Test de la connexion Clover", tester, "/admin/clover")
        message = _refus_config(ctx)
        if not message:
            identifiant = ctx.req.champ("merchant_id").strip()
            if identifiant and not (len(identifiant) == 13 and identifiant.isalnum()):
                message = _message(erreur="Identifiant marchand : 13 lettres ou chiffres.")
            else:
                def modifier(c):
                    c.setdefault("clover", {})["merchant_id"] = identifiant
                    c["clover"].setdefault("base_url", "https://api.clover.com")
                    c["clover"].pop("api_token", None)
                _ecrire(ctx, modifier)
                _garder_secrets(ctx, [("jeton", coffre.CLOVER_JETON)])
                message = _message("Configuration Clover enregistrée.")
    c = ctx.config.get("clover", {})
    corps = (message + f"<form method='post' class='carte'>{csrf(ctx)}<h2>Point de vente principal</h2>"
             "<div class='ligne'>" + _champ("merchant_id", "Identifiant marchand *", c.get("merchant_id"), 16)
             + _secret("jeton", "Jeton API *", coffre.CLOVER_JETON) + "</div><div class='boutons'><button "
             "name='action' value='Enregistrer'>Enregistrer</button><button class='second' name='action' "
             "value='Tester'>Tester la connexion</button></div></form>"
             + tableau(["Point de vente", "Marchand", "Client Sage", "Dépôt Sage", "Préfixe", "Actif"],
                       [[e(p.get("nom", "")), e(p.get("merchant_id", "")), e(p.get("client_sage", "")),
                         e(p.get("depot_sage", "")), e(p.get("prefixe", "")), "Oui" if p.get("actif", True) else "Non"]
                        for p in ctx.config.get("points_vente", [])])
             + "<p class='note'>Autres points de vente : application complète (Administration > Clover).</p>")
    return Reponse(corps=page(ctx, "Clover", corps))


# --------------------------------------------------------------------------------------------- Sage 50
def sage(ctx: Contexte) -> Reponse:
    from .. import coffre
    from ..calendrier_paie import Calendrier

    message = ""
    if ctx.req.methode == "POST":
        message = _refus_config(ctx)
        if not message:
            fichier = ctx.req.champ("fichier").strip()
            if fichier and not fichier.lower().endswith(".sai"):
                message = _message(erreur="Le fichier d'entreprise est un .SAI.")
            else:
                try:
                    premiere = ctx.req.champ("premiere").strip()
                    if premiere:
                        jour = date.fromisoformat(premiere)
                        cal = Calendrier(ctx.racine)
                        cal.definir(jour.year, jour, int(ctx.req.champ("delai") or 15))
                        cal.enregistrer()

                    def modifier(c):
                        c.setdefault("sage_base", {}).update(utilisateur=ctx.req.champ("utilisateur").strip(),
                                                              fichier_entreprise=fichier)
                        c["sage_base"].pop("mot_de_passe", None)
                        c["sage_base"].setdefault("port", 13540)
                        c.setdefault("sage_import", {}).update(fichier_entreprise=fichier)
                        for cle, defaut in (("version", "12001"), ("pays", "1"), ("position_numero", 3)):
                            c["sage_import"].setdefault(cle, defaut)
                    _ecrire(ctx, modifier)
                    _garder_secrets(ctx, [("lecture", coffre.SAGE_LECTURE), ("import", coffre.SAGE_IMPORT)])
                    message = _message("Configuration Sage 50 enregistrée.")
                except ValueError as erreur:
                    message = _message(erreur=f"Première paie : {erreur}")
    b = ctx.config.get("sage_base", {})
    cal = Calendrier(ctx.racine)
    premiere = cal.premiere(date.today().year)
    corps = (message + f"<form method='post' class='carte'>{csrf(ctx)}<h2>Fichier d'entreprise</h2><div class='ligne'>"
             + _champ("fichier", "Fichier d'entreprise (.SAI, sur le serveur) *",
                      b.get("fichier_entreprise") or ctx.config.get("sage_import", {}).get("fichier_entreprise"), 60)
             + _champ("utilisateur", "Utilisateur Sage (lecture) *", b.get("utilisateur") or "mvogmbi_sync", 16)
             + _secret("lecture", "Mot de passe de lecture", coffre.SAGE_LECTURE)
             + _secret("import", "Mot de passe de l'import (sysadmin)", coffre.SAGE_IMPORT)
             + "</div><h2>Paie</h2><div class='ligne'>"
             + _champ("premiere", "Première paie de l'année", premiere.isoformat() if premiere else "", 10, "date")
             + _champ("delai", "Délai après la période (jours)", cal.delai, 4)
             + "</div><div class='boutons'><button>Enregistrer</button></div></form>")
    return Reponse(corps=page(ctx, "Sage 50", corps))


# --------------------------------------------------------------------------------------------- Courriel
def courriel(ctx: Contexte) -> Reponse:
    from .. import coffre
    from ..courriel import adresses, adresses_invalides
    from . import taches

    message = ""
    if ctx.req.methode == "POST":
        if ctx.req.champ("action") == "Tester":
            def tester(journal):
                from ..courriel import envoyer_a

                dest = adresses(ctx.config.get("courriel", {}).get("destinataires", ""))
                if not dest:
                    raise RuntimeError("Aucun destinataire du compte rendu.")
                envoyer_a(ctx.config, dest[0], "Essai MVOGMBI_Sync", "Courriel d'essai envoyé depuis l'application web.")
                return f"Courriel d'essai envoyé à {dest[0]}."

            return taches.lancer(ctx, "Essai du courriel", tester, "/admin/courriel")
        message = _refus_config(ctx)
        if not message:
            v = {k: ctx.req.champ(k).strip() for k in ("serveur", "port", "securite", "utilisateur", "expediteur",
                                                         "destinataires", "copie", "cci", "b_serveur", "b_utilisateur",
                                                         "b_depuis", "fc_expediteurs", "fc_textes", "fc_depuis",
                                                         "ria_courriel", "ria_serveur", "ria_expediteurs", "ria_depuis")}
            invalides = adresses_invalides(v["destinataires"]) + adresses_invalides(v["copie"]) + \
                adresses_invalides(v["cci"])
            try:
                port = int(v["port"] or 587)
                for jour in (v["b_depuis"], v["fc_depuis"]):
                    if jour:
                        date.fromisoformat(jour)
            except ValueError:
                message = _message(erreur="Vérifiez le port et les dates (AAAA-MM-JJ).")
            else:
                if invalides:
                    message = _message(erreur="Adresse(s) invalide(s) : " + ", ".join(invalides))
                else:
                    def modifier(c):
                        c.setdefault("courriel", {}).update(
                            serveur=v["serveur"], port=port, securite=v["securite"] or "STARTTLS",
                            utilisateur=v["utilisateur"], expediteur=v["expediteur"],
                            destinataires=", ".join(adresses(v["destinataires"])),
                            copie=", ".join(adresses(v["copie"])), cci=", ".join(adresses(v["cci"])),
                            envoyer_si_succes=bool(ctx.req.champ("si_succes")))
                        c.setdefault("boite_paiements", {}).update(serveur=v["b_serveur"],
                                                                    utilisateur=v["b_utilisateur"],
                                                                    depuis=v["b_depuis"] or "2026-08-01")
                        c["boite_paiements"].setdefault("port", 993)
                        c.setdefault("factures_courriel", {}).update(
                            expediteurs=", ".join(x.strip() for x in v["fc_expediteurs"].replace(";", ",").split(",")
                                                  if x.strip()),
                            textes="; ".join(x.strip() for x in v["fc_textes"].split(";") if x.strip()),
                            depuis=v["fc_depuis"] or v["b_depuis"] or "2026-08-01",
                            automatique=bool(ctx.req.champ("fc_auto")))
                        c.setdefault("ria", {}).update(courriel=v["ria_courriel"], serveur=v["ria_serveur"],
                                                       expediteurs=v["ria_expediteurs"], depuis=v["ria_depuis"])
                    _ecrire(ctx, modifier)
                    _garder_secrets(ctx, [("mdp", coffre.COURRIEL), ("b_mdp", coffre.BOITE_PAIEMENTS),
                                          ("ria_mdp", coffre.BOITE_RIA)])
                    message = _message("Configuration du courriel enregistrée.")
    c, b = ctx.config.get("courriel", {}), ctx.config.get("boite_paiements", {})
    fc, r = ctx.config.get("factures_courriel", {}), ctx.config.get("ria", {})
    securite = "".join(f"<option{' selected' if s == c.get('securite', 'STARTTLS') else ''}>{s}</option>"
                       for s in ("STARTTLS", "SSL", "Aucune"))
    corps = (message + f"<form method='post'>{csrf(ctx)}<div class='carte'><h2>1. Envoi du compte rendu</h2>"
             "<div class='ligne'>" + _champ("serveur", "Serveur SMTP", c.get("serveur")) + _champ("port", "Port",
                                                                                                  c.get("port", 587), 5)
             + f"<div><label>Sécurité</label><select name='securite'>{securite}</select></div>"
             + _champ("utilisateur", "Utilisateur", c.get("utilisateur")) + _secret("mdp", "Mot de passe",
                                                                                     coffre.COURRIEL)
             + _champ("expediteur", "Expéditeur", c.get("expediteur")) + _champ("destinataires", "Destinataires",
                                                                                c.get("destinataires"), 40)
             + _champ("copie", "Copie", c.get("copie"), 30) + _champ("cci", "Copie cachée (Cci)", c.get("cci"), 30)
             + f"</div><p><label><input type='checkbox' name='si_succes' value='1'"
               f"{' checked' if c.get('envoyer_si_succes', True) else ''}> Envoyer aussi quand tout va bien</label></p>"
               "</div><div class='carte'><h2>2. Boîte des avis de paiement (IMAP, lecture seule)</h2><div class='ligne'>"
             + _champ("b_serveur", "Serveur IMAP", b.get("serveur")) + _champ("b_utilisateur", "Adresse",
                                                                             b.get("utilisateur"))
             + _secret("b_mdp", "Mot de passe", coffre.BOITE_PAIEMENTS) + _champ("b_depuis", "Depuis", b.get("depuis"),
                                                                                10, "date")
             + "</div></div><div class='carte'><h2>3. Factures fournisseurs reçues par courriel</h2><div class='ligne'>"
             + _champ("fc_expediteurs", "Expéditeurs", fc.get("expediteurs"), 40) + _champ("fc_textes", "Textes (« ; »)",
                                                                                         fc.get("textes"), 30)
             + _champ("fc_depuis", "Depuis", fc.get("depuis"), 10, "date")
             + f"</div><p><label><input type='checkbox' name='fc_auto' value='1'"
               f"{' checked' if fc.get('automatique', True) else ''}> Lire chaque nuit</label></p></div>"
               "<div class='carte'><h2>4. États de compte RIA</h2><div class='ligne'>"
             + _champ("ria_courriel", "Adresse", r.get("courriel")) + _champ("ria_serveur", "Serveur IMAP",
                                                                            r.get("serveur"))
             + _champ("ria_expediteurs", "Expéditeurs", r.get("expediteurs"), 30)
             + _champ("ria_depuis", "Depuis", r.get("depuis"), 10, "date") + _secret("ria_mdp", "Mot de passe (si autre "
                                                                                     "boîte)", coffre.BOITE_RIA)
             + "</div></div><div class='boutons'><button name='action' value='Enregistrer'>Enregistrer</button>"
               "<button class='second' name='action' value='Tester'>Envoyer un courriel d'essai</button></div></form>")
    return Reponse(corps=page(ctx, "Courriel", corps))


# --------------------------------------------------------------------------------------------- Automatisation
def automatisation(ctx: Contexte) -> Reponse:
    from .. import planification
    from . import taches

    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        message = _refus_config(ctx)
        if not message and action in ("Installer la tâche", "Retirer la tâche"):
            def tache(journal):
                if action == "Retirer la tâche":
                    return planification.retirer()
                return planification.installer(ctx.racine, ctx.config.get("automatique", {}).get("heure", "01:00"))

            return taches.lancer(ctx, action, tache, "/admin/automatisation")
        if not message:
            try:
                depart, enc = ctx.req.champ("date_depart").strip(), ctx.req.champ("enc_depart").strip()
                date.fromisoformat(depart)
                date.fromisoformat(enc)
                heure = ctx.req.champ("heure").strip()
                h, m = heure.split(":")
                assert 0 <= int(h) < 24 and 0 <= int(m) < 60
            except (ValueError, AssertionError):
                message = _message(erreur="Vérifiez les dates (AAAA-MM-JJ) et l'heure (HH:MM).")
            else:
                def modifier(c):
                    c.setdefault("automatique", {}).update(date_depart=depart, heure=heure)
                    c["automatique"].setdefault("delai_import", 3600)
                    c.setdefault("encaissements", {}).update(compte_depot=ctx.req.champ("compte").strip() or "1055",
                                                             date_depart=enc)
                    c["encaissements"].setdefault("mode", "Comptant")
                    c["encaissements"]["automatique"] = bool(ctx.req.champ("enc_auto"))
                _ecrire(ctx, modifier)
                message = _message("Automatisation enregistrée (réinstallez la tâche si l'heure a changé).")
    try:
        etat = planification.etat()
    except Exception as erreur:  # noqa: BLE001
        etat = str(erreur)
    a, en = ctx.config.get("automatique", {}), ctx.config.get("encaissements", {})
    corps = (message + f"<form method='post' class='carte'>{csrf(ctx)}<div class='ligne'>"
             + _champ("date_depart", "Facturer depuis", a.get("date_depart"), 10, "date")
             + _champ("heure", "Heure du traitement de nuit", a.get("heure", "01:00"), 6)
             + _champ("compte", "Compte de dépôt", en.get("compte_depot", "1055"), 6)
             + _champ("enc_depart", "Encaisser les dépôts depuis", en.get("date_depart"), 10, "date")
             + f"</div><p><label><input type='checkbox' name='enc_auto' value='1'"
               f"{' checked' if en.get('automatique', True) else ''}> Encaisser les dépôts la nuit</label></p>"
               "<div class='boutons'><button name='action' value='Enregistrer'>Enregistrer</button></div></form>"
             + f"<div class='carte'><h2>Tâche planifiée du serveur</h2><pre class='resultat'>{e(etat)}</pre>"
               f"<form method='post' class='boutons'>{csrf(ctx)}<button class='second' name='action' value='Installer la "
               "tâche'>Installer la tâche</button><button class='second' name='action' value='Retirer la tâche'>Retirer "
               "la tâche</button></form></div>")
    return Reponse(corps=page(ctx, "Automatisation", corps))


# --------------------------------------------------------------------------------------------- sauvegarde
def sauvegarde(ctx: Contexte) -> Reponse:
    from .. import sauvegarde as sv
    from . import taches

    cible = sv.dossier(ctx.racine, ctx.config)
    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        if action == "Sauvegarder":
            def sauvegarder(journal):
                etat = sv.sauvegarder(ctx.racine, ctx.config)
                return f"{'✔' if etat.ok else '✘'} {etat.message or etat.fichier} ({etat.fichiers} fichiers)."

            return taches.lancer(ctx, "Sauvegarde des données", sauvegarder, "/sauvegarde")
        if action == "Restaurer":
            nom_action = "Restaurer une sauvegarde"
            archive = cible / Path(ctx.req.champ("archive")).name
            if not action_permise(ctx, nom_action):
                message = _message(erreur=f"Votre profil n'a pas le droit « {nom_action} ».")
            elif not ctx.req.champ("confirme"):
                message = _message(erreur="Cochez la confirmation : les données actuelles seront remplacées (elles "
                                          "sont d'abord sauvegardées dans « avant_restauration »).")
            elif not archive.exists():
                message = _message(erreur="Archive introuvable.")
            else:
                def restaurer(journal):
                    etat, n = sv.restaurer(ctx.racine, ctx.config, archive)
                    return [f"{n} fichier(s) restauré(s) depuis {archive.name}.",
                            f"État actuel gardé : {etat.fichier}"]

                return taches.lancer(ctx, f"Restauration de {archive.name}", restaurer, "/sauvegarde")
    derniere = sv.derniere(ctx.racine)
    retard = sv.en_retard(ctx.racine)
    archives = sv.archives(cible) if cible.exists() else []
    lignes = [[e(p.name), f"{p.stat().st_size / 1_048_576:.1f} Mo".replace(".", ",")] for p in archives]
    options = "".join(f"<option>{e(p.name)}</option>" for p in archives)
    corps = (message + f"<div class='cartes'><div class='carte'><div class='t'>Dernière sauvegarde</div><div class='v'>"
             f"{e(derniere.quand[:16].replace('T', ' ') or 'aucune')}</div><div class='d'>{e(derniere.message)}</div></div>"
             f"<div class='carte'><div class='t'>Dossier</div><div class='d'>{e(str(cible))}</div></div></div>"
             + (_message(erreur=retard) if retard else "")
             + f"<form method='post' class='boutons'>{csrf(ctx)}<button name='action' value='Sauvegarder'>Sauvegarder "
               "maintenant</button></form>"
             + tableau(["Archive", "Taille"], lignes, {1})
             + (f"<form method='post' class='carte'>{csrf(ctx)}<h2>Restaurer</h2><div class='ligne'><div><label>Archive"
                f"</label><select name='archive'>{options}</select></div></div><p><label><input type='checkbox' "
                "name='confirme' value='1'> Je remplace les données actuelles par cette sauvegarde</label></p><div "
                "class='boutons'><button class='second' name='action' value='Restaurer'>Restaurer</button></div></form>"
                if archives else ""))
    return Reponse(corps=page(ctx, "Sauvegarde des données", corps))


# --------------------------------------------------------------------------------------------- utilisateurs
def utilisateurs(ctx: Contexte) -> Reponse:
    from ..utilisateurs import ACTIONS_FENETRES, ADMIN, ErreurUtilisateur, Registre
    from .menu import PAGES_MENU, cle_page, groupes

    message = ""
    if ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        try:
            with ctx.app.ecriture:
                reg = Registre(ctx.racine)
                nom = ctx.req.champ("nom").strip()
                if action == "Ajouter":
                    reg.ajouter(nom, ctx.req.champ("profil"), ctx.req.champ("mot_de_passe"))
                elif action == "Profil":
                    reg.changer_profil(nom, ctx.req.champ("profil"))
                elif action == "Mot de passe":
                    reg.changer_mot_de_passe(nom, ctx.req.champ("mot_de_passe"))
                    ctx.app.sessions.fermer_compte(nom)
                elif action in ("Désactiver", "Réactiver"):
                    reg.activer(nom, action == "Réactiver")
                    if action == "Désactiver":
                        ctx.app.sessions.fermer_compte(nom)
                elif action == "Supprimer":
                    if not action_permise(ctx, "Supprimer"):
                        raise ErreurUtilisateur("Votre profil n'a pas le droit « Supprimer ».")
                    reg.supprimer(nom)
                    ctx.app.sessions.fermer_compte(nom)
                elif action == "Nouveau profil":
                    reg.definir_profil(ctx.req.champ("profil_nouveau"), ["accueil"])
                elif action == "Accès":
                    profil = ctx.req.champ("profil")
                    fonctions = ctx.req.champs("fonction")
                    pages_cochees = set()
                    for _n, _i, elements in groupes():
                        for el in elements:
                            titre = PAGES_MENU[el][1] if isinstance(el, int) else el[1]
                            page_el = el if isinstance(el, int) else el[2]
                            cle = cle_page(el) if isinstance(el, int) else titre
                            if cle in fonctions:
                                pages_cochees.add(cle_page(page_el))
                    reg.definir_acces(profil, fonctions, sorted(pages_cochees))
                    toutes = [a for liste in ACTIONS_FENETRES.values() for a in liste]
                    reg.definir_fonctions(profil, [a for a in toutes if a not in set(ctx.req.champs("action_permise"))])
                    reg.definir_export(profil, bool(ctx.req.champ("export")))
                    reg.definir_tous_employes(profil, bool(ctx.req.champ("tous_employes")))
                reg.enregistrer()
            message = _message("Enregistré.")
        except ErreurUtilisateur as erreur:
            message = _message(erreur=str(erreur))
    reg = Registre(ctx.racine)
    profils = "".join(f"<option>{e(p)}</option>" for p in reg.profils)
    lignes = []
    for u in reg.utilisateurs:
        cache = f"<input type='hidden' name='nom' value='{e(u.nom)}'>"
        lignes.append([e(u.nom), e(u.profil), "Verrouillé" if u.verrouille else ("Actif" if u.actif else "Inactif"),
                       e(u.derniere_connexion.replace("T", " ")),
                       f"<form method='post' class='ligne'>{csrf(ctx)}{cache}<select name='profil'>"
                       + "".join(f"<option{' selected' if p == u.profil else ''}>{e(p)}</option>" for p in reg.profils)
                       + "</select><button class='second' name='action' value='Profil'>Profil</button></form>",
                       f"<form method='post' class='ligne'>{csrf(ctx)}{cache}<input type='password' name='mot_de_passe' "
                       "size='10' autocomplete='new-password' placeholder='6 caractères ou plus'><button class='second' "
                       "name='action' value='Mot de passe'>Changer</button></form>",
                       f"<form method='post' class='ligne'>{csrf(ctx)}{cache}<button class='second' name='action' "
                       f"value='{'Désactiver' if u.actif else 'Réactiver'}'>{'Désactiver' if u.actif else 'Réactiver'}"
                       "</button><button class='second' name='action' value='Supprimer'>Supprimer</button></form>"])
    choisi = ctx.req.query.get("profil") or ctx.req.champ("profil") or next((p for p in reg.profils if p != ADMIN), "")
    acces = ""
    if choisi and choisi != ADMIN and choisi in reg.profils:
        permises = reg.fonctions_permises.get(choisi)
        pages_profil = set(reg.profils.get(choisi, []))
        refusees = set(reg.fonctions_refusees.get(choisi, []))
        arbre = ""
        for nom_groupe, icone, elements in groupes():
            cases = ""
            for el in elements:
                titre = PAGES_MENU[el][1] if isinstance(el, int) else el[1]
                if el == 14:
                    continue
                cle = cle_page(el) if isinstance(el, int) else titre
                if permises is not None:
                    coche = cle in permises
                else:
                    page_el = el if isinstance(el, int) else el[2]
                    coche = cle_page(page_el) in pages_profil and titre not in refusees
                cases += (f"<label><input type='checkbox' name='fonction' value='{e(cle)}'{' checked' if coche else ''}>"
                          f" {e(titre)}</label><br>")
            arbre += f"<div class='carte'><strong>{icone} {e(nom_groupe or 'Accueil et aide')}</strong><br>{cases}</div>"
        actions = "".join(
            f"<div class='carte'><strong>{e(g)}</strong><br>" + "".join(
                f"<label><input type='checkbox' name='action_permise' value='{e(a)}'{'' if a in refusees else ' checked'}>"
                f" {e(a)}</label><br>" for a in liste) + "</div>" for g, liste in ACTIONS_FENETRES.items())
        acces = (f"<form method='post'>{csrf(ctx)}<input type='hidden' name='profil' value='{e(choisi)}'>"
                 f"<h2>Fonctions permises au profil « {e(choisi)} »</h2><div class='tuiles'>{arbre}</div>"
                 f"<h2>Actions dans les fenêtres</h2><div class='tuiles'>{actions}</div><p><label><input type='checkbox' "
                 f"name='export' value='1'{' checked' if choisi not in reg.sans_export else ''}> Exporter les données"
                 f"</label> <label><input type='checkbox' name='tous_employes' value='1'"
                 f"{' checked' if choisi not in reg.limites else ''}> Voir tous les employés</label></p><div "
                 "class='boutons'><button name='action' value='Accès'>Enregistrer les accès</button></div></form>")
    choix_profil = "".join(f"<option{' selected' if p == choisi else ''}>{e(p)}</option>" for p in reg.profils
                           if p != ADMIN)
    corps = (message + tableau(["Utilisateur", "Profil", "État", "Dernière connexion", "Changer le profil",
                                "Nouveau mot de passe", ""], lignes)
             + f"<form method='post' class='carte'>{csrf(ctx)}<h2>Nouvel utilisateur</h2><div class='ligne'>"
               "<div><label>Nom</label><input name='nom' required></div><div><label>Profil</label><select name='profil'>"
               f"{profils}</select></div><div><label>Mot de passe (6 caractères ou plus)</label><input type='password' "
               "name='mot_de_passe' autocomplete='new-password' required></div><button name='action' value='Ajouter'>"
               "Ajouter</button></div></form>"
             + f"<form class='ligne' method='get'><div><label>Profil à régler</label><select name='profil'>{choix_profil}"
               "</select></div><button class='second'>Afficher</button></form>"
             + f"<form method='post' class='ligne'>{csrf(ctx)}<div><label>Nouveau profil</label><input "
               "name='profil_nouveau'></div><button class='second' name='action' value='Nouveau profil'>Créer le profil"
               "</button></form>" + acces
             + "<p class='note'>Un compte verrouillé (3 mots de passe faux) se rouvre en lui donnant un nouveau mot de "
               "passe. Il reste toujours au moins un administrateur actif.</p>")
    return Reponse(corps=page(ctx, "Utilisateurs", corps))


FONCTIONS = [
    Fonction("/admin/clover", "clover", "clover", clover, "🛒", "Administration", menu=False, page_entiere=True),
    Fonction("/admin/sage", "sage", "sage", sage, "📒", "Administration", menu=False, page_entiere=True),
    Fonction("/admin/courriel", "courriel", "courriel", courriel, "📧", "Administration", menu=False,
             page_entiere=True),
    Fonction("/admin/automatisation", "automatisation", "automatisation", automatisation, "⏰", "Administration",
             menu=False, page_entiere=True),
    Fonction("/sauvegarde", "Sauvegarde des données", "automatisation", sauvegarde, "💾", "Administration", menu=False),
    Fonction("/utilisateurs", "utilisateurs", "utilisateurs", utilisateurs, "👥", "Administration", menu=False,
             page_entiere=True),
]
WEB = {"Clover": "/admin/clover", "Sage 50": "/admin/sage", "Courriel": "/admin/courriel",
       "Automatisation": "/admin/automatisation", "Sauvegarde des données": "/sauvegarde", "Utilisateurs": "/utilisateurs"}
