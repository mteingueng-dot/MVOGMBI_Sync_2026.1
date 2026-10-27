from datetime import date, datetime

from mvogmbi_sync.automatique import jours_couverts_sage, resumer_jours


def test_facture_mal_numerotee_ignoree():
    lignes = [{"s": "Vente 2026-06-07", "d": datetime(2025, 6, 7)},       # faute de frappe : 2026 au lieu de 2025
              {"s": "Vente 2026-06-08", "d": datetime(2026, 6, 8)},
              {"s": "Vente 2026-06-12/14", "d": datetime(2026, 6, 14)}]  # fin de semaine datée du dimanche
    dates, incoherentes = jours_couverts_sage(lignes)
    assert dates == {date(2026, 6, 8), date(2026, 6, 12), date(2026, 6, 13), date(2026, 6, 14)}
    assert incoherentes == ["Vente 2026-06-07 (datée du 2025-06-07 dans Sage)"]
    assert max(dates) == date(2026, 6, 14)


def test_jours_manquants_resumes():
    jours = [date(2026, 2, 1), date(2026, 2, 2), date(2026, 2, 3), date(2026, 2, 10), date(2026, 3, 1),
             date(2026, 3, 2)]
    assert resumer_jours(jours) == "2026-02-01 → 2026-02-03, 2026-02-10, 2026-03-01 → 2026-03-02"


def test_une_piece_jointe_excel_par_module():
    from decimal import Decimal

    from mvogmbi_sync.automatique import BLOQUEE, IMPORTEE, CompteRendu, EtatJour
    from mvogmbi_sync.courriel import pieces_jointes

    cr = CompteRendu()
    cr.note("Lecture de Sage…")
    cr.jours = [EtatJour(date(2026, 6, 1), IMPORTEE, "", 99, Decimal("1497.63"), Decimal("25.35"), Decimal("1522.98")),
                EtatJour(date(2026, 7, 2), BLOQUEE, "article non relié")]
    cr.problemes = ["Vente 2026-07-02 : article non relié", "Encaissement : Interac : aucune facture"]
    cr.encaissements = ["Dépôt du 2026-06-02 : 1 000,00 $"]
    noms = [nom.split("_20")[0] for nom, _ in pieces_jointes(cr)]
    assert noms == ["Ventes", "Encaissements", "Journal"]  # pas de paiements fournisseurs cette nuit-là
