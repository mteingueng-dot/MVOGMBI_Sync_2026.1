import tkinter as tk


def test_action_refusee_dans_une_fenetre(tmp_path, monkeypatch):
    from mvogmbi_sync import design
    from mvogmbi_sync.utilisateurs import ACTIONS_FENETRES, Registre

    assert "Traiter la paie dans Sage" in ACTIONS_FENETRES["Paie"]
    registre = Registre(tmp_path)
    registre.definir_fonctions("Comptable", ["Traiter la paie dans Sage", "Restaurer une sauvegarde"])
    registre.enregistrer()
    assert {"Traiter la paie dans Sage", "Restaurer une sauvegarde"} <= set(Registre(tmp_path).fonctions_refusees["Comptable"])
    messages = []
    monkeypatch.setattr("tkinter.messagebox.showwarning", lambda *a, **k: messages.append(a))
    racine = tk.Tk()
    racine.withdraw()
    try:
        assert design.action_permise(racine, "Traiter la paie dans Sage")      # hors de l'application : permise
        racine.permis_fenetre = lambda action: action != "Traiter la paie dans Sage"
        assert not design.action_permise(racine, "Traiter la paie dans Sage") and messages
        assert design.action_permise(racine, "Imprimer des étiquettes")
    finally:
        racine.destroy()

