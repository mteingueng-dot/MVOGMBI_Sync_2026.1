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



def test_acces_par_fonction_et_droit_supprimer(tmp_path, monkeypatch):
    """Accès par fonction (2026-10-30) : « Liste des articles » seule, sans le reste de la rubrique Articles ;
    droit « Supprimer » sur tous les boutons Supprimer / 🗑."""
    from mvogmbi_sync import design
    from mvogmbi_sync.interface import Application
    from mvogmbi_sync.utilisateurs import ACTIONS_FENETRES, Registre, Utilisateur

    assert "Supprimer" in ACTIONS_FENETRES["Général"]
    registre = Registre(tmp_path)
    registre.definir_profil("Magasin", ["accueil"])
    registre.definir_acces("Magasin", ["Liste des articles", "tableau"], ["correspondance", "tableau"])
    registre.definir_fonctions("Magasin", ["Supprimer"])
    registre.enregistrer()
    relu = Registre(tmp_path)
    u = Utilisateur("x", "Magasin")
    assert relu.permises(u) == {"Liste des articles", "tableau", "accueil"}
    assert relu.pages(u) >= {"correspondance", "tableau"}
    assert relu.permises(Utilisateur("y", "Comptable")) is None  # ancien modèle conservé

    faux = type("F", (), {})()
    faux._fonctions, faux._refusees = relu.permises(u), relu.refusees(u)
    faux.permis = lambda index: True
    liste = ("📚", "Liste des articles", 5, "ouvrir_liste", "articles")
    creer = ("🆕", "Créer un article", 5, "ouvrir_creation_article")
    assert Application.permis_action(faux, liste) and not Application.permis_action(faux, creer)
    assert Application.au_menu(faux, 6) and not Application.au_menu(faux, 5)  # Tableau oui, Correspondance non

    assert design.est_suppression("🗑  Supprimer") and design.est_suppression("🗑")
    assert not design.est_suppression("💾  Enregistrer")
    messages, faits = [], []
    monkeypatch.setattr("tkinter.messagebox.showwarning", lambda *a, **k: messages.append(a))
    racine = tk.Tk()
    racine.withdraw()
    try:
        racine.permis_fenetre = lambda action: action != "Supprimer"
        bouton = design.Bouton(racine, "🗑  Supprimer", lambda: faits.append(1))
        bouton.pack()
        racine.update()
        bouton._clic(type("E", (), {"x": 0, "y": 0})())
        assert not faits and messages
        racine.permis_fenetre = lambda action: True
        bouton._clic(type("E", (), {"x": 0, "y": 0})())
        assert faits == [1]
    finally:
        racine.destroy()
