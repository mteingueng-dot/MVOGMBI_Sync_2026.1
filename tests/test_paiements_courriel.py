from datetime import date
from decimal import Decimal as D

from mvogmbi_sync.paiements_courriel import ANNULE, DEPOSE, EXPIRE, analyser, numeros_cites

# Texte inventé, au format des avis Interac de Desjardins (aucune vraie donnée dans le dépôt public)
SUJET = "Virement Interac : Votre virement de 180,00 $ à JEAN EXEMPLE a été déposé avec succès."
CORPS = """Bonjour MARCHE TEST INC.,
Le virement que vous avez envoyé à JEAN EXEMPLE a été déposé.
Le virement de 180,00 $ (CAD) que vous avez envoyé à JEAN EXEMPLE a été déposé.
Précisions sur le virement
Date :
20 août 2026
Numéro de référence :
CAtest12
Message :
Facture 14402 du 20/08/2026
"""


def test_avis_depose():
    a = analyser(SUJET, CORPS, "<id-1>", date(2026, 8, 20))
    assert (a.etat, a.montant, a.beneficiaire) == (DEPOSE, D("180.00"), "JEAN EXEMPLE")
    assert (a.date_virement, a.reference, a.message) == ("2026-08-20", "CAtest12", "Facture 14402 du 20/08/2026")
    assert a.numeros_facture == ["14402"]


def test_avis_annule_et_expire():
    annule = analyser("Virement Interac : Votre virement de 1 250,50 $ à JEAN EXEMPLE a été annulé.", "")
    assert (annule.etat, annule.montant) == (ANNULE, D("1250.50"))
    expire = analyser("Virement Interac : Votre virement de 75,00 $ à JEAN EXEMPLE a expiré.", "")
    assert expire.etat == EXPIRE


def test_autre_courriel_ignore():
    assert analyser("Votre relevé est disponible", "Bonjour") is None


def test_numeros_de_facture_cites():
    assert numeros_cites("Facture 14402 du 20/08/2026") == ["14402"]
    assert "104202" in "".join(numeros_cites("Paiement FA-104202"))
    assert numeros_cites("Merci !") == []
