from datetime import date, datetime
from decimal import Decimal as D
from types import SimpleNamespace

from mvogmbi_sync import paquet3 as p3


class CloverFactice:
    def __init__(self, prix):
        self.prix = dict(prix)
        self.ecrits = []

    def _get(self, chemin):
        ident = chemin.split("/")[-1]
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"price": int(self.prix[ident] * 100)})

    def regler_prix(self, ident, prix):
        self.ecrits.append((ident, prix))
        self.prix[ident] = prix


def test_inventaire_tournant():
    plan = p3.plan_tournant(["Riz", "Épices", "Fruits", "Riz", "", "Huiles"], 2)
    assert sorted(sum(plan, [])) == ["Fruits", "Huiles", "Riz", "Épices"] and len(plan) == 2
    assert all(len(semaine) == 2 for semaine in plan)
    assert p3.semaine_du_cycle(date(2026, 10, 29), 8) == date(2026, 10, 29).isocalendar()[1] % 8


def test_promotion_debut_et_fin(tmp_path):
    registre = p3.Promotions(tmp_path)
    p = registre.ajouter("I1", "Riz", D("8.99"), date(2026, 11, 2), date(2026, 11, 8), "gérant")
    try:
        p3.Promotions(tmp_path).ajouter("I1", "Riz", D("7"), date(2026, 11, 5), date(2026, 11, 10))
        assert False, "chevauchement refusé"
    except ValueError:
        pass
    clover = CloverFactice({"I1": D("10.99")})
    assert p3.appliquer_promotions(tmp_path, clover, date(2026, 11, 1)) == []           # pas encore
    p3.appliquer_promotions(tmp_path, clover, date(2026, 11, 2))
    assert clover.prix["I1"] == D("8.99") and p3.Promotions(tmp_path).liste[0].prix_normal == "10.99"
    p3.appliquer_promotions(tmp_path, clover, date(2026, 11, 9))
    assert clover.prix["I1"] == D("10.99") and p3.Promotions(tmp_path).liste[0].etat == p3.TERMINEE
    # prix changé à la main pendant la promotion : jamais écrasé à la fin
    p2 = p3.Promotions(tmp_path).ajouter("I2", "Huile", D("4"), date(2026, 11, 2), date(2026, 11, 3))
    clover2 = CloverFactice({"I2": D("5")})
    p3.appliquer_promotions(tmp_path, clover2, date(2026, 11, 2))
    clover2.prix["I2"] = D("4.50")
    p3.appliquer_promotions(tmp_path, clover2, date(2026, 11, 4))
    assert clover2.prix["I2"] == D("4.50") and "laissé tel quel" in p3.Promotions(tmp_path).liste[-1].messages[-1]
    assert p.numero == "PR-0001" and p2.numero == "PR-0002"


def test_clients_pro_et_relance(tmp_path):
    f1 = SimpleNamespace(tiers="Resto A", numero="F1", date=date(2026, 9, 1), echeance=date(2026, 9, 30),
                         solde=D("500"), retard=29)
    f2 = SimpleNamespace(tiers="Resto A", numero="F2", date=date(2026, 8, 1), echeance=date(2026, 8, 31),
                         solde=D("300"), retard=59)
    c = p3.ClientPro("Resto A", "a@exemple.test", D("600"), D("800"), D("800"), D("300"), [f1, f2])
    assert c.depasse
    entetes, lignes, sous = p3.lettre_relance(c, date(2026, 10, 29))
    assert len(lignes) == 3 and lignes[-1][-1] == "800,00 $" and "Resto A" in sous
    p3.noter_relance(tmp_path, "Resto A", D("800"), "courriel")
    assert p3.derniere_relance(tmp_path) == {"Resto A": date.today().isoformat()}
    page = p3.page_telephone("<p>résumé</p>", ["Caisse non comptée"], datetime(2026, 10, 29, 6, 0))
    assert "width=device-width" in page and "Caisse non comptée" in page
