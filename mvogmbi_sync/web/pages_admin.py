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
            f"{'••••••••' if present else ''}'>")


def _sortie_test(ctx: Contexte, cle: str) -> str:
    """Zone de sortie (Application._sortie) : résultat du dernier test lancé de cette page."""
    texte = ctx.app.memoire.get(("test_admin", cle), "")
    return f"<pre class='sortie'>{e(texte)}</pre>" if texte else ""


ENREGISTRER_CONFIG = ("<div class='barre-onglet barre-config'><button class='a-droite' name='action' value='Enregistrer'>💾 "
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
                   "</div>" + _zone_sortie(ctx, "clover"))
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
    from ..depots import sans_clover
    from ..rapprochement import compte_banque

    message = ""
    if ctx.req.methode == "POST" and ctx.req.champ("action") in ("Ajouter le compte bancaire",
                                                                  "Retirer le compte bancaire"):
        message = _comptes_bancaires_action(ctx)
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
                        if ctx.req.champ("banque_depot") in FORMATS_RELEVES:  # banque du compte de dépôt
                            c.setdefault("rapprochement", {})["banque_depot"] = ctx.req.champ("banque_depot")
                        if ctx.req.champ("compte_bnc").strip():  # compte de la Banque Nationale
                            c.setdefault("rapprochement", {})["compte_bnc"] = ctx.req.champ("compte_bnc").strip()
                        if "depots" in ctx.req.form:  # dépôts sans Clover
                            c.setdefault("sage", {})["depots_sans_clover"] = "; ".join(
                                x.strip() for x in ctx.req.champ("depots").split(";") if x.strip())
                    _ecrire(ctx, modifier)
                    _garder_secrets(ctx, [("lecture", coffre.SAGE_LECTURE), ("import", coffre.SAGE_IMPORT)])
                    message = _message("Configuration Sage 50 enregistrée.")
                except ValueError as erreur:
                    message = _message(erreur=f"Vérifiez les dates : {erreur}")
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
                 + _ligne("Premier jour à importer", _entree("date_depart", a.get("date_depart") or date.today().isoformat(), "date", 12),
                          "Utilisé seulement si Sage ne contient encore aucune facture de vente de Clover.")
                 + _ligne("Compte de dépôt des encaissements", _entree("compte", en.get("compte_depot", "1055"),
                                                                        taille=10),
                          "Compte de banque Sage où Clover dépose les ventes par carte (ex. 1055).")
                 + _ligne("Banque du compte de dépôt", _choix_banque(ctx),
                          "Banque ou caisse du compte où Clover dépose les ventes (toutes les banques du Canada) : ses "
                          "relevés servent aux encaissements et au rapprochement.")
                 + _ligne("Encaisser à partir des ventes du", _entree("enc_depart", en.get("date_depart") or date.today().isoformat(), "date",
                                                                       12),
                          "Les dépôts des ventes antérieures ne sont jamais encaissés.")
                 + _ligne("Compte Sage du compte BNC", _entree("compte_bnc", compte_banque(ctx.config, "bnc"), taille=10),
                          "Compte de banque Sage du compte de la Banque Nationale (rapprochement des relevés BNC).")
                 + _ligne("Dépôts sans Clover", _entree("depots", "; ".join(sans_clover(ctx.config)), taille=40),
                          "Emplacements Sage sans caisse Clover (entrepôt, réserve), séparés par « ; ». Les dépôts des points de vente viennent de la carte « Points de vente » (page Clover)."))
             + _carte("2", "Utilisateurs Sage", _ligne(
                 "Utilisateur Sage (lecture)", _entree("utilisateur", b.get("utilisateur") or "mvogmbi_sync"),
                 "Utilisateur avec « Droits d'accès aux produits tiers : Consultation seule » et accès Vue aux "
                 "modules Stocks & Services et Clients & Ventes.")
                 + _ligne("Mot de passe (lecture)", _mot_de_passe("lecture", coffre.SAGE_LECTURE))
                 + _ligne("Mot de passe Sage pour l'import", _mot_de_passe("import", coffre.SAGE_IMPORT),
                          "Mot de passe demandé par la fenêtre « Sage 50 - Password » de l'import (utilisateur "
                          "sysadmin).")
                 + "<span></span><div><button name='action' value='Tester'>📒 Tester l'accès à Sage</button></div>"
                 + _zone_sortie(ctx, "sage"))
             + _carte("3", "Paie", _ligne(
                 "Première paie de l'année", _entree("premiere", premiere.isoformat() if premiere else "", "date", 12),
                 "Date de la première paie de l'année : les paies suivantes (tous les 14 jours) et leurs périodes se "
                 "calculent (« Paie > Calendrier de paie »).")
                 + _ligne("Jours entre la fin de la période et la paie", _entree("delai", cal.delai, taille=5)))
             + ENREGISTRER_CONFIG + "</form>" + _carte_comptes_bancaires(ctx))
    return Reponse(corps=page(ctx, "Sage 50", corps))


from ..banques_canada import NOMS as FORMATS_RELEVES  # noqa: E402  (toutes les banques et caisses du Canada)


def _choix_banque(ctx: Contexte) -> str:
    from ..rapprochement import compte_bancaire

    actuelle = compte_bancaire(ctx.config).format
    return "<select name='banque_depot'>" + "".join(
        f"<option value='{k}'{' selected' if k == actuelle else ''}>{e(v)}</option>"
        for k, v in FORMATS_RELEVES.items()) + "</select>"


def _carte_comptes_bancaires(ctx: Contexte) -> str:
    """Comptes bancaires du rapprochement (demande du propriétaire du 2026-11-05 : « ajouter la possibilité
    d'ajouter un compte bancaire ») : Desjardins et BNC d'office, comptes ajoutés retirables."""
    from ..rapprochement import comptes_bancaires

    ajoutes = {str(c.get("code")) for c in ctx.config.get("comptes_bancaires", []) or []}
    lignes = "".join(
        f"<tr><td>{e(c.nom)}</td><td>{e(FORMATS_RELEVES.get(c.format, c.format))}</td><td>{e(c.compte_sage)}</td>"
        f"<td>{e(c.numero or '—')}</td><td>{e(c.code)}</td><td>"
        + (f"<form method='post'>{csrf(ctx)}<input type='hidden' name='code' value='{e(c.code)}'><button "
           "class='danger' name='action' value='Retirer le compte bancaire'>🗑 Retirer</button></form>"
           if c.code in ajoutes else "<span class='note'>d'office</span>") + "</td></tr>"
        for c in comptes_bancaires(ctx.config))
    formats = "".join(f"<option value='{k}'>{e(v)}</option>" for k, v in FORMATS_RELEVES.items())
    contenu = ("<div class='defile'><table><thead><tr><th>Compte</th><th>Banque (relevé)</th><th>Compte Sage</th>"
               f"<th>N° à la banque</th><th>Dossier</th><th></th></tr></thead><tbody>{lignes}</tbody></table></div>"
               f"<form method='post' class='ligne'>{csrf(ctx)}"
               "<div><label>Nom</label><input name='nom' size='22' required placeholder='ex. BNC épargne'></div>"
               f"<div><label>Banque</label><select name='format'>{formats}</select></div>"
               "<div><label>Compte Sage</label><input name='compte_sage' size='8' required inputmode='numeric'></div>"
               "<div><label>N° à la banque</label><input name='numero' size='16' placeholder='facultatif'></div>"
               "<button name='action' value='Ajouter le compte bancaire'>➕ Ajouter le compte bancaire</button></form>")
    return _carte("4", "Comptes bancaires (rapprochement)", contenu,
                  "Chaque compte a ses relevés (Comptabilité > Rapprochement) et son compte de banque dans Sage. Un "
                  "relevé chargé (PDF, OFX / QFX ou CSV, toutes les banques du Canada) va d'office dans le bon compte : "
                  "le n° du compte à la banque, puis la banque reconnue d'après le relevé.")


def _comptes_bancaires_action(ctx: Contexte) -> str:
    from ..rapprochement import comptes_bancaires

    if ctx.req.champ("action") == "Retirer le compte bancaire":  # page Sage 50 : réservée par les droits du profil
        code = ctx.req.champ("code")

        def retirer(c):
            c["comptes_bancaires"] = [x for x in c.get("comptes_bancaires", []) or [] if str(x.get("code")) != code]
        _ecrire(ctx, retirer)
        return _message(f"Compte bancaire « {code} » retiré (ses relevés restent dans donnees/releves_{code}).")
    nom, compte = ctx.req.champ("nom").strip(), ctx.req.champ("compte_sage").strip()
    fmt = ctx.req.champ("format") if ctx.req.champ("format") in FORMATS_RELEVES else "autre"
    if not nom or not compte.isdigit():
        return _message(erreur="Donnez un nom et un n° de compte Sage (chiffres).")
    existants = {c.code for c in comptes_bancaires(ctx.config)}
    base = "".join(x for x in nom.lower() if x.isalnum())[:16] or "compte"
    code, n = base, 2
    while code in existants:
        code, n = f"{base}{n}", n + 1
    if compte in {c.compte_sage for c in comptes_bancaires(ctx.config)}:
        return _message(erreur=f"Le compte Sage {compte} est déjà celui d'un autre compte bancaire.")

    def ajouter(c):
        c.setdefault("comptes_bancaires", []).append({"code": code, "nom": nom, "format": fmt, "compte_sage": compte,
                                                      "numero": ctx.req.champ("numero").strip(), "actif": True})
    _ecrire(ctx, ajouter)
    return _message(f"Compte bancaire « {nom} » ajouté (compte Sage {compte}).")


# --------------------------------------------------------------------------------------------- Courriel
def courriel(ctx: Contexte) -> Reponse:
    from .. import coffre
    from ..courriel import adresses, adresses_invalides
    from . import taches

    message = ""
    if ctx.req.methode == "POST":
        if ctx.req.champ("action") == "Tester":  # Application.tester_courriel
            def tester():
                from ..courriel import envoyer

                envoyer(ctx.config, "MVOGMBI_Sync : courriel de test",
                        "Ce courriel confirme que les alertes de MVOGMBI_Sync sont bien configurées.")
                return "courriel envoyé"

            _tester(ctx, "courriel", "Courriel de test", tester)
            return Reponse(corps=page(ctx, "Courriel", _page_courriel(ctx, "")))
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
                message = _message(erreur="Vérifiez le port et les dates.")
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
    return Reponse(corps=page(ctx, "Courriel", _page_courriel(ctx, message)))


def _page_courriel(ctx: Contexte, message: str) -> str:
    from .. import coffre

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
                      + _ligne("Autres destinataires", _entree("copie", c.get("copie")),
                               "Facultatif : autres personnes à informer, adresses séparées par des virgules (ex. "
                               "comptable@exemple.com, gerant@exemple.com).")
                      + case("si_succes", c.get("envoyer_si_succes", True), "Envoyer le compte rendu après chaque "
                             "traitement, y compris en cas de succès (dates traitées et leur état)")
                      + "<span></span><div><button name='action' value='Tester'>✉ Envoyer un courriel de test</button>"
                        "</div>" + _zone_sortie(ctx, "courriel")
                      + _ligne("Copie cachée (Cci)", _entree("cci", c.get("cci")),
                               "Reçoit en copie cachée chaque courriel envoyé par l'application (bulletins, T4 / RL-1, "
                               "relances), sauf les comptes rendus du traitement automatique. Vide : le premier "
                               "destinataire ci-dessus."))
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
                 "marquer comme lus et les ajoute à « RIA > États de compte RIA ».")
             + ENREGISTRER_CONFIG + "</form>")
    return corps


# --------------------------------------------------------------------------------------------- Automatisation
def automatisation(ctx: Contexte) -> Reponse:
    from .. import planification
    from . import taches

    message = ""
    if ctx.req.query.get("fichier") == "client":  # serveur.json à copier à côté de MVOGMBI_Sync_Client.exe
        from .. import serveur_appli

        return Reponse(corps=serveur_appli.fichier_client(ctx.config), type="application/json",
                       entetes={"Content-Disposition": "attachment; filename=\"serveur.json\""})
    if ctx.req.methode == "POST" and ctx.req.champ("action") == "État":
        _tester(ctx, "auto", "État de la tâche", planification.etat)
    elif ctx.req.methode == "POST" and ctx.req.champ("action") == "Raccourci":
        return _raccourci(ctx)
    elif ctx.req.methode == "POST":
        action = ctx.req.champ("action")
        message = _refus_config(ctx)
        if not message and action in ("Installer la tâche", "Retirer la tâche"):
            if action == "Retirer la tâche" and not ctx.req.champ("confirme"):
                message = _message(erreur="Retirer la tâche planifiée ? Les ventes ne seront plus importées "
                                          "automatiquement : cochez « Je confirme » puis « Retirer la tâche ».")
            else:
                heure = ctx.config.get("automatique", {}).get("heure", "01:00")
                _tester(ctx, "auto", "Retrait de la tâche" if action == "Retirer la tâche" else
                        "Installation de la tâche", planification.retirer if action == "Retirer la tâche" else
                        (lambda: planification.installer(ctx.racine, heure)))
        elif not message and action == "Reprendre":
            message = _reprendre(ctx, ctx.req.champ("dossier").strip())
        elif not message:
            heure = ctx.req.champ("heure").strip()
            try:
                h, m = heure.split(":")
                assert 0 <= int(h) < 24 and 0 <= int(m) < 60
            except (ValueError, AssertionError):
                message = _message(erreur="Vérifiez l'heure (HH:MM).")
            else:
                from .. import serveur_appli

                valeurs = {k: ctx.req.champ(f"s_{k}") for k in ("machine", "adresse", "adresse_locale", "nom_public",
                                                                "port", "certificat", "cle")}

                from .. import pointage_wifi

                def modifier(c):
                    c.setdefault("automatique", {})["heure"] = heure
                    c["automatique"].setdefault("delai_import", 3600)
                    if any(valeurs.values()):
                        serveur_appli.ecrire(c, valeurs)
                    if ctx.req.champ("p_present"):
                        pointage_wifi.ecrire(c, ctx.req.champ("p_wifi"), ctx.req.champ("p_adresses"),
                                             ctx.req.champ("p_postes"), ctx.req.champ("p_minutes") or 0)
                try:
                    _ecrire(ctx, modifier)
                    serveur_appli.copier_pour_client(ctx.racine, ctx.config)
                    message = _message("Configuration enregistrée (réinstallez la tâche si l'heure a changé ; "
                                       "redémarrez le serveur web si son adresse ou son port a changé).")
                except ValueError as erreur:
                    message = _message(erreur=str(erreur))
    a = ctx.config.get("automatique", {})
    corps = (message + _titre("Traitement automatique quotidien") + f"<form method='post'>{csrf(ctx)}"
             + _carte("1", "Tâche planifiée", _ligne(
                 "Heure du traitement", _entree("heure", a.get("heure", "01:00"), taille=8),
                 "HH:MM. Le serveur doit être allumé et la session Windows ouverte ; Sage peut être fermé.")
                 + "<span></span><div class='barre-onglet'><button name='action' value='Installer la tâche'>⏰ Installer "
                   "la tâche planifiée</button><button class='danger' name='action' value='Retirer la tâche'>Retirer la "
                   "tâche</button><button class='second' name='action' value='État'>État de la tâche</button><label "
                   "class='case'><input type='checkbox' name='confirme' value='1'> Je confirme le retrait</label></div>"
                 + _zone_sortie(ctx, "auto"))
             + _carte_serveur(ctx) + _carte_wifi(ctx)
             + _carte("2", "Outils", "<div class='barre-onglet'><button class='second' name='action' value='Raccourci'>"
                                     "Créer un raccourci sur le Bureau</button><a class='ouvrir' href='/parcourir-config'>"
                                     "Reprendre une configuration existante…</a></div><p class='desc'>Copie config.toml, "
                                     "la correspondance des articles et les articles à relier depuis un autre dossier "
                                     "(ex. le dossier du projet). Les mots de passe restent dans le coffre-fort.</p>"
                      + (f"<input type='hidden' name='dossier' value='{e(ctx.req.query['dossier'])}'><p>Dossier choisi "
                         f"sur le serveur : <strong>{e(ctx.req.query['dossier'])}</strong> <button name='action' "
                         "value='Reprendre'>✔ Reprendre cette configuration</button></p>"
                         if ctx.req.query.get("dossier") else ""),
                      couleur="jaune")
             + ENREGISTRER_CONFIG + "</form>")
    return Reponse(corps=page(ctx, "Automatisation", corps))


def _carte_wifi(ctx: Contexte) -> str:
    """Carte « Wi-Fi du magasin (pointage) » : nom du Wi-Fi, adresses publiques du magasin, postes du magasin ;
    l'adresse du réseau de l'appareil qui affiche la page aide à remplir les adresses depuis le magasin."""
    from .. import pointage_wifi

    r = pointage_wifi.reglages(ctx.config)
    reseau = pointage_wifi.adresse_du_reseau(ctx.req.adresse) if ctx.req.adresse.startswith("100.") else ""
    ici = (f"Réseau de cet appareil : <strong>{e(reseau)}</strong> (ouvrez cette page depuis le magasin, sur son "
           "Wi-Fi, et copiez cette adresse ci-dessus)." if reseau else
           "Ouvrez cette page depuis le magasin, sur son Wi-Fi, pour voir l'adresse à inscrire.")
    return _carte("4", "Wi-Fi du magasin (pointage)", "<input type='hidden' name='p_present' value='1'>" + _ligne(
        "Nom du Wi-Fi du magasin", _entree("p_wifi", r["wifi"]),
        "Affiché aux employés qui essaient de pointer ailleurs.")
        + _ligne("Adresses du Wi-Fi du magasin", _entree("p_adresses", ", ".join(r["adresses_magasin"])),
                 "Adresse publique de la connexion Internet du magasin (ou début d'adresse terminé par un point), "
                 "séparées par des virgules. Vide : pas de contrôle du Wi-Fi.")
        + _ligne("Postes du magasin", _entree("p_postes", ", ".join(r["postes"])),
                 "Adresses Tailscale des postes fixes du magasin, toujours permis (ex. 100.101.7.12).")
        + _ligne("Pause hors du Wi-Fi après (minutes)", _entree("p_minutes", r["pause_minutes"], taille=6),
                 "Employé qui a pointé depuis son téléphone : en pause après ce nombre de minutes de suite hors du "
                 "Wi-Fi du magasin, reprise à son retour. 0 = jamais.")
        + f"<span></span><div class='aide'>{ici}</div>",
        "Les employés pointent seulement depuis le Wi-Fi du magasin : l'application lit dans Tailscale le réseau d'où "
        "vient le téléphone ou le poste.")


def _carte_serveur(ctx: Contexte) -> str:
    """Carte « Serveur de l'application » (Application._onglet_automatisation, carte 3)."""
    from .. import serveur_appli

    r = serveur_appli.lire(ctx.config)
    return _carte("3", "Serveur de l'application", _ligne(
        "Nom de l'ordinateur", _entree("s_machine", r["machine"]),
        "Ordinateur qui a Sage 50 et MVOGMBI_Sync (serveur web, traitement de nuit).")
        + _ligne("Adresse Tailscale", _entree("s_adresse", r["adresse"]),
                 "Adresse 100.x.y.z du serveur dans Tailscale (accès depuis le magasin, le bureau et les téléphones).")
        + _ligne("Adresse locale", _entree("s_adresse_locale", r["adresse_locale"]),
                 "Adresse sur le réseau du bureau (ex. 192.168.2.62) : Bureau à distance.")
        + _ligne("Nom tapé dans le client", _entree("s_nom_public", r["nom_public"]),
                 "Ce que les employés tapent dans MVOGMBI_Sync_Client (ex. marchemvogmbi.com).")
        + _ligne("Port du serveur web", _entree("s_port", r["port"], taille=8),
                 "8765 sans HTTPS ; 443 avec HTTPS (adresse sans port : https://app.marchemvogmbi.com).")
        + _ligne("Certificat HTTPS (.pem)", _entree("s_certificat", r["certificat"]),
                 "Fichier du certificat Let's Encrypt (certificat_https.ps1 : …-chain.pem). Vide : pas de HTTPS. "
                 "Redémarrez le serveur web après un changement ; un certificat renouvelé est relu tout seul.")
        + _ligne("Clé du certificat (.pem)", _entree("s_cle", r["cle"]), "Fichier …-key.pem.")
        + "<span></span><div><a class='ouvrir' href='/admin/automatisation?fichier=client'>⬇ Fichier du client "
          "(serveur.json)</a><div class='aide'>À copier à côté de MVOGMBI_Sync_Client.exe sur chaque poste : le client "
          "envoie alors vers ce serveur. Les postes installés avec MVOGMBI_Sync le reçoivent d'office.</div></div>",
        "Où l'application est déployée : changez ces réglages pour l'installer sur un autre serveur.")


def _raccourci(ctx: Contexte) -> Reponse:
    """« Créer un raccourci sur le Bureau » : raccourci Internet (.url) vers l'application web, à enregistrer sur le
    Bureau du poste (le navigateur ne peut pas écrire sur le Bureau lui-même)."""
    web = ctx.config.get("web", {})
    protocole = "https" if web.get("certificat") else "http"
    adresse = f"{protocole}://{web.get('adresse', '127.0.0.1')}:{web.get('port', 8765)}/"
    contenu = f"[InternetShortcut]\r\nURL={adresse}\r\nIconIndex=0\r\n"
    return Reponse(corps=contenu.encode("utf-8"), type="application/octet-stream",
                   entetes={"Content-Disposition": "attachment; filename=\"MVOGMBI_Sync.url\""})


def _reprendre(ctx: Contexte, dossier: str) -> str:
    """Application.reprendre : config.toml (secrets encore en clair passés au coffre-fort) et fichiers de données."""
    import shutil

    from .. import coffre
    from ..interface import ecrire_config, lire_config

    if dossier.replace("/", "\\").startswith("\\\\"):  # partage réseau refusé (analyse de sécurité du 2026-11-13)
        return _message(erreur="Choisissez un dossier de ce serveur (pas un partage réseau).")
    source = Path(dossier)
    if not dossier or not source.is_dir():
        return _message(erreur="Choisissez le dossier qui contient config.toml (et le sous-dossier donnees).")
    copies = []
    if (source / "config.toml").exists():
        ancienne = lire_config(source / "config.toml")
        jeton = ancienne.get("clover", {}).pop("api_token", "")
        mdp = ancienne.get("sage_base", {}).pop("mot_de_passe", "")
        if jeton and not coffre.present(coffre.CLOVER_JETON):
            coffre.ecrire(coffre.CLOVER_JETON, jeton)
        if mdp and not coffre.present(coffre.SAGE_LECTURE):
            coffre.ecrire(coffre.SAGE_LECTURE, mdp)
        with ctx.app.ecriture:
            ecrire_config(ctx.racine / "config.toml", ancienne)
            ctx.app.config.clear()
            ctx.app.config.update(ancienne)
        copies.append("config.toml")
    for nom in ("correspondance_articles.xlsx", "articles_a_relier.csv", "journal_imports.csv", "articles_sage.csv"):
        if (source / "donnees" / nom).exists():
            (ctx.racine / "donnees").mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / "donnees" / nom, ctx.racine / "donnees" / nom)
            copies.append(nom)
    if not copies:
        return _message(erreur="Aucun fichier de configuration dans ce dossier.")
    return _message("Repris : " + ", ".join(copies) + ".")


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
                if action in ("Changer le profil", "Nouveau mot de passe", "Activer / désactiver", "Supprimer le compte",
                              "Mot de passe web", "Effacer le mot de passe web"):
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
                elif action == "Mot de passe web":
                    reg.definir_mot_de_passe_web(nom, ctx.req.champ("mot_de_passe_web"))
                    ctx.app.sessions.fermer_compte(nom)
                    fait = f"Mot de passe web de « {nom} » enregistré."
                elif action == "Effacer le mot de passe web":
                    reg.effacer_mot_de_passe_web(nom)
                    ctx.app.sessions.fermer_compte(nom)
                    fait = f"Mot de passe web de « {nom} » effacé : il sera créé à sa prochaine connexion web."
                elif action in ("Désactiver", "Réactiver"):
                    reg.activer(nom, action == "Réactiver", ctx.u.nom)
                    if action == "Désactiver":
                        ctx.app.sessions.fermer_compte(nom)
                    fait = f"Compte « {nom} » {'activé' if action == 'Réactiver' else 'désactivé'}."
                elif action == "Supprimer":
                    if not action_permise(ctx, "Supprimer"):
                        raise ErreurUtilisateur("Votre profil n'a pas le droit « Supprimer ».")
                    reg.supprimer(nom)
                    ctx.app.sessions.fermer_compte(nom)
                elif action == "Nouveau profil":
                    reg.definir_profil(ctx.req.champ("profil_nouveau"), ["accueil"])
                elif action == "Supprimer le profil":
                    if not action_permise(ctx, "Supprimer"):
                        raise ErreurUtilisateur("Votre profil n'a pas le droit « Supprimer ».")
                    reg.supprimer_profil(ctx.req.champ("profil"))
                elif action == "Accès":
                    profil = ctx.req.champ("profil")
                    fonctions = _avec_rubriques(ctx, ctx.req.champs("fonction"), "rubrique", "fonction")
                    action_permises = _avec_rubriques(ctx, ctx.req.champs("action_permise"), "rubrique",
                                                      "action_permise")
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
                    refusees_ = [a for a in toutes if a not in set(action_permises)]
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
            message = _message(locals().get("fait") or "Enregistré.")
        except ErreurUtilisateur as erreur:
            message = _message(erreur=str(erreur))
    reg = Registre(ctx.racine)
    return Reponse(corps=page(ctx, "Utilisateurs", message + _page_utilisateurs(ctx, reg)))


def _avec_rubriques(ctx: Contexte, cochees: list[str], champ_rubrique: str, champ: str) -> list[str]:
    """Rubrique de l'arbre cochée ou décochée depuis l'affichage : toutes ses fonctions suivent (comme un clic sur la
    rubrique dans Windows) ; sinon les cases une à une."""
    resultat = list(cochees)
    maintenant = set(ctx.req.champs(champ_rubrique))
    for valeur in ctx.req.champs("rubrique_avant"):
        nom, _, avant = valeur.rpartition("=")
        enfants = [x for x in ctx.req.champs(f"enfants:{nom}") if x]
        if not enfants or (champ == "action_permise") != (nom == "actions"):
            continue
        if nom in maintenant and avant == "0":
            resultat += [x for x in enfants if x not in resultat]
        elif nom not in maintenant and avant == "1":
            resultat = [x for x in resultat if x not in enfants]
    return resultat


def entete_page(icone: str, titre: str, sous_titre: str = "") -> str:
    """design.entete_page : icône, titre vert souligné jaune / rouge et « — sous-titre » gris sur la même ligne."""
    return (f"<div class='entete-page'><span class='ic'>{icone}</span><div><div class='t'>{e(titre)}</div><div "
            "class='souligne'><span class='j'></span><span class='r'></span></div></div>"
            + (f"<span class='st'>— {e(sous_titre)}</span>" if sous_titre else "") + "</div>")


def _page_utilisateurs(ctx: Contexte, reg) -> str:
    """page_utilisateurs.PageUtilisateurs : « Comptes » à gauche (tableau, puis Nom / Profil / Mot de passe et leurs
    boutons), « Profils et fonctions permises » à droite (profil, ➕, 🗑, arbre du menu, points de vente, droits,
    « Enregistrer les accès »)."""
    from ..interface import ACCUEIL, LIBELLES_MENU, MENU_GROUPES
    from ..points_vente import points_de_vente
    from ..utilisateurs import ACTIONS_FENETRES, ADMIN, LONGUEUR_MIN, PAGES
    from .consultations import Section, tableau_section

    coche = ctx.req.champ("compte") or ctx.req.query.get("compte", "")
    lignes = [[f"<input type='radio' name='compte' value='{e(u.nom)}'{' checked' if u.nom == coche else ''}>",
               e(u.nom), e(u.profil), "Verrouillé" if u.verrouille else ("Actif" if u.actif else "Inactif"),
               "Défini" if u.empreinte_web else "À créer (1re connexion)",
               e(u.derniere_connexion.replace("T", " ")[:16])] for u in reg.utilisateurs]
    classes = ["" if u.actif else "termine" for u in reg.utilisateurs]
    profils = "".join(f"<option>{e(p)}</option>" for p in reg.profils)
    comptes = (f"<form method='post' class='colonne-comptes'>{csrf(ctx)}<div class='barre-onglet'><strong "
               "class='titre-carte'>Comptes</strong></div>"
               + tableau_section(Section("Comptes", ["", "Nom", "Profil", "État", "Mot de passe web",
                                                     "Dernière connexion"], lignes, classes=classes,
                                         html=set(range(6))))
               + "<div class='fiche-compte'><div class='grille-compte'><label>Nom</label><label>Profil</label><label>"
                 f"Mot de passe ({LONGUEUR_MIN} caractères min.)</label><input name='nom' size='22'><select "
                 f"name='profil'>{profils}</select><input type='password' name='mot_de_passe' "
                 "autocomplete='new-password' size='20'></div><div class='grille-compte'><label>Mot de passe web "
                 "(12 caractères, minuscule, majuscule, chiffre, caractère spécial)</label><span></span><span></span>"
                 "<input type='password' name='mot_de_passe_web' autocomplete='new-password' size='20'></div>"
                 "<div class='barre-onglet'><button name='action' "
                 "value='Ajouter'>➕ Ajouter</button><button class='second' name='action' value='Changer le profil'>"
                 "Changer le profil</button><button class='second' name='action' value='Nouveau mot de passe'>Nouveau "
                 "mot de passe</button><button class='second' name='action' value='Activer / désactiver'>Activer / "
                 "désactiver</button><button class='second' name='action' value='Mot de passe web'>Mot de passe web"
                 "</button><button class='second' name='action' value='Effacer le mot de passe web'>Effacer le mot de "
                 "passe web</button><button class='danger' name='action' value='Supprimer le compte'>🗑 Supprimer"
                 "</button></div></div></form>")
    choisi = ctx.req.query.get("profil") or ctx.req.champ("profil")
    if choisi not in reg.profils:
        choisi = ADMIN if ADMIN in reg.profils else next(iter(reg.profils), "")
    admin = choisi == ADMIN
    permises = reg.fonctions_permises.get(choisi)
    pages_profil = set(reg.profils.get(choisi, []))
    refusees = set(reg.fonctions_refusees.get(choisi, []))
    inactif = " disabled" if admin else ""

    def case(nom: str, valeur: str, coche_: bool, libelle: str, classe: str = "") -> str:
        return (f"<label class='noeud {classe}'><input type='checkbox' name='{nom}' value='{e(valeur)}'"
                f"{' checked' if coche_ or admin else ''}{inactif}> {e(libelle)}</label>")

    arbre = ""
    vus = set()
    for nom_groupe, icone, elements in MENU_GROUPES:
        noeuds, enfants = "", []
        for el in elements:
            if isinstance(el, int):
                if el >= len(PAGES):
                    continue  # page Utilisateurs : administrateurs seulement
                from .menu import PAGES_MENU

                cle = PAGES[el]
                libelle = LIBELLES_MENU.get(el) or (PAGES_MENU[el][1] if el in PAGES_MENU else cle)
                page_el = el
            else:
                if el[1] in vus:
                    continue
                cle, libelle, page_el = el[1], f"{el[0]}  {el[1]}", el[2]
            vus.add(cle)
            if permises is not None:
                ok = cle in permises
            else:
                ok = (PAGES[page_el] if page_el < len(PAGES) else "") in pages_profil and cle not in refusees
            ok = ok or (isinstance(el, int) and el == ACCUEIL)
            enfants.append((cle, ok))
            noeuds += case("fonction", cle, ok, libelle, "enfant" if nom_groupe else "")
        if nom_groupe:
            tous = all(ok for _c, ok in enfants)
            arbre += (case("rubrique", nom_groupe, tous, f"{icone}  {nom_groupe}", "rubrique")
                      + f"<input type='hidden' name='rubrique_avant' value='{e(nom_groupe)}={int(tous)}'>"
                      + "".join(f"<input type='hidden' name='enfants:{e(nom_groupe)}' value='{e(c)}'>"
                                for c, _ok in enfants))
        arbre += noeuds
    actions = [(a, g) for g, liste in ACTIONS_FENETRES.items() if g != "Général" for a in liste]
    tous = all(a not in refusees for a, _g in actions)
    arbre += (case("rubrique", "actions", tous, "🔒  Actions dans les fenêtres", "rubrique")
              + f"<input type='hidden' name='rubrique_avant' value='actions={int(tous)}'>"
              + "".join(f"<input type='hidden' name='enfants:actions' value='{e(a)}'>" for a, _g in actions)
              + "".join(case("action_permise", a, a not in refusees, f"{a}  ({g})", "enfant") for a, g in actions))
    codes = reg.points_vente.get(choisi)
    pdv = (case("pdv_tous", "1", codes is None, "Tous les points de vente")
           + "".join(case("pdv", x.code, codes is None or x.code in codes, x.libelle, "enfant")
                     for x in points_de_vente(ctx.config)))
    droits = "".join(case(n, "1", ok, lib) for n, lib, ok in (
        ("export", "Exporter les données (Excel, CSV, PDF, images)", choisi not in reg.sans_export),
        ("supprimer_permis", "Supprimer des éléments", "Supprimer" not in refusees),
        ("lancer_permis", "Lancer maintenant (importer dans Sage)", "Lancer le traitement maintenant" not in refusees),
        ("tous_employes", "Voir tous les employés", choisi not in reg.limites)))
    note = ("L'administrateur voit toutes les pages et gère les utilisateurs." if admin else
            f"{sum(1 for u in reg.utilisateurs if u.profil == choisi)} compte(s) avec ce profil ; les changements "
            "s'appliquent à leur prochaine connexion.")
    choix_profil = "".join(f"<option{' selected' if p == choisi else ''}>{e(p)}</option>" for p in reg.profils)
    profils_carte = (
        "<div class='carte carte-profils'><strong class='titre-carte'>Profils et fonctions permises</strong>"
        "<div class='ligne-profil'>"
        f"<form method='get'><select name='profil'>{choix_profil}</select><button class='second bouton-mini' "
        "title='Afficher ce profil'>↻</button></form>"
        f"<form method='post'>{csrf(ctx)}<input type='hidden' name='profil' value='{e(choisi)}'>"
        "<details class='nouveau-profil'><summary class='bouton-mini plein'>➕</summary><div><input name='profil_nouveau' "
        "size='16' placeholder='Nom du profil'><button name='action' value='Nouveau profil'>OK</button></div></details>"
        "<button class='danger bouton-mini' name='action' value='Supprimer le profil'>🗑</button></form></div>"
        "<p class='note'>Cliquez pour cocher ou décocher ; une rubrique coche toutes ses fonctions.</p>"
        f"<form method='post'>{csrf(ctx)}<input type='hidden' name='profil' value='{e(choisi)}'>"
        f"<div class='arbre-acces'>{arbre}</div>"
        f"<div class='titre-section'>Points de vente permis</div>{pdv}"
        f"<div class='titre-section'>Droits</div>{droits}"
        f"<p class='note'>{e(note)}</p>"
        + ("" if admin else "<button class='accent' name='action' value='Accès'>💾 Enregistrer les accès</button>")
        + "</form></div>")
    return (entete_page("👥", "Utilisateurs et accès", "comptes, profils et fonctions permises à chaque profil")
            + f"<div class='page-utilisateurs'><div>{comptes}</div>{profils_carte}</div>")


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
