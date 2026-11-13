"""Relevés de toutes les banques du Canada (demande du propriétaire du 2026-11-12) : OFX / QFX, CSV, PDF par
colonnes en anglais, reconnaissance de la banque et du compte, Interac et dépôts d'espèces. Données inventées."""

from decimal import Decimal
from pathlib import Path

import pytest

from mvogmbi_sync import rapprochement as rp
from mvogmbi_sync.banques_canada import code_du_nom, detecter, nom
from mvogmbi_sync.releves_bancaires import lire_csv, lire_date, lire_ofx, montant

OFX_SGML = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
CHARSET:1252

<OFX><SIGNONMSGSRSV1><SONRS><FI><ORG>RBC<FID>003</FI></SONRS></SIGNONMSGSRSV1>
<BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>CAD
<BANKACCTFROM><BANKID>000300012<ACCTID>5551234<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST><DTSTART>20260901<DTEND>20260930
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260903120000<TRNAMT>1250.40<FITID>1<NAME>DEPOSIT CLOVER<MEMO>BATCH 12
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260902<TRNAMT>-45.00<FITID>2<NAME>MONTHLY FEE
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260905<TRNAMT>80.00<FITID>3<NAME>INTERAC e-Transfer from ALICE
</BANKTRANLIST><LEDGERBAL><BALAMT>3285.40<DTASOF>20260930</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def test_banques_reconnues():
    assert detecter("Relevé de compte Desjardins … Caisse Desjardins de Sherbrooke") == "desjardins"
    assert detecter("RBC Royal Bank — Business Account Statement") == "rbc"
    assert detecter("TD Canada Trust") == "td"
    assert detecter("ABC Distribution Ltd") == "autre"  # « ltd » n'est pas TD
    assert detecter("Scotiabank Canada") == "scotia"
    assert detecter("", "000600012") == "bnc"  # n° d'institution de l'OFX
    # un virement vers une autre banque cité dans les mouvements ne l'emporte pas sur l'en-tête répété
    assert detecter("Banque Nationale … Banque Nationale … virement Desjardins … Banque Nationale") == "bnc"
    assert code_du_nom(nom("cibc")) == "cibc" and code_du_nom("??") == "autre"
    assert detecter("CIBC Smart Account — Withdrawals ($) Deposits ($) Balance ($)") == "cibc"
    assert detecter("Simplii Financial, a division of CIBC") == "simplii"
    assert detecter("Neo Financial — Neo Everyday account statement") == "neo"
    assert detecter("KOHO Financial Inc. — Statement") == "koho"
    assert detecter("BMO Bank of Montreal — Amounts deducted from your account ($)") == "bmo"
    assert detecter("Banque Scotia — Relevé") == "scotia"


def test_montants_et_dates():
    assert montant("1 234,56") == Decimal("1234.56")
    assert montant("-1,234.56") == Decimal("-1234.56")
    assert montant("(12.50)") == Decimal("-12.50")
    assert montant("$1,234.56") == Decimal("1234.56")
    assert montant("") is None
    assert str(lire_date("2026/09/02")) == "2026-09-02"
    assert str(lire_date("9/2/2026", "mja")) == "2026-09-02"
    assert str(lire_date("Sep 2, 2026")) == "2026-09-02"


def test_ofx(tmp_path):
    chemin = tmp_path / "rbc.ofx"
    chemin.write_text(OFX_SGML, encoding="cp1252")
    r = lire_ofx(chemin)
    assert [m.date for m in r.mouvements] == ["2026-09-02", "2026-09-03", "2026-09-05"]  # remis dans l'ordre
    assert r.mouvements[1].description == "DEPOSIT CLOVER BATCH 12"
    assert r.solde_fermeture == Decimal("3285.40") and r.solde_ouverture == Decimal("2000.00")
    assert not r.controles() and (r.debut, r.fin) == ("2026-09-01", "2026-09-30")
    assert rp.est_interac(r.mouvements[2])
    assert rp.lire_releve(chemin).solde_fermeture == Decimal("3285.40")  # lecture d'après l'extension


def test_csv_en_tete_francais(tmp_path):
    chemin = tmp_path / "bmo.csv"
    chemin.write_text("Date;Description;Retrait;Dépôt;Solde\n2026-09-01;Frais;5,00;;995,00\n"
                      "2026-09-02;Dépôt au guichet;;200,00;1 195,00\n", encoding="utf-8-sig")
    r = lire_csv(chemin)
    assert [m.montant for m in r.mouvements] == [Decimal("-5.00"), Decimal("200.00")]
    assert r.solde_ouverture == Decimal("1000.00") and r.solde_fermeture == Decimal("1195.00")
    assert rp.est_especes(r.mouvements[1]) and not r.controles()


def test_csv_anglais_plus_recent_d_abord(tmp_path):
    chemin = tmp_path / "rbc.csv"  # en-tête RBC, dates M/J/AAAA, plus récent d'abord, montant signé
    chemin.write_text("Account Type,Account Number,Transaction Date,Cheque Number,Description 1,Description 2,CAD$,USD$\n"
                      "Chequing,5551234,9/14/2026,,E-TRANSFER RECEIVED,BOB,40.00,\n"
                      "Chequing,5551234,9/2/2026,,MONTHLY FEE,,-12.95,\n", encoding="utf-8")
    r = lire_csv(chemin)
    assert [(m.date, m.montant) for m in r.mouvements] == [("2026-09-02", Decimal("-12.95")),
                                                          ("2026-09-14", Decimal("40.00"))]
    assert r.mouvements[1].description == "E-TRANSFER RECEIVED BOB" and rp.est_interac(r.mouvements[1])


def test_csv_sans_en_tete_sens_controle_par_le_solde(tmp_path):
    chemin = tmp_path / "td.csv"  # TD : date, description, débit, crédit, solde, sans en-tête
    chemin.write_text("09/01/2026,FEE,4.00,,996.00\n09/03/2026,DEPOSIT,,250.00,1246.00\n"
                      "09/04/2026,CHEQUE 12,46.00,,1200.00\n", encoding="utf-8")
    r = lire_csv(chemin)
    assert [m.montant for m in r.mouvements] == [Decimal("-4.00"), Decimal("250.00"), Decimal("-46.00")]
    assert r.solde_ouverture == Decimal("1000.00") and not r.controles()


def test_pdf_par_colonnes_en_anglais(tmp_path):
    fpdf = pytest.importorskip("fpdf")
    pdf = fpdf.FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=9)
    pdf.text(10, 15, "Business Account Statement   From Sep 1, 2026 to Sep 30, 2026")

    def ligne(y, *cellules):
        for x, texte, droite in cellules:
            pdf.text(x - (pdf.get_string_width(texte) if droite else 0), y, texte)

    ligne(30, (10, "Date", False), (30, "Description", False), (120, "Withdrawals", True), (150, "Deposits", True),
          (185, "Balance", True))
    ligne(37, (10, "Sep 01", False), (30, "Opening balance", False), (185, "1,000.00", True))
    ligne(44, (10, "Sep 02", False), (30, "Monthly fee", False), (120, "12.50", True), (185, "987.50", True))
    ligne(51, (10, "Sep 05", False), (30, "ATM deposit", False), (150, "300.00", True), (185, "1,287.50", True))
    ligne(58, (10, "Sep 30", False), (30, "Closing balance", False), (185, "1,287.50", True))
    chemin = tmp_path / "scotia.pdf"
    pdf.output(str(chemin))
    r = rp.lire_releve(chemin)
    assert [(m.date, m.montant) for m in r.mouvements] == [("2026-09-02", Decimal("-12.50")),
                                                          ("2026-09-05", Decimal("300.00"))]
    assert r.solde_ouverture == Decimal("1000.00") and r.solde_fermeture == Decimal("1287.50")
    assert not r.controles() and rp.est_especes(r.mouvements[1])


def test_releve_range_dans_le_compte_de_sa_banque(tmp_path):
    config = {"rapprochement": {"banque_depot": "rbc"},
              "comptes_bancaires": [{"code": "td1", "nom": "TD épargne", "format": "td", "compte_sage": "1070"}]}
    comptes = rp.comptes_bancaires(config)
    assert comptes[0].code == "desjardins" and comptes[0].format == "rbc" and comptes[0].nom.startswith("RBC")
    source = tmp_path / "relevé.ofx"
    source.write_text(OFX_SGML, encoding="cp1252")
    code, cible = rp.ranger_releve(tmp_path, source, config_toml=config)
    assert code == "desjardins" and cible.parent.name == "releves_desjardins"  # compte de dépôt (banque RBC)
    td = tmp_path / "td.csv"
    td.write_text("TD Canada Trust\nDate,Description,Withdrawals,Deposits,Balance\n2026-09-01,FEE,1.00,,9.00\n",
                  encoding="utf-8")
    assert rp.ranger_releve(tmp_path, td, config_toml=config)[0] == "td1"
    assert rp.RegistreReleves(tmp_path, "td1").fichiers() == [tmp_path / "donnees" / "releves_td1" / "td.csv"]
    assert rp.nombre_releves(tmp_path) == 2
    inconnu = tmp_path / "cibc.csv"
    inconnu.write_text("CIBC\nDate,Description,Amount\n2026-09-01,FEE,-1.00\n", encoding="utf-8")
    with pytest.raises(ValueError, match="CIBC"):
        rp.ranger_releve(tmp_path, inconnu, config_toml={**config, "rapprochement": {"banque_depot": "rbc"}})
    with pytest.raises(ValueError, match="Format"):
        rp.ranger_releve(tmp_path, Path(tmp_path / "x.docx"), config_toml=config)


def test_interac_et_especes_de_toutes_les_banques():
    def m(texte, montant="10"):
        return rp.MouvementBanque("2026-09-01", texte, Decimal(montant))

    for texte in ("VRW Virement Interac de ALICE", "INTERAC e-Transfer from BOB", "E-TRANSFER AUTODEPOSIT",
                  "Virement Interac reçu", "Autodépôt Virement"):
        assert rp.est_interac(m(texte)), texte
    for texte in ("DGA Dépôt au GA", "ATM DEPOSIT", "ABM DEPOSIT 0042", "Dépôt au guichet", "BRANCH DEPOSIT"):
        assert rp.est_especes(m(texte)), texte
    assert not rp.est_especes(m("DEPOSIT CLOVER")) and not rp.est_interac(m("SEND E-TFR", "-10"))
    assert rp.est_salaire(m("PAYROLL DEPOSIT", "-500"))


def test_avis_interac_en_anglais():
    from mvogmbi_sync.paiements_courriel import DEPOSE, analyser

    avis = analyser("INTERAC e-Transfer: Your money transfer to LEOPOLD X was deposited.",
                    "Your transfer of $180.00 (CAD) to LEOPOLD X has been deposited.\nReference Number: CA1x2y3z\n"
                    "Memo: Invoice 14402")
    assert avis and avis.montant == Decimal("180.00") and avis.beneficiaire == "LEOPOLD X"
    assert avis.etat == DEPOSE and avis.reference == "CA1x2y3z" and avis.message == "Invoice 14402"


def _pdf(tmp_path, nom, lignes, entete_x):
    """PDF inventé : `lignes` = [(y, [(x, texte, aligné_à_droite)])] (mise en page des modèles publiés par les
    banques ; aucune donnée réelle)."""
    fpdf = pytest.importorskip("fpdf")
    pdf = fpdf.FPDF()
    pdf.add_page()
    arial = Path("C:/Windows/Fonts/arial.ttf")
    if arial.exists():  # apostrophe typographique et accents
        pdf.add_font("arial", "", str(arial))
        pdf.set_font("arial", size=8)
    else:
        pytest.skip("police Unicode absente")
    for y, cellules in lignes:
        for x, texte, droite in cellules:
            pdf.text(x - (pdf.get_string_width(texte) if droite else 0), y, texte)
    chemin = tmp_path / nom
    pdf.output(str(chemin))
    return chemin


def test_modele_rbc(tmp_path):
    """Modèle RBC (« Votre relevé de compte ») : solde d'ouverture avec apostrophe typographique, « ,15 », une
    ligne de solde pour plusieurs opérations, pied « 1 de 2 »."""
    d = lambda y, jour, texte, retrait="", depot="", solde="": (y, [(10, jour, False), (30, texte, False)] + [
        (x, v, True) for x, v in ((120, retrait), (150, depot), (185, solde)) if v])
    chemin = _pdf(tmp_path, "rbc.pdf", [
        (12, [(10, "Banque Royale du Canada  du 12 mars 2026 au 12 avril 2026", False)]),
        (20, [(10, "Date", False), (30, "Description", False), (120, "Retraits ($)", True), (150, "Dépôts ($)", True),
              (185, "Solde ($)", True)]),
        (26, [(30, "Solde d\u2019ouverture", False), (185, "4 247,14", True)]),
        d(32, "15 mars", "Virement", depot="85,00", solde="4 332,14"),
        d(38, "", "Intérêts payés", depot=",15"),
        d(44, "", "Retrait GAB", retrait="100,00"),
        d(50, "", "Achat Interac - Épicerie", retrait="47,82", solde="4 184,47"),
        d(56, "18 mars", "Chèque n° 30", retrait="40,00", solde="4 144,47"),
        (62, [(30, "Solde de clôture", False), (185, "4 144,47", True)]),
        (70, [(100, "1 de 2", False)])], None)
    r = rp.lire_releve(chemin)
    assert [m.montant for m in r.mouvements] == [Decimal("85.00"), Decimal("0.15"), Decimal("-100.00"),
                                                Decimal("-47.82"), Decimal("-40.00")]
    assert r.solde_ouverture == Decimal("4247.14") and not r.controles()
    assert all(not m.remarque for m in r.mouvements) and "1 de 2" not in r.mouvements[-1].description


def test_modele_uni_corrections_et_autres_comptes(tmp_path):
    """Modèle UNI : colonnes Frais / Retrait / Dépôt / Solde, frais remboursés (« Correction ») dont le sens vient
    du solde imprimé, notes dans la marge, compte d'épargne qui suit (ignoré)."""
    d = lambda y, jour, texte, x, v, solde: (y, [(10, jour, False), (30, texte, False), (x, v, True),
                                                 (175, solde, True), (182, "note", False)])
    chemin = _pdf(tmp_path, "uni.pdf", [
        (12, [(10, "Caisse populaire acadienne  Pour la période 03-01 à 03-31 2026", False)]),
        (20, [(10, "Date", False), (30, "Description", False), (110, "Frais", True), (130, "Retrait", True),
              (150, "Dépôt", True), (175, "Solde", True)]),
        (26, [(10, "1 mars", False), (30, "Solde reporté", False), (175, "47.07", True)]),
        d(32, "1 mars", "Virement Frais", 110, "1.25", "45.82"),
        d(38, "2 mars", "Correction : Virement Frais", 110, "1.25", "47.07"),
        d(44, "31 mars", "Virement Interac reçu ALICE", 150, "20.00", "67.07"),
        (50, [(10, "31 mars", False), (30, "Solde courant", False), (175, "67.07", True)]),
        (58, [(10, "000111001157 Épargne à terme", False)]),
        (64, [(10, "Date", False), (30, "Description", False), (110, "Frais", True), (130, "Retrait", True),
              (150, "Dépôt", True), (175, "Solde", True)]),
        (70, [(10, "1 mars", False), (30, "Retrait", False), (130, "99.00", True), (175, "1.00", True)])], None)
    r = rp.lire_releve(chemin)
    assert [m.montant for m in r.mouvements] == [Decimal("-1.25"), Decimal("1.25"), Decimal("20.00")]
    assert (r.debut, r.fin) == ("2026-03-01", "2026-03-31") and not r.controles()
    assert "note" not in " ".join(m.description for m in r.mouvements) and rp.est_interac(r.mouvements[2])
    assert detecter("Caisse populaire acadienne ltée (UNI)") == "caisseuni"


def test_modele_td_date_apres_les_montants(tmp_path):
    """Modèle TD : « Description Withdrawals Deposits Date Balance », date « MAR04 » après les montants,
    « STARTING BALANCE », « BALANCE FORWARD » repris à la page suivante."""
    d = lambda y, texte, x, v, jour, solde="": (y, [(10, texte, False), (x, v, True), (150, jour, False)]
                                               + ([(190, solde, True)] if solde else []))
    chemin = _pdf(tmp_path, "td.pdf", [
        (12, [(10, "TD Canada Trust   MAR 31/26 - APR 30/26", False)]),
        (20, [(10, "Description", False), (110, "Withdrawals", True), (140, "Deposits", True), (150, "Date", False),
              (190, "Balance", True)]),
        (26, [(10, "STARTING BALANCE", False), (150, "MAR31", False), (190, "1,000.00", True)]),
        d(32, "MONTHLY ACCOUNT FEE", 110, "4.00", "APR01", "996.00"),
        d(38, "E-TRANSFER RECEIVED", 140, "1,250.40", "APR04", "2,246.40"),
        d(44, "CHQ#00012", 110, "46.40", "APR04", "2,200.00")], None)
    r = rp.lire_releve(chemin)
    assert [(m.date[5:], m.montant) for m in r.mouvements] == [("04-01", Decimal("-4.00")),
                                                              ("04-04", Decimal("1250.40")),
                                                              ("04-04", Decimal("-46.40"))]
    assert r.solde_ouverture == Decimal("1000.00") and not r.controles() and rp.est_interac(r.mouvements[1])
    assert r.mouvements[0].description == "MONTHLY ACCOUNT FEE"


def test_modele_colonne_montant_unique_et_dollar(tmp_path):
    """Colonne « Amount » signée (Tangerine) et montants précédés de « $ » (Scotia)."""
    chemin = _pdf(tmp_path, "tangerine.pdf", [
        (12, [(10, "Tangerine  Statement period: Sep 1, 2026 to Sep 30, 2026", False)]),
        (20, [(10, "Date", False), (40, "Transaction Description", False), (150, "Amount", True),
              (190, "Balance", True)]),
        (26, [(10, "Sep 1", False), (40, "Opening Balance", False), (190, "$271.49", True)]),
        (32, [(10, "Sep 3", False), (40, "INTERAC e-Transfer From: BOB", False), (150, "$50.00", True),
              (190, "$321.49", True)]),
        (38, [(10, "Sep 9", False), (40, "Bill Payment HYDRO", False), (150, "-$21.49", True),
              (190, "$300.00", True)])], None)
    r = rp.lire_releve(chemin)
    assert [m.montant for m in r.mouvements] == [Decimal("50.00"), Decimal("-21.49")]
    assert r.solde_ouverture == Decimal("271.49") and r.solde_fermeture == Decimal("300.00") and not r.controles()
