"""Application web : connexion, droits par profil, sécurité des formulaires, pointage, feuilles de temps."""

import http.cookiejar
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from mvogmbi_sync import paie_temps as pt
from mvogmbi_sync import planning as pl
from mvogmbi_sync.utilisateurs import Registre
from mvogmbi_sync.web import serveur


class SansRedirection(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


@pytest.fixture
def site(tmp_path):
    Registre._blocages.clear()  # un autre test bloque « Patron » (dernier administrateur) pour 15 min
    (tmp_path / "config.toml").write_text("[web]\npostes_pointage = ['127.0.0.1']\n", encoding="utf-8")
    reg = Registre(tmp_path)
    reg.ajouter("Patron", "Administrateur", "secret123")
    reg.ajouter("Awa", "Employé", "secret456")
    reg.enregistrer()
    registre = pt.Registre(tmp_path)
    awa = registre.ajouter("Awa Mballa")
    awa.compte = "Awa"
    registre.definir_nip(awa.id, "1234")
    registre.enregistrer()
    planning = pl.Planning(tmp_path)
    planning.definir(awa.id, [date.today()], pl.Quart("08:00", "16:00", 30))
    planning.publier(f"{date.today():%Y-%m}")
    planning.enregistrer()
    srv = serveur.creer_serveur(tmp_path, "127.0.0.1", 0)
    fil = threading.Thread(target=srv.serve_forever, daemon=True)
    fil.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", srv, awa
    srv.shutdown()
    srv.server_close()


def navigateur():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), SansRedirection), jar


def ouvrir(nav, url, donnees=None, entetes=None):
    corps = urllib.parse.urlencode(donnees, doseq=True).encode() if donnees is not None else None
    req = urllib.request.Request(url, data=corps, headers=entetes or {})
    try:
        with nav.open(req) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except urllib.error.HTTPError as erreur:
        return erreur.code, erreur.read().decode("utf-8"), dict(erreur.headers)


def mdp_web(mdp: str) -> str:
    """Mot de passe web des tests (12 caractères, minuscule, majuscule, chiffre, caractère spécial)."""
    return f"Web-{mdp}-2026!"


def connecter(base, nom, mdp):
    """Connexion web : mot de passe web s'il existe déjà, sinon mot de passe de l'application puis création du mot de
    passe web (1re connexion)."""
    nav, jar = navigateur()
    statut, _, entetes = ouvrir(nav, base + "/connexion", {"nom": nom, "mot_de_passe": mdp_web(mdp)})
    if statut == 303 and entetes["Location"] == "/":
        return nav
    statut, _, entetes = ouvrir(nav, base + "/connexion", {"nom": nom, "mot_de_passe": mdp})
    assert statut == 303 and entetes["Location"] == "/mot-de-passe"
    _, page, _ = ouvrir(nav, base + "/mot-de-passe")
    ouvrir(nav, base + "/mot-de-passe", {"csrf": jeton_csrf(page), "nouveau": mdp_web(mdp),
                                         "confirmation": mdp_web(mdp)})
    nav, jar = navigateur()
    statut, _, entetes = ouvrir(nav, base + "/connexion", {"nom": nom, "mot_de_passe": mdp_web(mdp)})
    assert statut == 303 and entetes["Location"] == "/"
    return nav


def jeton_csrf(page: str) -> str:
    return page.split("name='csrf' value='")[1].split("'")[0]


def test_connexion_et_securite(site):
    base, srv, _ = site
    nav, _ = navigateur()
    statut, _, entetes = ouvrir(nav, base + "/")
    assert statut == 303 and entetes["Location"] == "/connexion"
    statut, page, entetes = ouvrir(nav, base + "/connexion", {"nom": "Patron", "mot_de_passe": "faux"})
    assert "incorrect" in page
    assert "script-src" not in entetes["Content-Security-Policy"] and "frame-ancestors 'none'" in \
        entetes["Content-Security-Policy"]
    nav = connecter(base, "Patron", "secret123")
    statut, page, _ = ouvrir(nav, base + "/")
    assert statut == 200 and "Feuilles de temps" in page and "Statistiques Clover" in page
    # formulaire sans jeton anti-falsification, puis venu d'un autre site
    assert ouvrir(nav, base + "/feuilles", {"debut": "2026-10-18"})[0] == 403
    statut, page, _ = ouvrir(nav, base + "/feuilles")
    donnees = {"csrf": jeton_csrf(page), "debut": "2026-10-18"}
    assert ouvrir(nav, base + "/feuilles", donnees, {"Origin": "https://exemple.com"})[0] == 403
    assert ouvrir(nav, base + "/feuilles", donnees)[0] == 200
    # session fermée après l'inactivité
    srv.app.sessions.inactivite = 0
    time.sleep(0.01)
    assert ouvrir(nav, base + "/")[0] == 303


def test_profil_employe_limite(site):
    base, _, awa = site
    nav = connecter(base, "Awa", "secret456")
    statut, page, _ = ouvrir(nav, base + "/")
    assert "Mon horaire" in page and "Feuilles de temps" not in page
    assert ouvrir(nav, base + "/feuilles")[0] == 403
    statut, page, _ = ouvrir(nav, base + "/horaire")
    assert statut == 200 and "08:00 – 16:00" in page and "30 min" in page
    statut, page, _ = ouvrir(nav, base + "/horaire?employe=autre")
    assert "08:00" in page  # un employé ne voit que lui-même
    assert ouvrir(nav, base + "/mes-heures")[0] == 200


def test_pointage_et_approbation(site, tmp_path):
    base, srv, awa = site
    nav = connecter(base, "Awa", "secret456")
    _, page, _ = ouvrir(nav, base + "/pointage")
    assert "Touchez votre nom" in page and "Awa Mballa" in page
    _, page, _ = ouvrir(nav, base + f"/pointage?employe={awa.id}")
    csrf = jeton_csrf(page)
    assert "Tapez votre NIP" in page
    for touche in "9999":
        _, page, _ = ouvrir(nav, base + "/pointage", {"csrf": csrf, "action": f"touche:{touche}"})
    assert "●●●●" in page and "9999" not in page          # le NIP reste sur le serveur
    _, page, _ = ouvrir(nav, base + "/pointage", {"csrf": csrf, "action": "touche:✔"})
    assert "NIP incorrect" in page
    _, page, _ = ouvrir(nav, base + "/pointage", {"csrf": csrf, "nip": "1234", "action": "NIP"})
    assert "pointer:Arrivée" in page and "pointer:Départ" not in page and "Mon horaire" in page
    _, page, _ = ouvrir(nav, base + "/pointage", {"csrf": csrf, "action": "pointer:Arrivée"})
    assert "Arrivée à" in page and "Touchez votre nom" in page
    assert pt.Registre(tmp_path).etat_actuel(awa.id) == pt.ARRIVEE
    # pointage refusé depuis un appareil hors du magasin
    srv.app.config["web"]["postes_pointage"] = ["10.0.0."]
    _, page, _ = ouvrir(nav, base + "/pointage")
    assert "poste du magasin" in page

    # feuille d'une période passée : approuvée par le patron
    registre = pt.Registre(tmp_path)
    debut = pt.debut_periode(date.today()) - timedelta(days=pt.JOURS_PERIODE)
    jour = datetime.combine(debut + timedelta(days=1), datetime.min.time())
    registre.corriger(awa.id, pt.ARRIVEE, jour.replace(hour=8), "Patron", "essai")
    registre.corriger(awa.id, pt.DEPART, jour.replace(hour=16), "Patron", "essai")
    patron = connecter(base, "Patron", "secret123")
    _, page, _ = ouvrir(patron, base + f"/feuilles?debut={debut}")
    assert "Awa Mballa" in page and "8,00" in page
    _, page, _ = ouvrir(patron, base + "/feuilles", {"csrf": jeton_csrf(page), "debut": str(debut),
                                                     "approuver": awa.id, "action": "Approuver"})
    assert "1 feuille(s) approuvée(s)" in page
    assert pt.feuille(pt.Registre(tmp_path), awa, debut).etat == pt.APPROUVEE


def test_trop_d_essais_depuis_une_adresse(site):
    base, _, _ = site
    nav, _ = navigateur()
    for _ in range(serveur.ECHECS_ADRESSE):
        ouvrir(nav, base + "/connexion", {"nom": "Inconnu", "mot_de_passe": "x"})
    _, page, _ = ouvrir(nav, base + "/connexion", {"nom": "Patron", "mot_de_passe": "secret123"})
    assert "Trop d&#x27;essais" in page


def test_client_des_postes(site, tmp_path, monkeypatch):
    from mvogmbi_sync.web import client

    base, _, _ = site
    assert client.normaliser("100.69.84.52") == "http://100.69.84.52:8765"
    assert client.normaliser(" http://serveur:9000/ ") == "http://serveur:9000"
    assert client.normaliser("https://serveur") == "https://serveur"
    for nom in ("marchemvogmbi.com", " www.MarcheMvogmbi.com/ ", "http://marchemvogmbi.com"):
        assert client.adresse_serveur(nom) == "https://app.marchemvogmbi.com"
    assert client.candidats("https://app.marchemvogmbi.com/")[0] == "https://app.marchemvogmbi.com"
    assert "http://app.marchemvogmbi.com:8765" in client.candidats("app.marchemvogmbi.com")
    assert client.adresse_serveur("100.69.84.52") == "http://100.69.84.52:8765"
    for mauvaise in ("", "ftp://x", "http://x/page"):
        with pytest.raises(ValueError):
            client.normaliser(mauvaise)
    assert client.verifier(base) == ""                       # le serveur MVOGMBI_Sync répond
    assert "ne répond pas" in client.verifier("http://127.0.0.1:1", delai=1)
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    assert client.lire_reglages() == {}
    client.ecrire_reglages({"adresse": base})
    assert client.lire_reglages() == {"adresse": base}


def test_pages_paie_du_gerant(site, tmp_path):
    from mvogmbi_sync import conges as co

    base, _, awa = site
    patron = connecter(base, "Patron", "secret123")
    _, page, _ = ouvrir(patron, base + "/")
    assert "Planning mensuel" in page and "Employés et NIP" in page and "Jours fériés et congés" in page
    mois = f"{date.today():%Y-%m}"
    _, page, _ = ouvrir(patron, base + f"/planning?employe={awa.id}&mois={mois}")
    csrf = jeton_csrf(page)
    lundi = date.today().replace(day=1)
    _, page, _ = ouvrir(patron, base + f"/planning?employe={awa.id}", {
        "csrf": csrf, "mois": mois, "du": str(lundi), "au": str(lundi + timedelta(days=6)), "debut": "9",
        "fin": "17:00", "pause": "60", "jours": ["0"], "employe": [awa.id], "action": "Définir"})
    assert "jour(s) mis à jour pour 1 employé(s)" in page and "09:00-17:00 (60)" in page
    _, page, _ = ouvrir(patron, base + f"/planning?employe={awa.id}", {"csrf": csrf, "mois": mois,
                                                                       "action": "Publier le mois"})
    assert "publié" in page
    # employés : ajout, NIP, compte relié
    _, page, _ = ouvrir(patron, base + "/employes")
    _, page, _ = ouvrir(patron, base + "/employes", {"csrf": jeton_csrf(page), "nom": "Ben Ndi", "action": "ajouter"})
    assert "Enregistré" in page and "Ben Ndi" in page
    ident = next(x.id for x in pt.Registre(tmp_path).employes if x.nom == "Ben Ndi")
    _, page, _ = ouvrir(patron, base + "/employes?op=nip&id=" + ident)
    assert "Définir le NIP" in page
    _, page, _ = ouvrir(patron, base + f"/employe?id={ident}")
    _, page, _ = ouvrir(patron, base + "/employe", {"csrf": jeton_csrf(page), "id": ident, "nip": "4321",
                                                    "action": "Changer le NIP"})
    assert "Enregistré" in page
    _, page, _ = ouvrir(patron, base + "/employe", {"csrf": jeton_csrf(page), "id": ident, "nip": "1234",
                                                    "action": "Changer le NIP"})
    assert "autre employé" in page  # NIP déjà pris par Awa
    assert pt.Registre(tmp_path).employe(ident).nip
    # feuille : correction puis annulation
    debut = pt.debut_periode(date.today())
    _, page, _ = ouvrir(patron, base + f"/feuille?employe={awa.id}&debut={debut}")
    csrf = jeton_csrf(page)
    _, page, _ = ouvrir(patron, base + "/feuille", {"csrf": csrf, "employe": awa.id, "debut": str(debut),
                                                    "type": "Arrivée", "moment": f"{debut} 08:00",
                                                    "motif": "oubli", "action": "ajouter"})
    assert "Pointage ajouté" in page and "oubli" in page and "Changer l'heure" in page
    ajoute = next(p for p in pt.Registre(tmp_path).valides(awa.id) if p.source == "Correction")
    _, page, _ = ouvrir(patron, base + "/feuille", {"csrf": csrf, "employe": awa.id, "debut": str(debut),
                                                    "pointage": ajoute.id, "motif": "erreur", "action": "annuler"})
    assert "Pointage annulé" in page
    # congés
    _, page, _ = ouvrir(patron, base + "/conges")
    jour = str(date.today() + timedelta(days=3))
    _, page, _ = ouvrir(patron, base + "/conges", {"csrf": jeton_csrf(page), "employe": awa.id, "type": "Vacances",
                                                   "du": jour, "au": jour, "heures": "8", "onglet": "conges",
                                                   "action": "Ajouter le congé"})
    assert "1 jour(s) de congé" in page
    assert [c.jour for c in co.Registre(tmp_path).conges] == [jour]
    assert "Soldes de congés" in ouvrir(patron, base + "/conges?onglet=soldes")[1]


def test_paies_web_et_droits(site, monkeypatch):
    from decimal import Decimal

    from mvogmbi_sync import paie as pa
    from mvogmbi_sync.web import pages_paie

    base, _, awa = site
    paie = pa.PaieSage(7, date(date.today().year, 1, 15), "PAY15012026", "Awa Mballa",
                       gains={"Salaires": Decimal("100")}, net=Decimal("80"))
    monkeypatch.setattr(pages_paie, "_paies_annee", lambda ctx, annee: [paie])
    nav = connecter(base, "Awa", "secret456")
    assert ouvrir(nav, base + "/planning")[0] == 403 and ouvrir(nav, base + "/conges")[0] == 403
    statut, page, _ = ouvrir(nav, base + "/paies")
    assert statut == 200 and "80,00 $" in page and "bulletin?employe=" in page
    statut, page, entetes = ouvrir(nav, base + f"/bulletin?employe={awa.id}&annee={paie.jour.year}&paie=7")
    assert statut == 200 and "Fiche de paie" in page and "'unsafe-inline'" in entetes["Content-Security-Policy"]
    assert ouvrir(nav, base + f"/bulletin?employe=autre&annee={paie.jour.year}&paie=7")[0] == 404


def test_client_bureau_a_distance(tmp_path, monkeypatch):
    from mvogmbi_sync.web import client

    monkeypatch.setenv("APPDATA", str(tmp_path))
    texte = client.fichier_rdp(client.adresse_serveur("marchemvogmbi.com")).read_text(encoding="utf-8")
    assert "full address:s:app.marchemvogmbi.com" in texte and "prompt for credentials:i:1" in texte


def test_menu_comme_l_application_windows(site):
    from urllib.parse import quote

    base, _, _ = site
    patron = connecter(base, "Patron", "secret123")
    _, page, _ = ouvrir(patron, base + "/planning")
    for rubrique in ("Administration", "Articles", "Stock", "Vente", "Fournisseur", "Comptabilité", "RIA", "Paie",
                     "État"):
        assert f"&nbsp; {rubrique}</summary>" in page
    assert "href='/plan-comptable'" in page and "class='actif ' href='/planning'" in page
    assert "href='/inventaire-tournant'" in page and "Marché MVOG-MBI Sherbrooke" in page
    _, page, _ = ouvrir(patron, base + "/")
    assert "Mise en route" in page and "Bienvenue dans MVOGMBI_Sync" in page and "Se déconnecter" in page
    _, page, _ = ouvrir(patron, base + "/complete?f=" + quote("Plan comptable"))  # renvoi : toujours possible
    assert "Application complète (Bureau à distance)" in page
    awa = connecter(base, "Awa", "secret456")
    _, page, _ = ouvrir(awa, base + "/")
    assert "Comptabilité</summary>" not in page and "Mon horaire" in page
    assert ouvrir(awa, base + "/complete?f=" + quote("Plan comptable"))[0] == 403
    assert ouvrir(awa, base + "/plan-comptable")[0] == 403 and ouvrir(awa, base + "/audit")[0] == 403
    _, page, _ = ouvrir(awa, base + "/aide?page=faq")
    assert "class='q'" in page


def test_consultations(site):
    import time as temps

    base, _, _ = site
    patron = connecter(base, "Patron", "secret123")
    statut, page, _ = ouvrir(patron, base + "/audit")
    assert statut == 200 and "Chaîne d&#x27;empreintes intacte" in page and "Patron" in page
    debut = temps.time()
    statut, page, _ = ouvrir(patron, base + "/clients")
    assert statut == 200 and "Sage ne répond pas" in page and temps.time() - debut < 30
    with urllib.request.urlopen(base + "/logo.png") as r:  # sans connexion (page de connexion)
        assert r.status == 200 and r.read(4)[1:] == b"PNG"


def test_vague_etat(site, tmp_path):
    from mvogmbi_sync.calendrier_paie import Calendrier

    base, _, _ = site
    cal = Calendrier(tmp_path)
    cal.definir(date.today().year, date(date.today().year, 1, 12))
    cal.enregistrer()
    patron = connecter(base, "Patron", "secret123")
    _, page, _ = ouvrir(patron, base + "/calendrier-paie")
    assert "Calendrier de paie" in page and f"{date.today().year}-01-12" in page
    statut, page, _ = ouvrir(patron, base + "/main-oeuvre")  # pas de jeton Clover ici : message, pas de coupure
    assert statut == 200 and "Clover ne répond pas" in page
    for chemin in ("/main-oeuvre", "/documents-stock", "/livre-inventaire", "/articles"):  # filtre « Dépôt » (2026-11-05)
        from urllib.parse import quote

        statut, page, _ = ouvrir(patron, base + chemin + "?depot=" + quote("Emplacement par défaut"))
        assert statut == 200 and "choix-multiple" in page and "Tout sélectionner" in page, chemin
    for chemin in ("/archives-fournisseurs", "/comptes-categories"):
        statut, page, _ = ouvrir(patron, base + chemin)
        assert statut == 200 and "erreur" not in page.split("<main>")[1][:4000].split("class='note'")[0], chemin
    _, page, _ = ouvrir(patron, base + "/planning")
    assert "href='/pareto'" in page and "href='/suivi-ventes'" in page


def test_caisse_et_depenses(site, tmp_path, monkeypatch):
    from mvogmbi_sync import caisse as ca
    from mvogmbi_sync import depenses as dp
    from mvogmbi_sync import plan_comptable

    base, _, _ = site
    patron = connecter(base, "Patron", "secret123")
    hier = date.today() - timedelta(days=1)
    statut, page, _ = ouvrir(patron, base + f"/caisse?jour={hier}")
    assert statut == 200 and "Clover ne répond pas" in page   # pas de jeton ici : comptage possible quand même
    _, page, _ = ouvrir(patron, base + "/caisse", {"csrf": jeton_csrf(page), "jour": str(hier), "c20": "10",
                                                   "c5": "2", "fond": "150,00", "action": "Enregistrer"})
    assert "enregistré" in page
    c = ca.Registre(tmp_path).comptage(hier)
    assert c.compte == "210.00" and c.a_deposer == Decimal("60.00")
    # dépense avec reçu (formulaire multipart)
    monkeypatch.setattr(plan_comptable, "verifier", lambda *a, **k: None)
    _, page, _ = ouvrir(patron, base + "/depenses")
    jeton = jeton_csrf(page)
    limite = "----MVOGMBI"
    champs = {"csrf": jeton, "jour": str(hier), "fournisseur": "Quincaillerie", "description": "ampoules",
              "montant": "11,50 $", "taxe": "GQ", "compte": "5450", "moyen": dp.PETITE_CAISSE, "action": "Ajouter"}
    corps = b"".join(f"--{limite}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
                     for k, v in champs.items())
    corps += (f"--{limite}\r\nContent-Disposition: form-data; name=\"recu\"; filename=\"reçu.pdf\"\r\n"
              f"Content-Type: application/pdf\r\n\r\n").encode() + b"%PDF-1.4 essai\r\n" + f"--{limite}--\r\n".encode()
    req = urllib.request.Request(base + "/depenses", data=corps,
                                 headers={"Content-Type": f"multipart/form-data; boundary={limite}"})
    with patron.open(req) as r:
        page = r.read().decode("utf-8")
    assert "DP-0001 ajoutée" in page and "11,50 $" in page
    d = dp.Registre(tmp_path).depenses[0]
    assert d.montant == "11.50" and (tmp_path / "donnees" / "recus" / d.recu).read_bytes().startswith(b"%PDF")
    # saisie dans Sage refusée tant que les comptes manquent (aucun travail lancé)
    _, page, _ = ouvrir(patron, base + "/depenses", {"csrf": jeton, "action": "Saisir dans Sage"})
    assert "Comptes Sage à choisir" in page


def test_vague_comptabilite(site, tmp_path):
    from mvogmbi_sync import ria

    base, _, _ = site
    patron = connecter(base, "Patron", "secret123")
    for chemin in ("/encaissements", "/paiements-fournisseurs", "/rapprochement", "/etats-ria"):
        statut, page, _ = ouvrir(patron, base + chemin)
        assert statut == 200, chemin
    _, page, _ = ouvrir(patron, base + "/ria")
    jeton = jeton_csrf(page)
    assert "Solde dû à RIA" in page and "Confirmer le surplus" in page
    _, page, _ = ouvrir(patron, base + "/ria", {"csrf": jeton, "jour": str(date.today()), "montant": "250,00",
                                                "description": "paiement", "action": "Paiement en espèces"})
    assert ria.Registre(tmp_path).operations[0].numero == "RI-0001" and "250,00 $" in page
    _, page, _ = ouvrir(patron, base + "/ria", {"csrf": jeton, "action": "Saisir dans Sage"})
    assert "Comptes à renseigner" in page          # aucun travail sur Sage sans les comptes
    _, page, _ = ouvrir(patron, base + "/comptes-ria", {"csrf": jeton, "ria": "2410", "commissions": "4090",
                                                        "especes": "1050", "action": "Enregistrer"})
    assert "enregistrés" in page and ria.Registre(tmp_path).comptes["ria"] == "2410"
    _, page, _ = ouvrir(patron, base + "/ria", {"csrf": jeton, "ligne": "0", "action": "Supprimer"})
    assert not ria.Registre(tmp_path).operations
    # relevé : seul un PDF est accepté
    limite = "----X"
    corps = (f"--{limite}\r\nContent-Disposition: form-data; name=\"csrf\"\r\n\r\n{jeton}\r\n"
             f"--{limite}\r\nContent-Disposition: form-data; name=\"action\"\r\n\r\nCharger\r\n"
             f"--{limite}\r\nContent-Disposition: form-data; name=\"releves\"; filename=\"releve.txt\"\r\n\r\n"
             f"pas un pdf\r\n--{limite}--\r\n").encode()
    req = urllib.request.Request(base + "/rapprochement", data=corps,
                                 headers={"Content-Type": f"multipart/form-data; boundary={limite}"})
    with patron.open(req) as r:
        assert "relevé de compte (Desjardins ou BNC) en PDF" in r.read().decode("utf-8")


def test_documents_saisis(site, tmp_path):
    from mvogmbi_sync import documents as dc

    base, _, _ = site
    patron = connecter(base, "Patron", "secret123")
    _, page, _ = ouvrir(patron, base + "/document/saisie?genre=commande")
    jeton = jeton_csrf(page)
    statut, _, entetes = ouvrir(patron, base + "/document/saisie", {
        "csrf": jeton, "genre": "commande", "n": "", "tiers": "Restaurant Kribi", "jour": "2026-11-02", "depot": "",
        "remarque": "", "sens": "", "article": ["C0001", ""], "description": ["Plantain", ""], "quantite": ["3", ""],
        "prix": ["2,50", ""], "taxe": ["", ""], "action": "Enregistrer"})
    assert statut == 303 and entetes["Location"] == "/document?n=CC-0001"
    _, page, _ = ouvrir(patron, base + "/document?n=CC-0001")
    assert "7,50 $" in page and "Facturer la commande" in page
    statut, _, entetes = ouvrir(patron, base + "/document", {"csrf": jeton, "n": "CC-0001", "action": "Facturer"})
    assert statut == 303 and entetes["Location"].startswith("/document?n=FV-")
    registre = dc.Registre(tmp_path)
    assert registre.document("CC-0001").etat == dc.FACTUREE
    with patron.open(base + "/document/pdf?n=CC-0001") as r:
        assert r.read(4) == b"%PDF"
    facture = entetes["Location"].split("=")[1]
    statut, _, entetes = ouvrir(patron, base + "/document", {"csrf": jeton, "n": facture, "action": "Supprimer"})
    assert statut == 303 and dc.Registre(tmp_path).document("CC-0001").etat == dc.OUVERTE
    _, page, _ = ouvrir(patron, base + "/documents-vente?du=2026-11-01&au=2026-11-30&voir=1")
    assert "CC-0001" in page and "en bleu : documents de l" in page and "🔀 Transformer" in page
    _, page, _ = ouvrir(patron, base + "/documents-vente?du=2026-11-01&au=2026-11-30&voir=1&op=ouvrir&ligne=app:doc:CC-0001")
    assert "/document?n=CC-0001" in page
    _, page, _ = ouvrir(patron, base + "/document/choisir?cote=stock")
    assert "Quel type de document de stock voulez-vous ajouter ?" in page and "Inventaire tournant" in page
    statut, _, entetes = ouvrir(patron, base + "/document/choisir", {"csrf": jeton_csrf(page), "cote": "stock",
                                                                    "type": "Entrée de stock", "action": "OK"})
    assert statut == 303 and "sens=Entr" in entetes["Location"]
    statut, _, entetes = ouvrir(patron, base + "/document/choisir", {"csrf": jeton_csrf(page), "cote": "stock",
                                                                    "type": "Perte et démarque", "action": "OK"})
    assert entetes["Location"] == "/pertes"
    _, page, _ = ouvrir(patron, base + "/document/choisir?cote=vente")
    assert "Quel type de document voulez-vous ajouter ?" in page
    awa = connecter(base, "Awa", "secret456")
    assert ouvrir(awa, base + "/document?n=CC-0001")[0] == 403


def test_factures_fournisseurs_web(site, tmp_path):
    from mvogmbi_sync import fournisseurs as fo

    base, srv, _ = site
    patron = connecter(base, "Patron", "secret123")
    _, page, _ = ouvrir(patron, base + "/factures-fournisseurs")
    jeton = jeton_csrf(page)
    limite = "----F"
    corps = (f"--{limite}\r\nContent-Disposition: form-data; name=\"csrf\"\r\n\r\n{jeton}\r\n"
             f"--{limite}\r\nContent-Disposition: form-data; name=\"action\"\r\n\r\nAjouter des factures\r\n"
             f"--{limite}\r\nContent-Disposition: form-data; name=\"facture\"; filename=\"facture.pdf\"\r\n\r\n"
             f"%PDF-1.4 illisible\r\n--{limite}--\r\n").encode()
    req = urllib.request.Request(base + "/factures-fournisseurs", data=corps,
                                 headers={"Content-Type": f"multipart/form-data; boundary={limite}"})
    try:
        patron.open(req)
    except urllib.error.HTTPError as reponse:  # redirection vers le travail (non suivie par le navigateur d'essai)
        assert reponse.code == 303 and reponse.headers["Location"].startswith("/tache?id=")
    for _ in range(100):
        if fo.Registre(tmp_path).factures:
            break
        time.sleep(0.1)
    f = fo.Registre(tmp_path).factures[0]
    assert f.etat == fo.A_SAISIR
    _, page, _ = ouvrir(patron, base + "/factures-fournisseurs?i=0")
    assert "Lignes de la facture" in page and "📤 Importer cette facture" in page
    _, page, _ = ouvrir(patron, base + "/factures-fournisseurs", {
        "csrf": jeton, "i": "0", "fournisseur": "Grossiste Afro", "numero": "F-77", "date": "2026-11-01",
        "sous_total": "20", "tps": "0", "tvq": "0", "total": "20", "action": "➕"})
    assert "l=0" in page and "Article Sage :" in page
    commun = {"csrf": jeton, "i": "0", "l": "0", "fournisseur": "Grossiste Afro", "numero": "F-77",
              "date": "2026-11-01", "sous_total": "20", "tps": "0", "tvq": "0", "total": "20",
              "l_code": "", "l_description": "Plantain caisse", "l_quantite": "2", "l_prix": "10", "l_facteur": "12",
              "l_taxe": ""}
    _, page, _ = ouvrir(patron, base + "/factures-fournisseurs", {**commun, "action": "Appliquer"})
    f = fo.Registre(tmp_path).factures[0]
    assert f.lignes[0].montant == Decimal("20.00") and f.lignes[0].en_sage()[0] == 24 and not f.lignes[0].confirme
    f.lignes[0].numero_sage = "B0000190"
    reg = fo.Registre(tmp_path)
    reg.factures[0] = f
    reg.enregistrer()
    _, page, _ = ouvrir(patron, base + "/factures-fournisseurs", {**commun, "action": "Confirmer la proposition"})
    f = fo.Registre(tmp_path).factures[0]
    assert f.lignes[0].confirme and f.etat == fo.PRETE, f.controles()
    _, page, _ = ouvrir(patron, base + "/factures-fournisseurs", {**commun, "action": "Enregistrer la facture"})
    assert "Facture enregistrée" in page and "prête à importer" in page
    statut, _, entetes = ouvrir(patron, base + "/facture-fournisseur?i=0")
    assert statut == 303 and entetes["Location"] == "/factures-fournisseurs?i=0"


def test_achats_web(site, tmp_path):
    from mvogmbi_sync import fournisseurs as fo
    from mvogmbi_sync import retours as rt

    base, _, _ = site
    patron = connecter(base, "Patron", "secret123")
    _, page, _ = ouvrir(patron, base + "/saisir-facture-achat")
    jeton = jeton_csrf(page)
    statut, _, entetes = ouvrir(patron, base + "/saisir-facture-achat", {
        "csrf": jeton, "fournisseur": "Grossiste Afro", "numero": "A-12", "date": "2026-11-02",
        "l_article": "B0000190", "l_description": "Plantain", "l_quantite": "2", "l_prix": "1.25", "l_taxe": "",
        "action": "Ajouter aux factures fournisseurs"})
    assert statut == 303 and entetes["Location"] == "/factures-fournisseurs?i=0"
    assert fo.Registre(tmp_path).factures[0].modele == "Saisie manuelle"
    _, page, _ = ouvrir(patron, base + "/bons-commande")
    assert "Proposer les commandes" in page and "Comparer avec la facture" in page
    _, page, _ = ouvrir(patron, base + "/bons-commande", {
        "csrf": jeton_csrf(page), "fournisseur": "Grossiste Afro", "jour": "2026-11-04", "l_numero": ["B0000190", ""],
        "l_description": ["Plantain", ""], "l_quantite": ["2", ""], "l_prix": ["10", ""], "l_facteur": ["12", ""],
        "action": "Créer le bon de commande"})
    assert "Bon BC-0001 créé" in page
    _, page, _ = ouvrir(patron, base + "/bons-commande", {"csrf": jeton_csrf(page), "bon": "BC-0001",
                                                          "op": "transformer"})
    assert "Transformation de BC-0001" in page
    _, page, _ = ouvrir(patron, base + "/retours", {
        "csrf": jeton, "fournisseur": "Grossiste Afro", "facture": "A-12", "jour": "2026-11-03", "motif": "abîmé",
        "article": "B0000190", "description": "Plantain", "quantite": "2", "prix": "1,25", "taxe": "",
        "action": "Ajouter la ligne"})
    assert "Retirer la ligne" in page and "B0000190" in page
    _, page, _ = ouvrir(patron, base + "/retours", {
        "csrf": jeton, "fournisseur": "Grossiste Afro", "facture": "A-12", "jour": "2026-11-03", "motif": "abîmé",
        "l_article": "B0000190", "l_description": "Plantain", "l_quantite": "2", "l_prix": "1,25", "l_taxe": "",
        "action": "Créer le retour"})
    assert "Retour R-A-12 créé" in page and "2,50 $" in page
    assert rt.Registre(tmp_path).retours[0].lignes[0].quantite == "2"


def test_articles_web(site, tmp_path, monkeypatch):
    from mvogmbi_sync import cache_lectures, paquet3 as p3
    from mvogmbi_sync import pertes as pe

    catalogue = [{"id": "ABC123", "name": "Plantain jaune", "price": 199, "code": "", "itemStock": {"quantity": 40}},
                 {"id": "DEF456", "name": "Attiéké 1kg", "price": 599}]
    monkeypatch.setattr(cache_lectures, "inventaire_clover", lambda racine, pv=None: catalogue)
    monkeypatch.setattr(pe, "appliquer", lambda racine, config, numero, client=None: pe.Registre(racine).perte(numero))
    base, _, _ = site
    patron = connecter(base, "Patron", "secret123")
    _, page, _ = ouvrir(patron, base + "/pertes")
    assert "Déclarer une perte" in page and "Rapport des pertes" in page and "Plantain jaune — ABC123" in page
    commun = {"csrf": jeton_csrf(page), "pv": "1", "jour": "2026-11-03", "motif": pe.MOTIFS[0], "remarque": ""}
    _, page, _ = ouvrir(patron, base + "/pertes", {**commun, "article": "Plantain jaune — ABC123", "quantite": "3",
                                                    "action": "Ajouter la ligne"})
    assert "1 ligne(s)" in page and "name='lid' value='ABC123'" in page
    statut, _, entetes = ouvrir(patron, base + "/pertes", {**commun, "lid": "ABC123", "lq": "3",
                                                           "action": "Enregistrer et sortir du stock"})
    assert statut == 303 and entetes["Location"].startswith("/tache?id=")
    p = pe.Registre(tmp_path).pertes[0]
    assert p.numero == "PE-0001" and p.lignes[0].quantite == "3"
    _, page, _ = ouvrir(patron, base + "/pertes?onglet=liste&perte=PE-0001")
    assert "Lignes de PE-0001" in page and "Refaire la sortie du stock Clover" in page
    assert ouvrir(patron, base + "/pertes?onglet=rapport&afficher=1")[0] == 200
    _, page, _ = ouvrir(patron, base + "/promotions")
    _, page, _ = ouvrir(patron, base + "/promotions", {
        "csrf": jeton_csrf(page), "pv": "1", "article": "Attiéké 1kg — 5.99 $", "prix": "4,99", "du": "2026-11-10",
        "au": "2026-11-16", "action": "Ajouter"})
    assert "PR-0001 prévue" in page and p3.Promotions(tmp_path).liste[0].prix_promo == "4.99"
    from types import SimpleNamespace
    from mvogmbi_sync import couts_clover as cc
    propositions = [SimpleNamespace(nom="Plantain jaune", numero_sage="B0000190", prix=Decimal("1.99"),
                                    cout_clover=Decimal("1.00"), cump=Decimal("1.20"), etat="À mettre à jour",
                                    note="", permis=True, cochee_par_defaut=True),
                    SimpleNamespace(nom="Attiéké 1kg", numero_sage="C0001", prix=Decimal("5.99"), cout_clover=None,
                                    cump=Decimal("99"), etat="Valeur aberrante", note="", permis=False,
                                    cochee_par_defaut=False)]
    monkeypatch.setattr(cc, "lire", lambda racine, config, ouvrir=True: (propositions, 3))
    _, page, _ = ouvrir(patron, base + "/couts-clover")
    assert "Tout cocher" in page and "name='choix' value='0' checked" in page and "value='1'" not in page
    _, page, _ = ouvrir(patron, base + "/couts-clover?filtre=Valeur%20aberrante")
    assert "1 ligne(s) affichée(s)" in page
    _, page, _ = ouvrir(patron, base + "/etiquettes")
    _, page, _ = ouvrir(patron, base + "/etiquettes", {"csrf": jeton_csrf(page), "article": "Plantain jaune — ABC123",
                                                       "nombre": "2", "action": "Ajouter"})
    assert "2 étiquette(s)" in page
    _, page, _ = ouvrir(patron, base + "/etiquettes", {"csrf": jeton_csrf(page), "eid": ["ABC123"],
                                                       "format": "Feuille Avery 5160 / 8160 (3 × 10)",
                                                       "action": "Imprimer les étiquettes"})
    assert "Plantain jaune" in page and "1,99 $" in page


def test_catalogue_web(site, tmp_path, monkeypatch):
    from mvogmbi_sync import cache_lectures
    from mvogmbi_sync import correspondance as co

    catalogue = [{"id": "ABC123", "name": "Plantain jaune", "price": 199, "sku": "LOT-7"},
                 {"id": "DEF456", "name": "Attiéké 1kg", "price": 599, "sku": "31/12/2026"}]
    monkeypatch.setattr(cache_lectures, "inventaire_clover", lambda racine, pv=None: catalogue)
    co.ecrire_correspondance([co.Correspondance(co.A_CONFIRMER, "Attiéké 1kg", "Féculents", Decimal("0"), "C0001",
                                                "Attiéké 500g", "4016", "Ressemblance", 80, "", "", "DEF456")],
                             tmp_path / "donnees" / "correspondance_articles.xlsx")
    base, _, _ = site
    patron = connecter(base, "Patron", "secret123")
    _, page, _ = ouvrir(patron, base + "/articles-clover?ugs=1")
    assert "Plantain jaune" in page and "Attiéké" not in page        # UGS « LOT-7 » n'est pas une date
    _, page, _ = ouvrir(patron, base + "/correspondance")
    assert "Attiéké 1kg" in page and "Article sélectionné" in page
    from mvogmbi_sync.articles_sage import ArticleSage, ecrire_copie
    ecrire_copie([ArticleSage("C0001", "Attiéké 500g", "Stock", "4016")], tmp_path / "donnees" / "articles_sage.csv")
    _, page, _ = ouvrir(patron, base + "/correspondance?filtre=Tous&id=DEF456")
    assert "C0001" in page and "(autre format)" in page and "Créer l'article dans Sage" in page
    donnees = {"csrf": jeton_csrf(page), "pv": "1", "filtre": "Tous", "q": "", "id": "DEF456", "numero": "C0001"}
    _, page, _ = ouvrir(patron, base + "/correspondance", {**donnees, "action": "Confirmer l'article choisi"})
    assert "pas le même format" in page                              # 1kg / 500g : refusé sans « quand même »
    _, page, _ = ouvrir(patron, base + "/correspondance", {**donnees, "action": "Confirmer quand même"})
    assert co.lire_correspondances(tmp_path / "donnees" / "correspondance_articles.xlsx")[0].statut == co.CONFIRME
    _, page, _ = ouvrir(patron, base + "/creer-article?nom=Atti%C3%A9k%C3%A9&id_clover=DEF456")
    assert "Article Clover existant" in page
    _, page, _ = ouvrir(patron, base + "/comptes-categories")
    _, page, _ = ouvrir(patron, base + "/comptes-categories", {"csrf": jeton_csrf(page), "nouvelle": "Féculents",
                                                               "action": "➕"})
    _, page, _ = ouvrir(patron, base + "/comptes-categories", {
        "csrf": jeton_csrf(page), "categorie": "Féculents", "prefixe": "C", "actif": "1516", "produits": "4016",
        "cmv": "5016", "ecart": "", "action": "Appliquer"})
    from mvogmbi_sync.creation_articles import TableCategories
    assert TableCategories(tmp_path).lignes["Féculents"].ecart == "5016" and "Table enregistrée" in page
    _, page, _ = ouvrir(patron, base + "/historique?type=Statistiques%20fournisseur")
    assert "Par :" in page and "Articles du" in page and "Statistiques employé" in page
    _, page, _ = ouvrir(patron, base + "/budget")
    _, page, _ = ouvrir(patron, base + "/budget", {"csrf": jeton_csrf(page), "mois": "2026-10", "poste0": "50000",
                                                   "poste1": "35000", "poste2": "8000",
                                                   "action": "Enregistrer le budget"})
    from mvogmbi_sync.budget import Budget
    assert "Budget de 2026-10 enregistré" in page and Budget(tmp_path).mois(2026, 10)["Autres charges"] == 8000
    _, page, _ = ouvrir(patron, base + "/interrogation-fournisseur")
    assert "<option selected>Fournisseur</option>" in page
    _, page, _ = ouvrir(patron, base + "/historique?type=Vente&chercher=1")
    assert "Résultats : Vente" in page
    for chemin in ("/inventaire", "/inventaire-tournant", "/transferts", "/creer-article"):
        assert ouvrir(patron, base + chemin)[0] == 200, chemin


def test_administration_web(site, tmp_path, monkeypatch):
    from mvogmbi_sync import coffre
    from mvogmbi_sync.utilisateurs import Registre as RegistreU

    gardes = {}
    monkeypatch.setattr(coffre, "ecrire", lambda cle, valeur: gardes.__setitem__(cle, valeur))
    monkeypatch.setattr(coffre, "present", lambda cle: cle in gardes)
    base, srv, _ = site
    patron = connecter(base, "Patron", "secret123")
    _, page, _ = ouvrir(patron, base + "/admin/clover")
    jeton = jeton_csrf(page)
    _, page, _ = ouvrir(patron, base + "/admin/clover", {"csrf": jeton, "merchant_id": "ABCDEFGHJK123",
                                                         "jeton": "jeton-essai", "action": "Enregistrer"})
    assert "enregistrée" in page and "jeton-essai" not in page and gardes[coffre.CLOVER_JETON] == "jeton-essai"
    import tomllib
    config = tomllib.loads((tmp_path / "config.toml").read_text(encoding="utf-8"))
    assert config["clover"]["merchant_id"] == "ABCDEFGHJK123" and config["web"]["postes_pointage"] == ["127.0.0.1"]
    # utilisateurs : nouveau compte, puis accès du profil Employé limité à « Mon horaire »
    _, page, _ = ouvrir(patron, base + "/utilisateurs", {"csrf": jeton, "nom": "Comptable 1", "profil": "Comptable",
                                                         "mot_de_passe": "secret789", "action": "Ajouter"})
    assert RegistreU(tmp_path).trouver("Comptable 1").profil == "Comptable"
    _, page, _ = ouvrir(patron, base + "/utilisateurs", {"csrf": jeton, "profil": "Employé", "fonction": ["Mon horaire"],
                                                         "pdv_tous": "1", "action": "Accès"})
    reg = RegistreU(tmp_path)
    assert reg.fonctions_permises["Employé"] == ["Mon horaire"] and "accueil" in reg.profils["Employé"]
    awa = connecter(base, "Awa", "secret456")
    assert ouvrir(awa, base + "/horaire")[0] == 200 and ouvrir(awa, base + "/pointage")[0] == 403
    assert ouvrir(awa, base + "/utilisateurs")[0] == 403 and ouvrir(awa, base + "/admin/clover")[0] == 403


def test_traitement_paie_web(site, tmp_path, monkeypatch):
    from mvogmbi_sync import paie as pa
    from mvogmbi_sync.web import pages_paie

    base, _, awa = site
    paie = pa.PaieSage(9, date(date.today().year, 1, 15), "PAY15012026", "Awa Mballa",
                       gains={"Salaires": Decimal("100")}, net=Decimal("80"))
    monkeypatch.setattr(pages_paie, "_paies_annee", lambda ctx, annee: [paie])
    from mvogmbi_sync.web import pages_traitement_paie
    monkeypatch.setattr(pages_traitement_paie, "_paies_annee", lambda ctx, annee: [paie])
    patron = connecter(base, "Patron", "secret123")
    for chemin in ("/traitement-paie", "/traitement-paie?onglet=validees", "/fin-emploi"):
        assert ouvrir(patron, base + chemin)[0] == 200, chemin
    _, page, _ = ouvrir(patron, base + f"/paies-sage?du={date.today().year}-01-01&au={date.today()}")
    assert "Awa Mballa" in page and "80,00 $" in page
    _, page, _ = ouvrir(patron, base + f"/fin-annee?annee={date.today().year}")
    assert "Concordance" in page and "Awa Mballa" in page
    # paie dans le futur refusée (période en cours)
    from mvogmbi_sync import paie_temps as pt
    _, page, _ = ouvrir(patron, base + "/traitement-paie?onglet=validees")
    debut = pt.debut_periode(date.today())
    _, page, _ = ouvrir(patron, base + "/traitement-paie", {"csrf": jeton_csrf(page), "periode": str(debut),
                                                            "jour": str(date.today()), "onglet": "validees"})
    assert "pas terminée" in page
    awa_nav = connecter(base, "Awa", "secret456")
    assert ouvrir(awa_nav, base + "/paies-sage")[0] == 403


def test_graphiques_svg_comme_windows():
    from mvogmbi_sync.web.graphiques_svg import BLEU, BLEU_PALE, Graphique

    barres = Graphique(600, 200, "Ventes par heure").barres(["09h", "10h", "11h"], [
        ("Ventes nettes", [Decimal("100"), Decimal("513"), Decimal("250")], BLEU)], "Aucune vente").svg()
    assert "<svg" in barres and "600 $" in barres and "moy. 288 $" in barres and "513 $" in barres  # axe 513 -> 600
    courbes = Graphique(800, 170, "Évolution").courbes(["01/11", "02/11", "03/11"], [
        ("Période", [Decimal(1), Decimal(4545), Decimal(2)], BLEU, False), ("Avant", [1, 2, 3], BLEU_PALE, True)]).svg()
    assert "4,8 k$" in courbes and "max 4,5 k$ (02/11)" in courbes and "stroke-dasharray='5,3'" in courbes
    anneau = Graphique(360, 175, "Montant perçu").anneau([(f"M{i}", Decimal(i + 1)) for i in range(8)]).svg()
    assert anneau.count("<path") == 6 and "Autres" in anneau          # 5 parts + « Autres », comme Windows
    vide = Graphique(360, 175, "Rien").classement([], vide="Aucune vente").svg()
    assert "Aucune vente" in vide
    chaleur = Graphique(800, 240, "Jour × heure").chaleur(["Lun", "Mar"], ["9h", "10h"], [[1, 2], [3, 0]]).svg()
    assert "<title>Mar 9h" in chaleur


def test_exporter_les_tableaux_comme_windows(site):
    base, _, awa = site
    patron = connecter(base, "Patron", "secret123")
    _, page, _ = ouvrir(patron, base + "/employes")
    assert "⬇ Exporter ▾" in page and "exporter=0&amp;format=xlsx" in page
    with patron.open(base + "/employes?exporter=0&format=xlsx") as r:
        contenu = r.read()
        assert contenu[:2] == b"PK" and "attachment" in r.headers["Content-Disposition"]
    with patron.open(base + "/employes?exporter=0&format=csv") as r:
        texte = r.read().decode("utf-8-sig")
        assert texte.splitlines()[0].startswith("Employé;") and awa.nom in texte
    with patron.open(base + "/employes?exporter=0&format=pdf") as r:
        assert r.read()[:4] == b"%PDF"


def test_serveur_de_l_application(tmp_path, monkeypatch):
    """Serveur de l'application dans config.toml ([serveur], [web]) et serveur.json du client."""
    import json

    from mvogmbi_sync import serveur_appli
    from mvogmbi_sync.web import client

    c = {"web": {"adresse": "100.69.84.52", "port": 8765}}
    serveur_appli.ecrire(c, {"machine": "AUTRE", "adresse": "100.1.2.3", "adresse_locale": "10.0.0.5",
                             "nom_public": "Exemple.com", "port": "9000"})
    assert c["web"] == {"adresse": "100.1.2.3", "port": 9000} and c["serveur"]["nom_public"] == "exemple.com"
    contenu = json.loads(serveur_appli.fichier_client(c))
    assert contenu["noms"]["exemple.com"] == "http://exemple.com:9000"
    monkeypatch.setenv("APPDATA", str(tmp_path))
    (tmp_path / "MVOGMBI_Sync_Client").mkdir()
    (tmp_path / "MVOGMBI_Sync_Client" / "serveur.json").write_bytes(serveur_appli.fichier_client(c))
    assert client.adresse_serveur("exemple.com") == "http://exemple.com:9000"
    assert client.adresse_serveur("app.marchemvogmbi.com") == "https://app.marchemvogmbi.com"  # départ gardé


def test_pointage_wifi_du_magasin(monkeypatch):
    """Pointage : poste du magasin, ou appareil dont Tailscale montre qu'il vient du Wi-Fi du magasin."""
    from mvogmbi_sync import pointage_wifi as pw

    c = {}
    pw.ecrire(c, "MVOG-Magasin", "203.0.113.7, 198.51.100.", "100.101.7.12")
    assert c["pointage"]["adresses_magasin"] == ["203.0.113.7", "198.51.100."]
    assert pw.autorise(c, "100.101.7.12")[0]
    monkeypatch.setattr(pw, "adresse_du_reseau", lambda ip: {"100.1.1.1": "203.0.113.7",
                                                             "100.1.1.2": "198.51.100.40"}.get(ip, ""))
    assert pw.autorise(c, "100.1.1.1")[0] and pw.autorise(c, "100.1.1.2")[0]
    permis, raison = pw.autorise(c, "100.1.1.3")
    assert not permis and "MVOG-Magasin" in raison
    monkeypatch.setattr(pw, "_executer", lambda arguments, delai: (
        '{"Peer": {"a": {"TailscaleIPs": ["100.9.9.9"], "CurAddr": "203.0.113.7:41641"}}}'
        if arguments[0] == "status" else ""))
    pw._MEMOIRE.clear()
    monkeypatch.undo()
    monkeypatch.setattr(pw, "_executer", lambda arguments, delai: (
        '{"Peer": {"a": {"TailscaleIPs": ["100.9.9.9"], "CurAddr": "203.0.113.7:41641"}}}'
        if arguments[0] == "status" else "pong from x (100.8.8.8) via 198.51.100.9:41641 in 20ms"))
    assert pw.adresse_du_reseau("100.9.9.9") == "203.0.113.7"
    assert pw.adresse_du_reseau("100.8.8.8") == "198.51.100.9"


def test_pause_automatique_hors_du_wifi(tmp_path):
    """Téléphone hors du Wi-Fi 5 min de suite : pause à l'heure du départ ; retour sur le Wi-Fi : fin de pause."""
    from datetime import datetime, timedelta

    from mvogmbi_sync import paie_temps as pt
    from mvogmbi_sync import pointage_wifi as pw

    reg = pt.Registre(tmp_path)
    awa = reg.ajouter("Awa")
    reg.enregistrer()
    config = {"pointage": {"adresses_magasin": ["203.0.113.7"], "pause_hors_wifi_minutes": 5}}
    t0 = datetime(2026, 11, 4, 9, 0)
    pt.Registre(tmp_path).pointer(awa.id, pt.ARRIVEE, t0)
    pw.noter_pointage(tmp_path, config, awa.id, pt.ARRIVEE, "100.1.1.1")
    hors, dedans = (lambda ip: False), (lambda ip: True)
    assert pw.controler(tmp_path, config, t0 + timedelta(minutes=10), hors) == []  # 1er constat
    assert pw.controler(tmp_path, config, t0 + timedelta(minutes=13), hors) == []  # 3 min : pas encore
    fait = pw.controler(tmp_path, config, t0 + timedelta(minutes=15), hors)
    assert fait and "en pause depuis 09:10" in fait[0]
    assert pt.Registre(tmp_path).etat_actuel(awa.id) == pt.PAUSE
    fait = pw.controler(tmp_path, config, t0 + timedelta(minutes=40), dedans)
    assert fait and "fin de pause" in fait[0]
    valides = pt.Registre(tmp_path).valides(awa.id)
    assert [p.type for p in valides] == [pt.ARRIVEE, pt.PAUSE, pt.FIN_PAUSE]
    assert valides[1].moment.endswith("09:10:00") and valides[1].auteur == "Automatique"
    # pause pointée par l'employé : jamais terminée par l'application
    pt.Registre(tmp_path).pointer(awa.id, pt.PAUSE, t0 + timedelta(hours=2))
    pw.noter_pointage(tmp_path, config, awa.id, pt.PAUSE, "100.1.1.1")
    assert pw.controler(tmp_path, config, t0 + timedelta(hours=3), dedans) == []
    assert pt.Registre(tmp_path).etat_actuel(awa.id) == pt.PAUSE
    # départ : plus de suivi
    pt.Registre(tmp_path).pointer(awa.id, pt.DEPART, t0 + timedelta(hours=4))
    pw.noter_pointage(tmp_path, config, awa.id, pt.DEPART, "100.1.1.1")
    assert pw.lire_suivi(tmp_path) == {}


def test_activer_desactiver_un_compte(site, tmp_path):
    """Administration > Utilisateurs : un compte désactivé ne se connecte plus et ses sessions se ferment ; jamais
    son propre compte ; réactivé, il se reconnecte."""
    from mvogmbi_sync.utilisateurs import Registre as RegistreU

    base, _, _ = site
    patron = connecter(base, "Patron", "secret123")
    awa = connecter(base, "Awa", "secret456")
    assert ouvrir(awa, base + "/horaire")[0] == 200
    _, page, _ = ouvrir(patron, base + "/utilisateurs")
    jeton = jeton_csrf(page)
    _, page, _ = ouvrir(patron, base + "/utilisateurs", {"csrf": jeton, "compte": "Awa",
                                                         "action": "Activer / désactiver"})
    assert "Compte « Awa » désactivé." in page and not RegistreU(tmp_path).trouver("Awa").actif
    assert ouvrir(awa, base + "/horaire")[0] == 303  # session fermée
    statut, _, _ = ouvrir(navigateur()[0], base + "/connexion", {"nom": "Awa", "mot_de_passe": "secret456"})
    assert statut == 200  # connexion refusée (la page de connexion revient)
    _, page, _ = ouvrir(patron, base + "/utilisateurs", {"csrf": jeton, "compte": "Patron",
                                                         "action": "Activer / désactiver"})
    assert "propre compte" in page and RegistreU(tmp_path).trouver("Patron").actif
    _, page, _ = ouvrir(patron, base + "/utilisateurs", {"csrf": jeton, "compte": "Awa",
                                                         "action": "Activer / désactiver"})
    assert "Compte « Awa » activé." in page
    assert ouvrir(connecter(base, "Awa", "secret456"), base + "/horaire")[0] == 200


def test_prix_de_vente_sage_depuis_clover():
    """Prix Sage comparé au prix Clover des articles reliés : différent coché, formats de prix différents décochés,
    prix variable non cochable."""
    from decimal import Decimal

    from mvogmbi_sync import prix_sage as ps

    articles = [{"id": "A", "name": "Plantain", "price": 249}, {"id": "B", "name": "Riz 1kg", "price": 599},
                {"id": "C", "name": "Riz 1kg (lot)", "price": 649}, {"id": "D", "name": "Poisson", "price": 0,
                                                                       "priceType": "VARIABLE"},
                {"id": "E", "name": "Huile", "price": 1099}]
    liens = {"A": "S1", "B": "S2", "C": "S2", "D": "S3", "E": "S4"}
    sage = {"S1": ("Plantain", Decimal("1.99")), "S2": ("Riz", Decimal("5.99")), "S3": ("Poisson", Decimal("0")),
            "S4": ("Huile", Decimal("10.99"))}
    lignes = {l.numero_sage: l for l in ps.analyser(articles, liens, sage)}
    assert lignes["S1"].etat == ps.DIFFERENT and lignes["S1"].cochee_par_defaut
    assert lignes["S1"].prix_clover == Decimal("2.49") and lignes["S1"].ecart == Decimal("0.50")
    assert lignes["S2"].etat == ps.PLUSIEURS and not lignes["S2"].cochee_par_defaut
    assert lignes["S3"].etat == ps.VARIABLE and not lignes["S3"].permis
    assert lignes["S4"].etat == ps.IDENTIQUE


def test_mot_de_passe_web(site, tmp_path):
    """Mot de passe web à part : 12 caractères, minuscule, majuscule, chiffre, caractère spécial ; créé à la 1re
    connexion web (mot de passe Windows), puis seul accepté sur le web."""
    from mvogmbi_sync.utilisateurs import ErreurUtilisateur, Registre as RegistreU, probleme_mot_de_passe_web

    assert probleme_mot_de_passe_web("court") and probleme_mot_de_passe_web("motdepasse123!")
    assert not probleme_mot_de_passe_web("Marche-Mvog2026!")
    base, _, _ = site
    nav, _ = navigateur()
    statut, _, entetes = ouvrir(nav, base + "/connexion", {"nom": "Awa", "mot_de_passe": "secret456"})
    assert statut == 303 and entetes["Location"] == "/mot-de-passe"
    statut, _, entetes = ouvrir(nav, base + "/horaire")
    assert statut == 303 and entetes["Location"] == "/mot-de-passe"  # rien d'autre avant le mot de passe web
    _, page, _ = ouvrir(nav, base + "/mot-de-passe")
    assert "Créer mon mot de passe web" in page
    jeton = jeton_csrf(page)
    _, page, _ = ouvrir(nav, base + "/mot-de-passe", {"csrf": jeton, "nouveau": "faible", "confirmation": "faible"})
    assert "au moins 12 caractères" in page
    statut, _, _ = ouvrir(nav, base + "/mot-de-passe", {"csrf": jeton, "nouveau": "Marche-Mvog2026!",
                                                       "confirmation": "Marche-Mvog2026!"})
    assert statut == 303 and RegistreU(tmp_path).trouver("Awa").empreinte_web
    nav2, _ = navigateur()
    statut, _, _ = ouvrir(nav2, base + "/connexion", {"nom": "Awa", "mot_de_passe": "secret456"})
    assert statut == 200  # le mot de passe Windows n'ouvre plus l'application web
    statut, _, entetes = ouvrir(nav2, base + "/connexion", {"nom": "Awa", "mot_de_passe": "Marche-Mvog2026!"})
    assert statut == 303 and entetes["Location"] == "/"
    reg = RegistreU(tmp_path)
    assert reg.verifier("Awa", "secret456") is not None  # l'application Windows garde son mot de passe
    try:
        reg.definir_mot_de_passe_web("Awa", "secret456")
        assert False
    except ErreurUtilisateur:
        pass


def test_client_ouvre_directement_l_application_web(tmp_path, monkeypatch):
    """Le client ouvre l'application web tout de suite, même serveur injoignable ; la fenêtre de réglage seulement
    avec « --reglages »."""
    import sys

    from mvogmbi_sync.web import client

    monkeypatch.setenv("APPDATA", str(tmp_path))
    ouvertes, fenetres = [], []
    monkeypatch.setattr(client, "ouvrir", ouvertes.append)
    monkeypatch.setattr(client, "fenetre_reglage", lambda a, m: fenetres.append(a))
    monkeypatch.setattr(client, "verifier", lambda a, delai=5: "Le serveur ne répond pas.")
    monkeypatch.setattr(client, "adresse_installee", lambda: "https://app.marchemvogmbi.com")
    monkeypatch.setattr(sys, "argv", ["MVOGMBI_Sync_Client.exe"])
    client.principal()
    assert ouvertes == ["https://app.marchemvogmbi.com"] and not fenetres
    monkeypatch.setattr(sys, "argv", ["MVOGMBI_Sync_Client.exe", "--reglages"])
    client.principal()
    assert fenetres == ["https://app.marchemvogmbi.com"]


def test_photographier_une_facture(site):
    """Page du téléphone : bouton de l'appareil photo ; deux photos (pages) donnent un PDF de deux pages."""
    from io import BytesIO

    from PIL import Image
    from pypdf import PdfReader

    from mvogmbi_sync.web.pages_fournisseurs import pdf_des_photos

    base, _, _ = site
    nav = connecter(base, "Patron", "secret123")
    statut, page, _ = ouvrir(nav, base + "/photo-facture")
    assert statut == 200 and "capture='environment'" in page and "Terminer la facture" in page
    photos = []
    for couleur in ("white", "gray"):
        tampon = BytesIO()
        Image.new("RGB", (800, 1100), couleur).save(tampon, "JPEG")
        photos.append(tampon.getvalue())
    assert len(PdfReader(BytesIO(pdf_des_photos(photos))).pages) == 2
