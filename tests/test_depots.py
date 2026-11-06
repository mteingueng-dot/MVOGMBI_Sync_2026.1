from decimal import Decimal as D

from mvogmbi_sync import depots
from mvogmbi_sync.points_vente import DEPOT_DEFAUT


CONFIG = {"clover": {"merchant_id": "X"}, "sage": {"depots_sans_clover": "Entrepôt; Réserve"},
          "points_vente": [{"code": "2", "nom": "Magasin 2", "merchant_id": "Y", "client_sage": "Vente M2",
                            "depot_sage": "Magasin 2", "prefixe": "V2"}]}


def test_liste_des_depots_et_filtre():
    """Dépôts des points de vente, emplacement par défaut, dépôts sans Clover ; « Tout sélectionner » = tous."""
    assert depots.noms(CONFIG) == [DEPOT_DEFAUT, "Magasin 2", "Entrepôt", "Réserve"]
    assert depots.du_point_de_vente(CONFIG, "2") == "Magasin 2"
    assert not depots.du_nom(CONFIG, "Entrepôt").avec_clover
    assert depots.choisis(f"Magasin 2 | {depots.TOUS}") is None
    filtre = depots.choisis("Magasin 2 | Entrepôt")
    assert depots.garde("Magasin 2", filtre) and not depots.garde("", filtre)
    assert depots.points_vente_des(CONFIG, ["Magasin 2"]) == ["2"]


def test_transfert_apres_import():
    """Vente : le stock sort du dépôt ; remboursement net : il y revient ; achat : il entre dans le dépôt."""
    assert depots.mouvements(DEPOT_DEFAUT, [("A", D(1))], vente=True) == []
    vente = depots.mouvements("Magasin 2", [("A", D(2)), ("A", D(1)), ("B", D(-1))], vente=True)
    assert vente == [("Magasin 2", DEPOT_DEFAUT, [("A", D(3))]), (DEPOT_DEFAUT, "Magasin 2", [("B", D(1))])]
    assert depots.mouvements("Entrepôt", [("A", D(5))], vente=False) == [(DEPOT_DEFAUT, "Entrepôt", [("A", D(5))])]
    assert depots.reference("FACTURE-TRES-LONGUE-123") == "DP FACTURE-TRES-"


def test_courriel_apres_import_fournisseurs(monkeypatch):
    """Import à la demande : un courriel aux destinataires du compte rendu ; rien si le courriel n'est pas réglé."""
    from mvogmbi_sync import courriel

    envoyes = []
    monkeypatch.setattr(courriel, "envoyer", lambda c, sujet, texte, html=None: envoyes.append((sujet, texte)))
    resultats = {"F1.pdf": "importée (n° 1, 10 $)\n   Clover : A : stock Clover 0 + 1 = 1", "F2.pdf": "non importée : x"}
    courriel.envoyer_bilan_factures_fournisseurs({}, resultats)
    assert envoyes == []
    config = {"courriel": {"serveur": "smtp.exemple.com", "destinataires": "patron@exemple.com"}}
    courriel.envoyer_bilan_factures_fournisseurs(config, resultats)
    assert envoyes[0][0] == "MVOGMBI_Sync — Factures fournisseurs : 1 importée(s), 1 non importée(s)"
    assert "stock Clover 0 + 1 = 1" in envoyes[0][1]


def test_registre_factures_meme_etat_partout(tmp_path):
    """Web et Windows ouverts ensemble : l'import fait sur l'un n'est jamais écrasé par l'enregistrement de
    l'autre ; chacun ne remplace que ce qu'il a changé."""
    import time

    from mvogmbi_sync import fournisseurs as fo

    base = fo.Registre(tmp_path)
    base.factures = [fo.Facture("A.pdf", "a", numero="1", etat=fo.PRETE),
                     fo.Facture("B.pdf", "b", numero="2", etat=fo.A_VERIFIER)]
    base.enregistrer()
    windows, web = fo.Registre(tmp_path), fo.Registre(tmp_path)
    time.sleep(0.05)
    web.factures[0].etat = fo.IMPORTEE  # import fait sur le web
    web.enregistrer()
    assert windows.change_ailleurs()
    windows.factures[1].numero = "2-corrigé"  # saisie faite sous Windows sur une autre facture
    windows.factures[0].fournisseur_sage = "X"  # et la facture importée ailleurs, restée « Prête » ici
    windows.enregistrer()
    relue = {f.fichier: f for f in fo.Registre(tmp_path).factures}
    assert relue["A.pdf"].etat == fo.IMPORTEE and relue["B.pdf"].numero == "2-corrigé"


def test_releve_bnc():
    """Relevé de la Banque Nationale (texte inventé) : débit / crédit d'après le solde, contrôle des totaux ;
    reconnu comme BNC ; compte Sage 1060 par défaut."""
    from decimal import Decimal as D
    from pathlib import Path

    from mvogmbi_sync import rapprochement as rp

    texte = """Relevé de compte
Période du 01-09-2025 au 30-09-2025 Page 1 de 1
No de compte 00-000-00 No succursale 00000
MM JJ DESCRIPTION DÉBIT ($) CRÉDIT ($) SOLDE ($)
08 31 SOLDE PRECEDENT 1 000,00
09 02 G/DEPOT 00000000000 205,00 1 205,00
09 05 VIREMENT INTERAC 1 100,00 105,00
09 29 FACTURATION MENSUELLE 16,60 88,40
FACTURATION DÉTAILLÉE TRANSACTIONS/VOLUME(S) TARIF UNIT./TAUX FRAIS
FORFAIT 7,00
NOMBRE MONTANT TOTAL NOMBRE MONTANT TOTAL
TRANSACTIONS DÉBIT 2 1 116,60 CRÉDIT 1 205,00
"""
    assert rp.banque_du_texte(texte) == "bnc"
    r = rp.lire_releve_bnc(Path("essai.pdf"), None, texte)
    assert (r.debut, r.fin, r.solde_ouverture, r.solde_fermeture) == ("2025-09-01", "2025-09-30", D("1000.00"), D("88.40"))
    assert [m.montant for m in r.mouvements] == [D("205.00"), D("-1100.00"), D("-16.60")]
    assert r.controles() == []
    assert rp.compte_banque({}, "bnc") == "1060" and rp.compte_entier({}, "bnc") == 10600000
    assert rp.banques_reglees({}) == ["desjardins", "bnc"]


def test_documents_de_stock_par_depot():
    """Dépôt lu dans Sage (titrline.lInvLocId) ; journal 14 sans bTrfLoc = ajustement ; écarts de coût écartés."""
    from datetime import date

    from mvogmbi_sync import listes_sage as ls

    class Base:
        def requete(self, sql, params=()):
            j = date(2026, 11, 5)
            return [
                {"id": 1, "d": j, "j": 14, "t": 1, "s": "TR-0001", "q": -2, "m": -4, "e": "Primary location for all"},
                {"id": 1, "d": j, "j": 14, "t": 1, "s": "TR-0001", "q": 2, "m": 4, "e": "Dépôt 2"},
                {"id": 2, "d": j, "j": 14, "t": 0, "s": "DS-0001", "q": 1, "m": 2, "e": "Dépôt 2"},
                {"id": 3, "d": j, "j": 12, "t": 0, "s": "DS-0002", "q": -1, "m": -2, "e": "Primary location for all"},
                {"id": 4, "d": j, "j": 14, "t": 0, "s": "Vente 2026-11-04", "q": 0, "m": 0.03, "e": ""},
            ]

    entetes, lignes = ls.documents_stock(Base(), date(2026, 11, 1), date(2026, 11, 5))
    assert entetes[3] == "Dépôt"
    par_source = {l[2]: l for l in lignes}
    assert set(par_source) == {"TR-0001", "DS-0001", "DS-0002"}
    assert par_source["TR-0001"][1] == "Transfert entre emplacements"
    assert par_source["TR-0001"][3] == "Emplacement par défaut → Dépôt 2"
    assert par_source["DS-0001"][1] == "Ajustement d'inventaire" and par_source["DS-0001"][3] == "Dépôt 2"
    _, filtres = ls.documents_stock(Base(), date(2026, 11, 1), date(2026, 11, 5), ["Dépôt 2"])
    assert {l[2] for l in filtres} == {"TR-0001", "DS-0001"}


def test_main_oeuvre_par_depot(tmp_path):
    from datetime import date, datetime
    from decimal import Decimal

    from mvogmbi_sync import budget as bu, paie_temps as pt
    from mvogmbi_sync.planning import Planning, Quart

    reg = pt.Registre(tmp_path)
    a = reg.ajouter("Alice")
    b = reg.ajouter("Bruno")
    b.depot = "Dépôt 2"
    reg.enregistrer()
    jour = date(2026, 11, 3)
    plan = Planning(tmp_path)
    plan.definir(a.id, [jour], Quart("08:00", "12:00"))
    plan.definir(b.id, [jour], Quart("08:00", "10:00"))
    plan.enregistrer()
    _, planifiees = bu.heures_par_jour_tous(tmp_path, jour, jour)
    assert planifiees[jour] == Decimal(6)
    _, depot2 = bu.heures_par_jour_tous(tmp_path, jour, jour, ["Dépôt 2"])
    assert depot2[jour] == Decimal(2)
    _, defaut = bu.heures_par_jour_tous(tmp_path, jour, jour, ["Emplacement par défaut"])
    assert defaut[jour] == Decimal(4)


def test_rapports_de_gestion_par_point_de_vente(tmp_path):
    """Filtre « Point de vente » des statistiques : pertes, promotions, retours du point de vente ; main-d'œuvre à
    ses dépôts."""
    from datetime import date
    from decimal import Decimal

    from mvogmbi_sync import budget as bu, paie_temps as pt, rapports_gestion as rg
    from mvogmbi_sync.planning import Planning, Quart
    from mvogmbi_sync.points_vente import points_de_vente

    config = {"clover": {"nom": "Magasin 1"},
              "points_vente": [{"code": "2", "nom": "Magasin 2", "depot_sage": "Dépôt 2", "client_sage": "V2"}]}
    deux = [p for p in points_de_vente(config) if p.code == "2"]
    reg = pt.Registre(tmp_path)
    a, b = reg.ajouter("Alice"), reg.ajouter("Bruno")
    b.depot = "Dépôt 2"
    reg.enregistrer()
    jour = date(2026, 11, 3)
    plan = Planning(tmp_path)
    plan.definir(a.id, [jour], Quart("08:00", "12:00"))
    plan.definir(b.id, [jour], Quart("08:00", "10:00"))
    plan.enregistrer()
    tous = rg.main_oeuvre(tmp_path, jour, jour, {"config": config})
    seul = rg.main_oeuvre(tmp_path, jour, jour, {"config": config, "points_vente": deux})
    assert tous.cartes[1][2] == Decimal("6.00") and seul.cartes[1][2] == Decimal("2.00")
    assert rg._du_point("", {"points_vente": deux}) is False and rg._du_point("2", {"points_vente": deux})
    assert bu.heures_par_jour_tous(tmp_path, jour, jour, rg._depots({"points_vente": deux}))[1][jour] == 2


def test_suivi_des_ventes_de_tous_les_points_de_vente(tmp_path):
    from datetime import datetime

    from mvogmbi_sync import rapports as rp
    from mvogmbi_sync.points_vente import points_de_vente

    config = {"clover": {"nom": "Magasin 1"},
              "points_vente": [{"code": "2", "nom": "Magasin 2", "depot_sage": "Dépôt 2", "client_sage": "Client V2",
                                "prefixe": "V2"}]}

    class Base:
        def requete(self, sql, params=()):
            if "REGEXP" in sql:
                client = params[0]
                if client == "Client V2":
                    return [{"s": "V2 2026-11-03", "d": datetime(2026, 11, 3), "m": 50}]
                return [{"s": "Vente 2026-11-03", "d": datetime(2026, 11, 3), "m": 100}]
            return []

    suivi = rp.suivi_ventes(tmp_path, Base(), "Vente Hebdomadaire", 10550000, points_de_vente(config))
    par_n = {l.facture: l for l in suivi}
    assert set(par_n) == {"Vente 2026-11-03", "V2 2026-11-03"}
    assert par_n["V2 2026-11-03"].depot == "Dépôt 2"
    assert par_n["Vente 2026-11-03"].depot == "Emplacement par défaut"
    assert len(par_n["V2 2026-11-03"].valeurs()) == len(rp.ENTETES_SUIVI)
