"""8e vague de l'application web : rubrique Administration (comme les pages 1 à 4 de interface.py, fenetre_sauvegarde
et page_utilisateurs). Réglages Clover, Sage 50, Courriel, Automatisation : config.toml (interface.ecrire_config) et
secrets dans le coffre-fort de Windows du serveur (jamais réaffichés : « enregistré » seulement) ; sauvegarde des
données ; utilisateurs, profils et droits par fonction (administrateurs seulement).
"""

from __future__ import annotations

from datetime import date, datetime
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


def _titre(texte: str, sous_titre: str = "") -> str:
    """Application._titre : titre vert, soulignement jaune et rouge, sous-titre."""
    return (f"<div class='titre-admin'><div class='t'>{e(texte)}</div><div class='souligne'><span class='j'></span>"
            f"<span class='r'></span></div>" + (f"<p>{e(sous_titre)}</p>" if sous_titre else "") + "</div>")


def _carte(numero: str, titre: str, contenu: str, description: str = "", couleur: str = "") -> str:
    """Application._carte : carte blanche à liseré, pastille numérotée et titre, zone des champs."""
    return (f"<div class='carte-admin {couleur}'><div class='entete'><span class='pastille'>{e(numero)}</span>"
            f"{e(titre)}</div>" + (f"<p class='desc'>{e(description)}</p>" if description else "")
            + f"<div class='champs'>{contenu}</div></div>")


def _ligne(libelle: str, champ: str, aide: str = "") -> str:
    """Application._champ : libellé à gauche, champ large, aide en dessous."""
    return (f"<label>{e(libelle)}</label><div>{champ}" + (f"<div class='aide'>{e(aide)}</div>" if aide else "")
            + "</div>")


def _entree(nom: str, valeur="", type_: str = "text", taille: int = 52) -> str:
    return f"<input type='{type_}' name='{nom}' value='{e(valeur or '')}' size='{taille}'>"


def _mot_de_passe(nom: str, cle_coffre: str) -> str:
    from .. import coffre

    try:
        present = coffre.present(cle_coffre)
    except Exception:  # noqa: BLE001
        present = False
    return (f"<input type='password' name='{nom}' autocomplete='new-password' size='52' placeholder='"
            f"{'•••••••• (enregistré dans le coffre-fort : laissez vide pour le garder)' if present else ''}'>")


def _sortie_test(ctx: Contexte, cle: str) -> str:
    """Zone de sortie (Application._sortie) : résultat du dernier test lancé de cette page."""
    texte = ctx.app.memoire.get(("test_admin", cle), "")
    return f"<pre class='sortie'>{e(texte)}</pre>" if texte else ""


ENREGISTRER_CONFIG = ("<div class='barre-onglet'><button class='a-droite' name='action' value='Enregistrer'>💾 "
                      "Enregistrer la configuration</button></div>")


def _refus_config(ctx: Contexte) -> str:
    return "" if action_permise(ctx, ENREGISTRER) else _message(erreur=f"Votre profil n'a pas le droit « {ENREGISTRER} ».")


# --------------------------------------------------------------------------------------------- Clover
def clover(ctx: Contexte) -> Reponse:
    from .. import coffre
    from . import taches

    message = ""
    if ctx.req.methode == "POST" and ctx.req.champ("op"):
        reponse = _action_point_vente(ctx)
        if isinstance(reponse, Reponse):
            return reponse
        message = reponse
    elif ctx.req.methode == "POST" and ctx.req.champ("action") == "Tester":
        def tester():
            from ..points_vente import client

            return f"connecté à « {client(ctx.racine).marchand().get('name', '?')} »"

        _tester(ctx, "clover", "Test Clover", tester)
    elif ctx.req.methode == "POST":
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
    fiche = ctx.req.query.get("pv")
    if fiche:
        return Reponse(corps=page(ctx, "Clover", message + _fiche_point_vente(ctx, fiche)))
    # un seul formulaire pour la carte 1 et « Enregistrer la configuration » (attribut form=) ; la carte 2 a le sien
    corps = (message + _titre("Accès à votre compte Clover (lecture des ventes)",
                              "L'application lit les ventes payées dans Clover ; elle n'y modifie jamais rien.")
             + f"<form method='post' id='config'>{csrf(ctx)}"
             + _carte("1", "Identifiants Clover", _ligne(
                 "Identifiant marchand", _entree("merchant_id", c.get("merchant_id")),
                 "13 caractères, visibles dans l'adresse du tableau de bord Clover après « /m/ ».")
                 + _ligne("Jeton API", _mot_de_passe("jeton", coffre.CLOVER_JETON),
                          "Clover > Compte et configuration > Jetons API (droits en lecture). Laissez vide pour "
                          "conserver le jeton enregistré.")
                 + "<span></span><div><button name='action' value='Tester'>🔌 Tester la connexion à Clover</button>"
                   "</div>" + "<span></span>" + _zone_sortie(ctx, "clover"))
             + "</form>"
             + _carte("2", "Points de vente", _liste_points_vente(ctx),
                      "Chaque point de vente Clover est un dépôt (emplacement d'inventaire) dans Sage, avec son client "
                      "Sage et ses factures (« Vente 2026-10-23 » pour le n° 1, « V2 2026-10-23 » pour le n° 2…). Le "
                      "n° 1 utilise les identifiants ci-dessus.")
             + ENREGISTRER_CONFIG.replace("<button ", "<button form='config' "))
    return Reponse(corps=page(ctx, "Clover", corps))


def _tester(ctx: Contexte, cle: str, titre: str, fonction) -> None:
    """Test court lancé tout de suite ; son résultat va dans la zone de sortie de la page (Application._sortie)."""
    from datetime import datetime

    try:
        texte = f"✔ {fonction()}"
    except (Exception, SystemExit) as erreur:  # noqa: BLE001
        texte = f"✘ {erreur}"
    ctx.app.memoire[("test_admin", cle)] = f"{datetime.now():%H:%M:%S}  {titre} : {texte}"


def _zone_sortie(ctx: Contexte, cle: str) -> str:
    """Zone de sortie toujours visible (cadre gris de Windows), vide tant qu'aucun test n'a été lancé."""
    return f"<div><pre class='sortie'>{e(ctx.app.memoire.get(('test_admin', cle), ''))}</pre></div>"


# --------------------------------------------------------------------------------------------- points de vente
def _points(ctx: Contexte):
    from ..points_vente import points_de_vente

    return points_de_vente(ctx.config)


def _jeton_present(cle: str) -> bool:
    from .. import coffre

    try:
        return coffre.present(cle)
    except Exception:  # noqa: BLE001
        return False


def _liste_points_vente(ctx: Contexte) -> str:
    """CartePointsVente : tableau (N°, Nom, Identifiant marchand, Jeton, Client Sage, Dépôt Sage, Préfixe, Actif),
    une ligne choisie, puis « ➕ Ajouter un point de vente », « Modifier », « Supprimer », « 🔌 Tester ce point de
    vente »."""
    choisi = ctx.req.champ("code") or "1"
    lignes = []
    for x in _points(ctx):
        lignes.append(
            f"<tr><td><input type='radio' form='pv' name='code' value='{e(x.code)}'"
            f"{' checked' if x.code == choisi else ''}></td><td class='n'>{e(x.code)}</td><td>{e(x.nom)}</td>"
            f"<td>{e(x.merchant_id or '—')}</td><td class='centre'>{'✔' if _jeton_present(x.cle_jeton) else '✘'}</td>"
            f"<td>{e(x.client_sage)}</td><td>{e(x.depot_sage)}</td><td class='centre'>{e(x.prefixe)}</td>"
            f"<td class='centre'>{'Oui' if x.actif else 'Non'}</td></tr>")
    entetes = "".join(f"<th>{e(t)}</th>" for t in ("", "N°", "Nom", "Identifiant marchand", "Jeton", "Client Sage",
                                                     "Dépôt Sage", "Préfixe", "Actif"))
    return (f"<div class='defile'><table><tr>{entetes}</tr>{''.join(lignes)}</table></div>"
            f"<form method='post' id='pv'>{csrf(ctx)}<div class='barre-onglet'>"
            "<button name='op' value='ajouter'>➕ Ajouter un point de vente</button>"
            "<button class='second' name='op' value='modifier'>Modifier</button>"
            "<button class='danger' name='op' value='supprimer'>Supprimer</button>"
            "<button class='second' name='op' value='tester'>🔌 Tester ce point de vente</button></div></form>")


def _fiche_point_vente(ctx: Contexte, code: str) -> str:
    """page_points_vente.Fiche : Nom, (Identifiant marchand, Jeton API), Client Sage, Dépôt Sage, (Préfixe), Actif,
    « * champ obligatoire », Enregistrer / Annuler."""
    from ..points_vente import DEPOT_DEFAUT, LONGUEUR_PREFIXE, PointDeVente

    points = _points(ctx)
    p = next((x for x in points if x.code == code), None)
    if p is None:
        codes = {x.code for x in points}
        code = next(str(n) for n in range(2, 100) if str(n) not in codes)
        p = PointDeVente(code, f"Point de vente {code}", "", "", DEPOT_DEFAUT, f"V{code}", True)
    jeton_present = not p.principal and _jeton_present(p.cle_jeton)
    champs = _ligne("Nom *", _entree("nom", p.nom, taille=44))
    if not p.principal:
        champs += _ligne("Identifiant marchand *", _entree("marchand", p.merchant_id, taille=44),
                         "13 caractères, dans l'adresse du tableau de bord Clover de ce point de vente.")
        champs += _ligne("Jeton API" + ("" if jeton_present else " *"),
                         "<input type='password' name='jeton' autocomplete='new-password' size='44'>",
                         "Laissez vide pour conserver le jeton enregistré." if jeton_present else
                         "Clover > Compte et configuration > Jetons API (droits en lecture).")
    champs += _ligne("Client Sage *", _entree("client", p.client_sage, taille=44),
                     "Client des factures de ce point de vente (fiche : « Ce client utilise mes n° articles »).")
    champs += _ligne("Dépôt Sage *", _entree("depot", p.depot_sage, taille=44),
                     f"Emplacement d'inventaire Sage de ce point de vente (« {DEPOT_DEFAUT} » par défaut).")
    if not p.principal:
        champs += _ligne("Préfixe des factures *", _entree("prefixe", p.prefixe, taille=10),
                         f"{LONGUEUR_PREFIXE} caractères au plus, sans espace : « {p.prefixe or 'V2'} 2026-10-23/25 ».")
        champs += ("<span></span><div><label class='case'><input type='checkbox' name='actif' value='1'"
                   f"{' checked' if p.actif else ''}> Actif (traité avec « tous les points de vente »)</label></div>")
    return (_titre(f"Point de vente {p.code}") + f"<form method='post' action='/admin/clover'>{csrf(ctx)}"
            f"<input type='hidden' name='code' value='{e(p.code)}'>"
            + _carte(p.code, "Point de vente", champs)
            + "<div class='barre-onglet'><span class='note'>* champ obligatoire</span><span class='a-droite'>"
              "<button name='op' value='enregistrer'>Enregistrer</button> <a class='ouvrir' href='/admin/clover'>"
              "Annuler</a></span></div></form>")


def _action_point_vente(ctx: Contexte):
    """Ajouter / Modifier (fiche), Supprimer (le n° 1 jamais), Tester ce point de vente, Enregistrer la fiche."""
    from .. import coffre
    from ..points_vente import DEPOT_DEFAUT, PRINCIPAL, PointDeVente, problemes_configuration
    from .serveur import redirection

    op, code = ctx.req.champ("op"), ctx.req.champ("code")
    points = _points(ctx)
    p = next((x for x in points if x.code == code), None)
    if op == "ajouter":
        return redirection("/admin/clover?pv=nouveau")
    if p is None and op != "enregistrer":
        return _message(erreur="Sélectionnez un point de vente dans la liste.")
    if op == "modifier":
        return redirection(f"/admin/clover?pv={p.code}")
    if op == "tester":
        def tester():
            from ..__main__ import charger_config
            from ..api_clover import ClientClover

            try:
                config = charger_config(ctx.racine / "config.toml", p)
            except SystemExit as exc:
                raise RuntimeError(str(exc)) from None
            return f"connecté à « {ClientClover(config).marchand().get('name', '?')} »"

        _tester(ctx, "clover", f"Test Clover ({p.libelle})", tester)
        return ""
    if refus := _refus_config(ctx):
        return refus
    if op == "supprimer":
        if p.principal:
            return _message(erreur="Le point de vente n° 1 ne peut pas être supprimé.")
        points = [x for x in points if x.code != p.code]
    elif op == "enregistrer":
        if p is None:
            p = PointDeVente(code, "", "", "", DEPOT_DEFAUT, "", True)
        v = {k: ctx.req.champ(k).strip() for k in ("nom", "marchand", "jeton", "client", "depot", "prefixe")}
        jeton_present = not p.principal and _jeton_present(p.cle_jeton)
        cles = ["nom", "client", "depot"] + ([] if p.principal else ["marchand", "prefixe"]
                                              + ([] if jeton_present else ["jeton"]))
        manquants = [k for k in cles if not v[k]]
        if not p.principal and v["marchand"] and (len(v["marchand"]) != 13 or not v["marchand"].isalnum()):
            manquants.append("identifiant marchand (13 lettres ou chiffres)")
        if manquants:
            return _message(erreur="Champs obligatoires à remplir : " + ", ".join(manquants) + ".")
        p.nom, p.client_sage, p.depot_sage = v["nom"], v["client"], v["depot"] or DEPOT_DEFAUT
        if not p.principal:
            p.merchant_id, p.prefixe, p.actif = v["marchand"], v["prefixe"], bool(ctx.req.champ("actif"))
        points = [x for x in points if x.code != p.code] + [p]
        points.sort(key=lambda x: (x.code != PRINCIPAL, int(x.code) if x.code.isdigit() else 999, x.code))
    else:
        return ""
    if erreurs := problemes_configuration(points):
        return _message(erreur=" ".join(erreurs))

    def modifier(c):
        principal = points[0]
        c.setdefault("clover", {}).update(nom=principal.nom, client_sage=principal.client_sage,
                                          depot_sage=principal.depot_sage)
        c["points_vente"] = [dict(code=x.code, nom=x.nom, merchant_id=x.merchant_id, client_sage=x.client_sage,
                                  depot_sage=x.depot_sage, prefixe=x.prefixe, actif=x.actif) for x in points[1:]]
        if not c["points_vente"]:
            c.pop("points_vente")

    _ecrire(ctx, modifier)
    if op == "supprimer":
        coffre.supprimer(p.cle_jeton)
        return _message(f"Point de vente {p.libelle} supprimé. Ses factures déjà dans Sage ne sont pas touchées.")
    if v["jeton"] and not p.principal:
        coffre.ecrire(p.cle_jeton, v["jeton"])
    return _message(f"Point de vente {p.libelle} enregistré.")


# --------------------------------------------------------------------------------------------- Sage 50
def _test_sage(ctx: Contexte) -> str:
    """Application.tester_sage : lecture de Sage (ouvert, sinon base ouverte puis refermée par l'outil d'import)."""
    from ..__main__ import executable_import, ouvrir_base_sage
    from ..automatique import lire_etat_sage
    from ..facture import CLIENT
    from ..sage_auto import lire_pendant_connexion

    fichier = Path(ctx.config["sage_import"]["fichier_entreprise"])
    if not fichier.is_file():
        raise RuntimeError(f"fichier introuvable : {fichier}")

    def lecture():
        with ouvrir_base_sage(ctx.config, fichier) as base:
            return lire_etat_sage(base, CLIENT)

    try:
        etat, mode = lecture(), "Sage ouvert"
    except PermissionError:
        raise
    except Exception:  # noqa: BLE001
        exe = executable_import()
        if not exe:
            raise RuntimeError("Sage_SA_import.exe ?") from None
        etat = lire_pendant_connexion(exe, fichier, lecture)
        mode = "Sage fermé : base ouverte puis refermée automatiquement"
    client = "OK" if etat.client_configure else (
        "À RÉGLER : cocher « Ce client utilise mes n° articles » dans la fiche du client")
    sans_compte = sum(1 for a in etat.articles if not a.compte_revenus and a.type == "Inventory")
    return (f"{mode}. {len(etat.articles)} articles. Dernière facture journalière : {etat.derniere_date or 'aucune'}. "
            f"Client « {CLIENT} » : {client}. Articles sans compte de produits : {sans_compte}.")


def sage(ctx: Contexte) -> Reponse:
    from .. import coffre
    from ..calendrier_paie import Calendrier

    message = ""
    if ctx.req.methode == "POST" and ctx.req.champ("action") == "Tester":
        from . import taches

        def tester(journal):
            texte = _test_sage(ctx)
            ctx.app.memoire[("test_admin", "sage")] = f"{datetime.now():%H:%M:%S}  Test Sage : ✔ {texte}"
            return [texte]

        return taches.lancer(ctx, "Test Sage", tester, "/admin/sage")
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

                    depart, compte, enc = (ctx.req.champ(k).strip() for k in ("date_depart", "compte", "enc_depart"))
                    for jour_ in (depart, enc):
                        if jour_:
                            date.fromisoformat(jour_)

                    def modifier(c):
                        if depart:
                            c.setdefault("automatique", {})["date_depart"] = depart
                        if compte or enc:
                            c.setdefault("encaissements", {}).update(compte_depot=compte or "1055",
                                                                     date_depart=enc or date.today().isoformat())
                            c["encaissements"].setdefault("mode", "Comptant")
                            c["encaissements"].setdefault("automatique", True)
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
                    message = _message(erreur=f"Vérifiez les dates (AAAA-MM-JJ) : {erreur}")
    b = ctx.config.get("sage_base", {})
    cal = Calendrier(ctx.racine)
    premiere = cal.premiere(date.today().year)
    a, en = ctx.config.get("automatique", {}), ctx.config.get("encaissements", {})
    corps = (message + _titre("Fichier d'entreprise et comptes Sage") + f"<form method='post'>{csrf(ctx)}"
             + _carte("1", "Fichier d'entreprise", _ligne(
                 "Fichier d'entreprise (.SAI)", _entree("fichier", ctx.req.query.get("fichier")
                                                        or b.get("fichier_entreprise")
                                                        or ctx.config.get("sage_import", {}).get("fichier_entreprise"))
                 + " <a class='ouvrir' href='/parcourir-sai'>Parcourir…</a>",
                 "Le fichier dans lequel les factures sont importées (chemin sur le serveur). Pour les essais : une "
                 "COPIE.")
                 + _ligne("Premier jour à importer", _entree("date_depart", a.get("date_depart", ""), "date", 12),
                          "AAAA-MM-JJ. Utilisé seulement si Sage ne contient encore aucune facture « Vente AAAA-MM-JJ ».")
                 + _ligne("Compte de dépôt des encaissements", _entree("compte", en.get("compte_depot", "1055"),
                                                                        taille=10),
                          "Compte de banque Sage où Clover dépose les ventes par carte (1055 = Compte Desjardins).")
                 + _ligne("Encaisser à partir des ventes du", _entree("enc_depart", en.get("date_depart", ""), "date",
                                                                       12),
                          "AAAA-MM-JJ. Les dépôts des ventes antérieures ne sont jamais encaissés."))
             + _carte("2", "Utilisateurs Sage", _ligne(
                 "Utilisateur Sage (lecture)", _entree("utilisateur", b.get("utilisateur") or "mvogmbi_sync"),
                 "Utilisateur avec « Droits d'accès aux produits tiers : Consultation seule » et accès Vue aux "
                 "modules Stocks & Services et Clients & Ventes.")
                 + _ligne("Mot de passe (lecture)", _mot_de_passe("lecture", coffre.SAGE_LECTURE))
                 + _ligne("Mot de passe Sage pour l'import", _mot_de_passe("import", coffre.SAGE_IMPORT),
                          "Mot de passe demandé par la fenêtre « Sage 50 - Password » de l'import (utilisateur "
                          "sysadmin).")
                 + "<span></span><div><button name='action' value='Tester'>📒 Tester l'accès à Sage</button></div>"
                 + "<span></span>" + _zone_sortie(ctx, "sage"))
             + _carte("3", "Paie", _ligne(
                 "Première paie de l'année", _entree("premiere", premiere.isoformat() if premiere else "", "date", 12),
                 "Date de la première paie de l'année : les paies suivantes (tous les 14 jours) et leurs périodes se "
                 "calculent (« Paie > Calendrier de paie »).")
                 + _ligne("Jours entre la fin de la période et la paie", _entree("delai", cal.delai, taille=5)))
             + ENREGISTRER_CONFIG + "</form>")
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
    securite = "".join(f"<option{' selected' if x.casefold() == str(c.get('securite', 'starttls')).casefold() else ''}>"
                       f"{x}</option>" for x in ("starttls", "ssl", "aucune"))

    def case(nom: str, coche: bool, texte: str) -> str:
        return (f"<span></span><div><label class='case'><input type='checkbox' name='{nom}' value='1'"
                f"{' checked' if coche else ''}> {e(texte)}</label></div>")

    corps = (message + _titre("Alertes par courriel") + f"<form method='post'>{csrf(ctx)}"
             + _carte("1", "Serveur d'envoi", _ligne(
                 "Serveur d'envoi (SMTP)", _entree("serveur", c.get("serveur")),
                 "Ex. smtp.office365.com (Outlook) ou smtp.gmail.com (Gmail : mot de passe d'application).")
                 + _ligne("Port", _entree("port", c.get("port", 587), taille=8))
                 + _ligne("Sécurité", f"<select name='securite'>{securite}</select>")
                 + _ligne("Utilisateur", _entree("utilisateur", c.get("utilisateur")))
                 + _ligne("Mot de passe", _mot_de_passe("mdp", coffre.COURRIEL)))
             + _carte("2", "Envoi du compte rendu", _ligne("Expéditeur", _entree("expediteur", c.get("expediteur")))
                      + _ligne("Destinataire(s)", _entree("destinataires", c.get("destinataires")),
                               "Une ou plusieurs adresses séparées par des virgules.")
                      + _ligne("Copie cachée (Cci)", _entree("cci", c.get("cci")),
                               "Reçoit en copie cachée chaque courriel envoyé par l'application (bulletins, T4 / RL-1, "
                               "relances), sauf les comptes rendus du traitement automatique. Vide : le premier "
                               "destinataire ci-dessus.")
                      + _ligne("Autres destinataires", _entree("copie", c.get("copie")),
                               "Facultatif : autres personnes à informer, adresses séparées par des virgules.")
                      + case("si_succes", c.get("envoyer_si_succes", True), "Envoyer le compte rendu après chaque "
                             "traitement, y compris en cas de succès (dates traitées et leur état)")
                      + "<span></span><div><button name='action' value='Tester'>✉ Envoyer un courriel de test</button>"
                        "</div>")
             + _carte("3", "Avis de paiement (lecture de la boîte)", _ligne(
                 "Serveur (IMAP)", _entree("b_serveur", b.get("serveur", "")))
                 + _ligne("Adresse", _entree("b_utilisateur", b.get("utilisateur", "")))
                 + _ligne("Mot de passe", _mot_de_passe("b_mdp", coffre.BOITE_PAIEMENTS))
                 + _ligne("Lire les avis à partir du", _entree("b_depuis", b.get("depuis", "2026-08-01"), "date", 12)),
                 "Boîte où arrivent les avis Interac de Desjardins : l'application les lit (sans les marquer comme "
                 "lus) pour enregistrer les paiements aux fournisseurs.")
             + _carte("4", "Factures fournisseurs reçues par courriel", _ligne(
                 "Expéditeurs des factures", _entree("fc_expediteurs", fc.get("expediteurs", "")),
                 "Adresses ou domaines séparés par des virgules. Vide : tout courriel dont le sujet ou la pièce jointe "
                 "parle de facture.")
                 + _ligne("Textes dans le courriel", _entree("fc_textes", fc.get("textes", "")),
                          "Textes séparés par des points-virgules : les pièces jointes de tout courriel qui contient "
                          "l'un d'eux (sujet, expéditeur, message ou nom du fichier) sont prises.")
                 + _ligne("Lire les factures à partir du", _entree("fc_depuis", fc.get("depuis", b.get("depuis", "")),
                                                                    "date", 12))
                 + case("fc_auto", fc.get("automatique", True), "Les relever aussi pendant le traitement de nuit"),
                 "Les factures (PDF ou photos) jointes aux courriels de cette même boîte sont copiées dans « Fournisseur "
                 "> Factures fournisseurs », puis lues. Lecture seule : aucun courriel n'est marqué comme lu, déplacé "
                 "ni supprimé ; chaque pièce jointe n'est prise qu'une fois.")
             + _carte("5", "États RIA reçus par courriel", _ligne(
                 "Courriel de réception des états RIA", _entree("ria_courriel", r.get("courriel", "")))
                 + _ligne("Serveur (IMAP)", _entree("ria_serveur", r.get("serveur", "")),
                          "Vide : le serveur de la boîte des avis de paiement.")
                 + _ligne("Mot de passe", _mot_de_passe("ria_mdp", coffre.BOITE_RIA),
                          "Vide si c'est la même adresse que la boîte des avis de paiement.")
                 + _ligne("Expéditeurs des états", _entree("ria_expediteurs", r.get("expediteurs", "")),
                          "Facultatif : adresses ou domaines de RIA séparés par des virgules.")
                 + _ligne("Lire les états à partir du", _entree("ria_depuis", r.get("depuis", ""), "date", 12)),
                 "Adresse où RIA envoie les états de compte (AgentBalanceReport) : l'application les lit sans les "
                 "marquer comme lus et les ajoute à « Comptabilité > États de compte RIA ».")
             + ENREGISTRER_CONFIG + "</form>")
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
            heure = ctx.req.champ("heure").strip()
            try:
                h, m = heure.split(":")
                assert 0 <= int(h) < 24 and 0 <= int(m) < 60
            except (ValueError, AssertionError):
                message = _message(erreur="Vérifiez l'heure (HH:MM).")
            else:
                def modifier(c):
                    c.setdefault("automatique", {})["heure"] = heure
                    c["automatique"].setdefault("delai_import", 3600)
                _ecrire(ctx, modifier)
                message = _message("Configuration enregistrée (réinstallez la tâche si l'heure a changé).")
    try:
        etat = planification.etat()
    except Exception as erreur:  # noqa: BLE001
        etat = str(erreur)
    a = ctx.config.get("automatique", {})
    corps = (message + _titre("Traitement automatique quotidien") + f"<form method='post'>{csrf(ctx)}"
             + _carte("1", "Tâche planifiée", _ligne(
                 "Heure du traitement", _entree("heure", a.get("heure", "01:00"), taille=8),
                 "HH:MM. Le serveur doit être allumé et la session Windows ouverte ; Sage peut être fermé.")
                 + "<span></span><div class='barre-onglet'><button name='action' value='Installer la tâche'>⏰ Installer "
                   "la tâche planifiée</button><button class='danger' name='action' value='Retirer la tâche'>Retirer la "
                   "tâche</button><a class='ouvrir' href='/admin/automatisation'>État de la tâche</a></div>")
             + f"<pre class='sortie'>{e(etat)}</pre>"
             + _carte("2", "Outils", "<p class='desc'>« Créer un raccourci sur le Bureau » et « Reprendre une "
                                     "configuration existante… » se font sur le poste, dans l'application Windows.</p>",
                      couleur="jaune")
             + ENREGISTRER_CONFIG + "</form>")
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
        if action == "Enregistrer le dossier":
            message = _refus_config(ctx)
            if not message:
                dossier_ = ctx.req.champ("dossier").strip()

                def modifier(c):
                    c.setdefault("sauvegarde", {})["dossier"] = dossier_
                _ecrire(ctx, modifier)
                cible = sv.dossier(ctx.racine, ctx.config)
                message = _message("Dossier des sauvegardes enregistré.")
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
    from datetime import datetime

    from .consultations import Section, tableau_section

    lignes = [[f"<input type='radio' name='archive' value='{e(p.name)}'>",
               datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"), e(p.name),
               f"{p.stat().st_size / 1_048_576:.1f} Mo".replace(".", ",")] for p in archives]
    etat = ("⚠ " + retard) if retard else (
        f"✔ Dernière sauvegarde : {derniere.quand[:16].replace('T', ' ') or 'aucune'} — {derniere.message}")
    corps = (message + "<p class='note'>Chaque nuit, le traitement automatique copie les données de l'application "
             "(correspondance, pointages, feuilles de temps, registres, journaux) et la configuration dans une archive "
             "vérifiée. Gardées : 14 jours, 8 semaines, 12 mois.</p>"
             + f"<form method='post' class='barre-onglet'>{csrf(ctx)}<div class='large'><label>Dossier des sauvegardes"
               f"</label><input name='dossier' value='{e(ctx.req.query.get('dossier') or str(cible))}' size='62'>"
               "</div><a class='ouvrir' href='/parcourir-sauvegarde'>📁 Choisir…</a><button class='second' "
               "name='action' value='Enregistrer le dossier'>✔ Enregistrer le dossier</button></form>"
             + f"<form method='post'>{csrf(ctx)}<div class='barre-onglet'><button name='action' value='Sauvegarder'>💾 "
               "Sauvegarder maintenant</button><button class='danger' name='action' value='Restaurer'>↩ Restaurer la "
               "sauvegarde choisie…</button><label class='case'><input type='checkbox' name='confirme' value='1'> Je "
               "remplace les données actuelles par cette sauvegarde</label><a class='ouvrir' "
               "href='/dossier-sauvegardes'>📂 Ouvrir le dossier</a></div>"
             + f"<p class='{'erreur-texte' if retard else 'ok-texte'}'>{e(etat)}</p>"
             + tableau_section(Section("Sauvegardes", ["", "Date", "Sauvegarde", "Taille"], lignes, html={0, 1, 2, 3}))
             + "</form>")
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
                if action in ("Changer le profil", "Nouveau mot de passe", "Activer / désactiver", "Supprimer le compte"):
                    nom = ctx.req.champ("compte").strip() or nom  # compte coché dans la liste
                    if reg.trouver(nom) is None:
                        raise ErreurUtilisateur("Choisissez un compte dans la liste.")
                    action = {"Changer le profil": "Profil", "Nouveau mot de passe": "Mot de passe",
                              "Supprimer le compte": "Supprimer"}.get(action, action)
                    if action == "Activer / désactiver":
                        action = "Désactiver" if reg.trouver(nom).actif else "Réactiver"
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
                    toutes = [a for g, liste in ACTIONS_FENETRES.items() if g != "Général" for a in liste]
                    refusees_ = [a for a in toutes if a not in set(ctx.req.champs("action_permise"))]
                    # section « Droits » de page_utilisateurs : Supprimer et Lancer maintenant hors de l'arbre
                    if not ctx.req.champ("supprimer_permis"):
                        refusees_.append("Supprimer")
                    if not ctx.req.champ("lancer_permis"):
                        refusees_.append("Lancer le traitement maintenant")
                    reg.definir_fonctions(profil, refusees_)
                    reg.definir_export(profil, bool(ctx.req.champ("export")))
                    reg.definir_tous_employes(profil, bool(ctx.req.champ("tous_employes")))
                    reg.definir_points_vente(profil, None if ctx.req.champ("pdv_tous") else ctx.req.champs("pdv"))
                reg.enregistrer()
            message = _message("Enregistré.")
        except ErreurUtilisateur as erreur:
            message = _message(erreur=str(erreur))
    reg = Registre(ctx.racine)
    profils = "".join(f"<option>{e(p)}</option>" for p in reg.profils)
    coche = ctx.req.champ("compte") or ctx.req.query.get("compte", "")
    lignes = [[f"<input type='radio' name='compte' value='{e(u.nom)}'{' checked' if u.nom == coche else ''}>",
               e(u.nom), e(u.profil), "Verrouillé" if u.verrouille else ("Actif" if u.actif else "Inactif"),
               e(u.derniere_connexion.replace("T", " ")[:16])] for u in reg.utilisateurs]
    classes = ["" if u.actif else "termine" for u in reg.utilisateurs]
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
                f" {e(a)}</label><br>" for a in liste) + "</div>" for g, liste in ACTIONS_FENETRES.items()
            if g != "Général")
        from ..points_vente import points_de_vente

        codes = reg.points_vente.get(choisi)
        pdv = (f"<label><input type='checkbox' name='pdv_tous' value='1'{' checked' if codes is None else ''}> Tous les "
               "points de vente</label><br>" + "".join(
                   f"<label class='retrait'><input type='checkbox' name='pdv' value='{e(x.code)}'"
                   f"{' checked' if codes is None or x.code in codes else ''}> {e(x.libelle)}</label><br>"
                   for x in points_de_vente(ctx.config)))
        droits = "".join(
            f"<label><input type='checkbox' name='{n}' value='1'{' checked' if ok else ''}> {e(lib)}</label><br>"
            for n, lib, ok in (("export", "Exporter les données (Excel, CSV, PDF, images)", choisi not in reg.sans_export),
                               ("supprimer_permis", "Supprimer des éléments", "Supprimer" not in refusees),
                               ("lancer_permis", "Lancer maintenant (importer dans Sage)",
                                "Lancer le traitement maintenant" not in refusees),
                               ("tous_employes", "Voir tous les employés", choisi not in reg.limites)))
        acces = (f"<form method='post'>{csrf(ctx)}<input type='hidden' name='profil' value='{e(choisi)}'>"
                 f"<h2>Fonctions permises au profil « {e(choisi)} »</h2><div class='tuiles'>{arbre}</div>"
                 f"<h2>Actions dans les fenêtres</h2><div class='tuiles'>{actions}</div><div class='tuiles'><div "
                 f"class='carte'><strong>Points de vente permis</strong><br>{pdv}</div><div class='carte'><strong>"
                 f"Droits</strong><br>{droits}</div></div><div "
                 "class='boutons'><button class='accent' name='action' value='Accès'>💾 Enregistrer les accès</button></div>"
                 "</form>")
    choix_profil = "".join(f"<option{' selected' if p == choisi else ''}>{e(p)}</option>" for p in reg.profils
                           if p != ADMIN)
    from .consultations import Section, tableau_section

    comptes = (f"<form method='post'>{csrf(ctx)}"
               + tableau_section(Section("Comptes", ["", "Nom", "Profil", "État", "Dernière connexion"], lignes,
                                         classes=classes, html=set(range(5))))
               + "<div class='carte'><div class='ligne'><div><label>Nom</label><input name='nom' size='22'></div><div>"
                 f"<label>Profil</label><select name='profil'>{profils}</select></div><div><label>Mot de passe (6 "
                 "caractères min.)</label><input type='password' name='mot_de_passe' autocomplete='new-password' "
                 "size='20'></div></div><div class='barre-onglet'><button name='action' value='Ajouter'>➕ Ajouter"
                 "</button><button class='second' name='action' value='Changer le profil'>Changer le profil</button>"
                 "<button class='second' name='action' value='Nouveau mot de passe'>Nouveau mot de passe</button>"
                 "<button class='second' name='action' value='Activer / désactiver'>Activer / désactiver</button>"
                 "<button class='danger' name='action' value='Supprimer le compte'>🗑 Supprimer</button></div>"
                 "<p class='note'>Cochez un compte, puis choisissez son profil ou tapez son mot de passe. Un compte "
                 "verrouillé (3 mots de passe faux) se rouvre en lui donnant un nouveau mot de passe. Il reste toujours "
                 "au moins un administrateur actif.</p></div></form>")
    profils_carte = (f"<div class='carte'><h2>Profils et fonctions permises</h2><form class='barre-onglet' "
                     f"method='get'><div><label>Profil</label><select name='profil'>{choix_profil}</select></div>"
                     "<button class='second'>Afficher</button></form>"
                     f"<form method='post' class='barre-onglet'>{csrf(ctx)}<div><label>Nouveau profil</label><input "
                     "name='profil_nouveau' size='16'></div><button class='second' name='action' value='Nouveau "
                     "profil'>➕</button></form><p class='note'>Cliquez pour cocher ou décocher les fonctions de chaque "
                     f"rubrique.</p>{acces}</div>")
    corps = message + f"<div class='colonnes'><div>{comptes}</div><div>{profils_carte}</div></div>"
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
