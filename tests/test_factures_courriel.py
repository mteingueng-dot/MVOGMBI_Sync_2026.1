from datetime import date
from email.message import EmailMessage

from mvogmbi_sync import factures_courriel as fc


def courriel(expediteur: str, sujet: str, pieces: list[tuple[str, bytes]]) -> EmailMessage:
    m = EmailMessage()
    m["From"], m["Subject"], m["Date"] = expediteur, sujet, "Tue, 27 Oct 2026 09:15:00 -0400"
    m["Message-ID"] = "<abc@exemple>"
    m.set_content("Bonjour, voici la facture.")
    for nom, contenu in pieces:
        m.add_attachment(contenu, maintype="application", subtype="octet-stream", filename=nom)
    return m


def test_pieces_retenues_selon_expediteur_ou_mot_facture():
    m = courriel("Grossiste <factures@grossiste.ca>", "Votre commande", [("14402.pdf", b"%PDF-1"), ("logo.gif", b"x")])
    assert fc.pieces_du_message(m, "<abc@exemple>", []) == []  # ni « facture » ni expéditeur choisi
    (p,) = fc.pieces_du_message(m, "<abc@exemple>", ["grossiste.ca"])  # le .gif n'est pas une facture
    assert (p.nom, p.expediteur, p.recu, p.cle) == ("14402.pdf", "factures@grossiste.ca", date(2026, 10, 27),
                                                     "<abc@exemple>|14402.pdf")
    m2 = courriel("x@autre.com", "Facture 14402", [("doc.pdf", b"%PDF-2")])
    assert [p.nom for p in fc.pieces_du_message(m2, "<m2>", [])] == ["doc.pdf"]
    assert fc.pieces_du_message(m2, "<m2>", ["grossiste.ca"]) == []
    assert not fc.retenue("notify@payments.interac.ca", "Facture", "avis.pdf", [])  # jamais les avis Interac
    assert fc.nom_fichier(p) == "2026-10-27_grossiste.ca_14402.pdf"


def test_recuperer_une_seule_fois(tmp_path, monkeypatch):
    m = courriel("factures@grossiste.ca", "Facture", [("14402.pdf", b"%PDF-1 facture")])
    lues = []

    def boite(*args, **kwargs):
        lues.append(kwargs.get("deja", args[-1] if args else None))
        return fc.pieces_du_message(m, "<abc@exemple>", ["grossiste.ca"])

    monkeypatch.setattr(fc, "lire_boite", lambda *a, **k: boite(*a, **k))
    monkeypatch.setattr("mvogmbi_sync.coffre.lire", lambda *a, **k: "secret")
    config = {"boite_paiements": {"serveur": "imap.exemple", "utilisateur": "u@exemple", "depuis": "2026-10-01"},
              "factures_courriel": {"expediteurs": "grossiste.ca"}}
    (cree,) = fc.recuperer(tmp_path, config)
    assert cree.name == "2026-10-27_grossiste.ca_14402.pdf" and cree.read_bytes() == b"%PDF-1 facture"
    assert fc.recuperer(tmp_path, config) == []  # déjà prise, même si le fichier est écarté ensuite
    cree.unlink()
    assert fc.recuperer(tmp_path, config) == []
    assert fc.Memoire(tmp_path).prises["<abc@exemple>|14402.pdf"]["fichier"] == cree.name
