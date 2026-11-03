"""3e vague (demandes du propriétaire du 2026-11-01) : audit, pertes, étiquettes, filtres, plan comptable."""
import json
from decimal import Decimal as D

from mvogmbi_sync import audit, etiquettes, pertes as pe, plan_comptable as pc
from mvogmbi_sync.design import choix_multiples
from mvogmbi_sync.statistiques_clover import DonneesClover, filtrer, fusionner


def test_audit_chaine_et_alteration(tmp_path):
    audit.noter(tmp_path, "Connexion", "Connexion", utilisateur="Patron")
    audit.noter(tmp_path, "🗑 Supprimer", "Pertes et démarque", "PE-0001", utilisateur="Patron")
    entrees = audit.lire(tmp_path)
    assert [e.action for e in entrees] == ["Connexion", "🗑 Supprimer"] and audit.verifier(entrees) == []
    chemin = tmp_path / "donnees" / audit.FICHIER
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    altere = json.loads(lignes[0])
    altere["utilisateur"] = "Autre"
    chemin.write_text(json.dumps(altere) + "\n" + lignes[1] + "\n", encoding="utf-8")
    assert audit.verifier(audit.lire(tmp_path)) == [0]  # la ligne changée se voit


def test_plan_comptable_controle():
    connus = {"1000": pc.Compte("1000", "Actifs", "H", False, D(0)), "1055": pc.Compte("1055", "Banque", "R", False, D(0)),
              "5700": pc.Compte("5700", "Frais", "R", True, D(0))}
    assert pc.problemes(["1055"], connus) == []
    erreurs = pc.problemes(["1000", "5700", "9999"], connus)
    assert len(erreurs) == 3 and "en-tête" in erreurs[0] and "inactif" in erreurs[1] and "absent" in erreurs[2]
    assert pc.problemes(["9999"], {}) == []  # plan illisible : aucune opération bloquée


class CloverFactice:
    def __init__(self):
        self.stocks = {"X1": D(10)}

    def stock(self, i):
        return self.stocks[i]

    def regler_stock(self, i, q):
        self.stocks[i] = q


def test_perte_annulee_rend_le_stock_clover(tmp_path):
    clover = CloverFactice()
    r = pe.Registre(tmp_path)
    p = pe.nouvelle(r, "2026-11-01", pe.MOTIFS[0], [pe.LignePerte("X1", "Riz", "3", "2")])
    pe.appliquer(tmp_path, {}, p.numero, client=clover)
    assert clover.stocks["X1"] == D(7)
    p = pe.annuler(tmp_path, {}, p.numero, client=clover)
    assert clover.stocks["X1"] == D(10) and pe.est_annulee(p)
    lignes, total = pe.rapport(pe.Registre(tmp_path).pertes, __import__("datetime").date(2026, 1, 1),
                               __import__("datetime").date(2026, 12, 31))
    assert total == 0  # une perte annulée ne compte plus


def test_etiquettes_ticket():
    assert list(etiquettes.formats([("EPSON TM-T20", 80)]))[0] == "Ticket 80 mm — EPSON TM-T20"
    page = etiquettes.page([etiquettes.Etiquette("Riz", D("5.99"), "", "123")], imprimer=False, largeur_ticket=58)
    assert "size: 58mm 38mm" in page and "5,99 $" in page


def test_filtres_multiples_et_points_de_vente():
    assert choix_multiples("Riz | Mil") == ["Riz", "Mil"] and choix_multiples("") == []
    commande = lambda i, e: {"id": i, "employee": {"name": e}, "lineItems": {"elements": []}}
    d = DonneesClover(commandes=[commande("A", "Ana"), commande("B", "Bob"), commande("C", "Cy")])
    assert [c["id"] for c in filtrer(d, {"Employé": "Ana | Cy"}).commandes] == ["A", "C"]
    deux = fusionner([DonneesClover(commandes=[commande("A", "Ana")]), DonneesClover(commandes=[commande("B", "Bob")])])
    assert [c["id"] for c in deux.commandes] == ["A", "B"]
