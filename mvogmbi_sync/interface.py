"""Interface graphique d'installation et de suivi de MVOGMBI_Sync (tkinter, incluse avec Python).

Onglets : Accueil, Clover, Sage, Courriel, Automatisation, Correspondance des articles, Tableau de bord, Aide / FAQ.
Langues : français et anglais (sélecteur dans l'en-tête, enregistré dans config.toml [general] langue).
Les secrets (jeton Clover, mots de passe) vont dans le coffre-fort de Windows, jamais dans config.toml.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import tomllib
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import coffre, langues
from .langues import t

TITRE = "MVOGMBI_Sync — Clover → Sage 50"
MASQUE = "••••••••"  # affiché quand un secret est déjà enregistré dans le coffre
VERT = "#1a9b3c"


# --------------------------------------------------------------------------------------------- configuration
def lire_config(chemin: Path) -> dict:
    return tomllib.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def _valeur_toml(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    texte = str(v)
    if "'" not in texte and "\n" not in texte:
        return f"'{texte}'"  # chaîne littérale : les « \\ » des chemins Windows restent tels quels
    return '"' + texte.replace("\\", "\\\\").replace('"', '\\"') + '"'


def ecrire_config(chemin: Path, config: dict) -> None:
    lignes = ["# Configuration de MVOGMBI_Sync (modifiée par l'application de configuration).",
              "# Les secrets sont dans le coffre-fort de Windows, pas dans ce fichier.", ""]
    for section, valeurs in config.items():
        lignes.append(f"[{section}]")
        for cle, valeur in valeurs.items():
            lignes.append(f"{cle} = {_valeur_toml(valeur)}")
        lignes.append("")
    chemin.write_text("\n".join(lignes), encoding="utf-8")


# --------------------------------------------------------------------------------------------- application
class Application(tk.Tk):
    def __init__(self, racine: Path):
        super().__init__()
        self.racine = racine
        self.relancer = False
        self.chemin_config = racine / "config.toml"
        self.config_toml = lire_config(self.chemin_config)
        langues.depuis_config(self.config_toml)
        self.file_messages: queue.Queue = queue.Queue()
        self.title(TITRE)
        self.geometry("1060x780")
        self.minsize(780, 580)
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        entete = ttk.Frame(self, padding=(12, 8))
        entete.pack(fill="x")
        self._images = self._charger_logo()
        if self._images:
            self.iconphoto(True, self._images["icone"])
            ttk.Label(entete, image=self._images["entete"]).pack(side="left", padx=(0, 14))
        textes = ttk.Frame(entete)
        textes.pack(side="left", fill="x", expand=True)
        ttk.Label(textes, text=t("Marché MVOG-MBI Sherbrooke"), font=("Segoe UI", 15, "bold"),
                  foreground=VERT).pack(anchor="w")
        ttk.Label(textes, text=t("Synchronisation des ventes Clover → Sage 50"),
                  font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(textes, text=t("Chaque nuit, les ventes Clover sont importées dans Sage 50 : une facture par jour."),
                  foreground="#555").pack(anchor="w")
        choix = ttk.Frame(entete)
        choix.pack(side="right", anchor="n")
        ttk.Label(choix, text="Langue / Language").pack(anchor="e")
        self.langue = tk.StringVar(value=langues.LANGUES[langues.courante()])
        selecteur = ttk.Combobox(choix, textvariable=self.langue, values=list(langues.LANGUES.values()),
                                 state="readonly", width=12)
        selecteur.pack(anchor="e")
        selecteur.bind("<<ComboboxSelected>>", lambda _e: self.changer_langue())

        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.vars: dict[str, tk.Variable] = {}
        self._onglet_texte(t("Accueil"), "accueil")
        self._onglet_clover()
        self._onglet_sage()
        self._onglet_courriel()
        self._onglet_automatisation()
        self._onglet_correspondance()
        self._onglet_tableau()
        self._onglet_texte(t("Aide / FAQ"), "faq")

        bas = ttk.Frame(self, padding=(12, 0, 12, 10))
        bas.pack(fill="x")
        ttk.Button(bas, text=t("Enregistrer la configuration"), command=self.enregistrer).pack(side="right")
        self.etat = ttk.Label(bas, text="", foreground="#555")
        self.etat.pack(side="left")
        self._attente = self.after(200, self._relayer_messages)
        self.actualiser_tableau()

    @staticmethod
    def _charger_logo() -> dict:
        """Logo du marché (en-tête) et icône de la fenêtre ; rien si l'image est introuvable."""
        try:
            from PIL import Image, ImageTk

            logo = Image.open(Path(__file__).resolve().parent / "ressources" / "logo.png").convert("RGBA")
            entete = logo.copy()
            entete.thumbnail((90, 90), Image.LANCZOS)
            largeur, hauteur = logo.size
            icone = logo.crop((0, 0, largeur, int(hauteur * 0.76)))
            icone.thumbnail((64, 64), Image.LANCZOS)
            grand = logo.copy()
            grand.thumbnail((200, 260), Image.LANCZOS)
            return {"entete": ImageTk.PhotoImage(entete), "icone": ImageTk.PhotoImage(icone),
                    "grand": ImageTk.PhotoImage(grand)}
        except Exception:
            return {}

    def changer_langue(self) -> None:
        code = next(c for c, nom in langues.LANGUES.items() if nom == self.langue.get())
        if code == langues.courante():
            return
        self.config_toml.setdefault("general", {})["langue"] = code
        ecrire_config(self.chemin_config, self.config_toml)
        self.relancer = True  # la fenêtre est reconstruite dans la nouvelle langue
        self.destroy()

    # ---------------------------------------------------------------- outils d'interface
    def _var(self, cle: str, valeur, type_=tk.StringVar) -> tk.Variable:
        self.vars[cle] = type_(value=valeur)
        return self.vars[cle]

    def _champ(self, parent, ligne: int, libelle: str, cle: str, valeur="", secret: str | None = None,
               aide: str = "", parcourir: tuple | None = None):
        ttk.Label(parent, text=libelle).grid(row=ligne, column=0, sticky="w", pady=4, padx=(0, 10))
        if secret:
            valeur = MASQUE if coffre.present(secret) else ""
        champ = ttk.Entry(parent, textvariable=self._var(cle, valeur), width=52, show="•" if secret else "")
        champ.grid(row=ligne, column=1, sticky="we", pady=4)
        if parcourir:
            ttk.Button(parent, text=t("Parcourir…"), command=lambda: self._parcourir(cle, *parcourir)).grid(
                row=ligne, column=2, padx=(6, 0))
        if aide:
            ttk.Label(parent, text=aide, foreground="#777", wraplength=560).grid(
                row=ligne + 1, column=1, sticky="w", pady=(0, 4))
        parent.columnconfigure(1, weight=1)
        return champ

    def _parcourir(self, cle: str, titre: str, types: list) -> None:
        chemin = filedialog.askopenfilename(title=titre, filetypes=types)
        if chemin:
            self.vars[cle].set(str(Path(chemin)))

    def _cadre(self, titre: str) -> ttk.Frame:
        cadre = ttk.Frame(self.onglets, padding=14)
        self.onglets.add(cadre, text=titre)
        return cadre

    def _titre(self, parent, texte: str) -> ttk.Label:
        etiquette = ttk.Label(parent, text=texte, font=("Segoe UI", 10, "bold"))
        etiquette.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        return etiquette

    def _sortie(self, parent, hauteur=12) -> tk.Text:
        return tk.Text(parent, height=hauteur, wrap="word", font=("Consolas", 9), relief="solid", borderwidth=1)

    def _tache(self, titre: str, fonction, zone: tk.Text | None = None) -> None:
        """Exécute une action longue en arrière-plan ; ses messages s'affichent dans `zone`."""
        self.etat.config(text=f"{titre}…")

        def travail():
            try:
                resultat = fonction()
                self.file_messages.put((zone, f"✔ {titre} : {resultat or t('terminé')}"))
            except Exception as exc:
                self.file_messages.put((zone, f"✘ {titre} : {exc}"))
            self.file_messages.put((None, ""))

        threading.Thread(target=travail, daemon=True).start()

    def _relayer_messages(self) -> None:
        try:
            while True:
                zone, texte = self.file_messages.get_nowait()
                if zone is None:
                    self.etat.config(text=texte)
                    self.actualiser_tableau()
                else:
                    zone.insert("end", texte + "\n")
                    zone.see("end")
        except queue.Empty:
            pass
        self._attente = self.after(200, self._relayer_messages)

    def destroy(self) -> None:
        try:
            self.after_cancel(self._attente)
        except Exception:
            pass
        super().destroy()

    # ---------------------------------------------------------------- pages Accueil et Aide
    def _onglet_texte(self, titre_onglet: str, page: str) -> None:
        from .aide import ACCUEIL, FAQ

        blocs = (ACCUEIL if page == "accueil" else FAQ)[langues.courante()]
        cadre = ttk.Frame(self.onglets, padding=(14, 10))
        self.onglets.add(cadre, text=titre_onglet)
        if page == "accueil" and self._images:
            ttk.Label(cadre, image=self._images["grand"]).pack(side="left", anchor="n", padx=(0, 18))
        zone = tk.Text(cadre, wrap="word", relief="flat", background="white",
                       padx=18, pady=12, font=("Segoe UI", 10), cursor="arrow", spacing1=2, spacing3=2)
        defilement = ttk.Scrollbar(cadre, orient="vertical", command=zone.yview)
        zone.configure(yscrollcommand=defilement.set)
        defilement.pack(side="right", fill="y")
        zone.pack(side="left", fill="both", expand=True)
        zone.tag_configure("titre", font=("Segoe UI", 16, "bold"), foreground=VERT, spacing3=10)
        zone.tag_configure("sous_titre", font=("Segoe UI", 12, "bold"), spacing1=14, spacing3=4)
        zone.tag_configure("para", spacing3=6)
        zone.tag_configure("etape", lmargin1=12, lmargin2=30, spacing3=4)
        zone.tag_configure("puce", lmargin1=12, lmargin2=28, spacing3=3)
        zone.tag_configure("question", font=("Segoe UI", 10, "bold"), foreground="#1b5e9f", spacing1=12)
        zone.tag_configure("reponse", lmargin1=12, lmargin2=12, spacing3=4)
        for type_bloc, texte in blocs:
            prefixe = "•  " if type_bloc == "puce" else ("Q.  " if type_bloc == "question" else "")
            zone.insert("end", prefixe + texte + "\n", type_bloc)
        zone.configure(state="disabled")

    # ---------------------------------------------------------------- onglets de configuration
    def _onglet_clover(self) -> None:
        c = self.config_toml.get("clover", {})
        f = self._cadre(t("1. Clover"))
        self._titre(f, t("Accès à votre compte Clover (lecture des ventes)"))
        self._champ(f, 1, t("Identifiant marchand"), "clover.merchant_id", c.get("merchant_id", ""),
                    aide=t("13 caractères, visibles dans l'adresse du tableau de bord Clover après « /m/ »."))
        self._champ(f, 3, t("Jeton API"), "secret.clover", secret=coffre.CLOVER_JETON,
                    aide=t("Clover > Compte et configuration > Jetons API (droits en lecture). "
                           "Laissez « •••• » pour conserver le jeton enregistré."))
        self.sortie_clover = self._sortie(f, 6)
        ttk.Button(f, text=t("Tester la connexion à Clover"), command=self.tester_clover).grid(
            row=5, column=1, sticky="w", pady=8)
        self.sortie_clover.grid(row=6, column=0, columnspan=3, sticky="nsew")
        f.rowconfigure(6, weight=1)

    def _onglet_sage(self) -> None:
        b, i, a = (self.config_toml.get(s, {}) for s in ("sage_base", "sage_import", "automatique"))
        f = self._cadre(t("2. Sage 50"))
        self._titre(f, t("Fichier d'entreprise et comptes Sage"))
        types = [(t("Fichier d'entreprise Sage"), "*.SAI"), (t("Tous les fichiers"), "*.*")]
        self._champ(f, 1, t("Fichier d'entreprise (.SAI)"), "sage.fichier", i.get("fichier_entreprise", ""),
                    aide=t("Le fichier dans lequel les factures sont importées. Pour les essais : une COPIE."),
                    parcourir=(t("Fichier d'entreprise Sage"), types))
        self._champ(f, 3, t("Utilisateur Sage (lecture)"), "sage.utilisateur", b.get("utilisateur", "mvogmbi_sync"),
                    aide=t("Utilisateur avec « Droits d'accès aux produits tiers : Consultation seule » "
                           "et accès Vue aux modules Stocks & Services et Clients & Ventes."))
        self._champ(f, 5, t("Mot de passe (lecture)"), "secret.sage_lecture", secret=coffre.SAGE_LECTURE)
        self._champ(f, 6, t("Mot de passe Sage pour l'import"), "secret.sage_import", secret=coffre.SAGE_IMPORT,
                    aide=t("Mot de passe demandé par la fenêtre « Sage 50 - Password » de l'import (utilisateur sysadmin)."))
        self._champ(f, 8, t("Premier jour à importer"), "auto.date_depart", a.get("date_depart", date.today().isoformat()),
                    aide=t("AAAA-MM-JJ. Utilisé seulement si Sage ne contient encore aucune facture « Vente AAAA-MM-JJ »."))
        self.sortie_sage = self._sortie(f, 6)
        ttk.Button(f, text=t("Tester l'accès à Sage"), command=self.tester_sage).grid(row=10, column=1, sticky="w", pady=8)
        self.sortie_sage.grid(row=11, column=0, columnspan=3, sticky="nsew")
        f.rowconfigure(11, weight=1)

    def _onglet_courriel(self) -> None:
        c = self.config_toml.get("courriel", {})
        f = self._cadre(t("3. Courriel"))
        self._titre(f, t("Alertes par courriel"))
        self._champ(f, 1, t("Serveur d'envoi (SMTP)"), "courriel.serveur", c.get("serveur", ""),
                    aide=t("Ex. smtp.office365.com (Outlook) ou smtp.gmail.com (Gmail : mot de passe d'application)."))
        self._champ(f, 3, t("Port"), "courriel.port", str(c.get("port", 587)))
        ttk.Label(f, text=t("Sécurité")).grid(row=4, column=0, sticky="w", pady=4)
        ttk.Combobox(f, textvariable=self._var("courriel.securite", c.get("securite", "starttls")),
                     values=["starttls", "ssl", "aucune"], state="readonly", width=12).grid(row=4, column=1, sticky="w")
        self._champ(f, 5, t("Utilisateur"), "courriel.utilisateur", c.get("utilisateur", ""))
        self._champ(f, 6, t("Mot de passe"), "secret.courriel", secret=coffre.COURRIEL)
        self._champ(f, 7, t("Expéditeur"), "courriel.expediteur", c.get("expediteur", ""))
        self._champ(f, 8, t("Destinataire(s)"), "courriel.destinataires", c.get("destinataires", ""),
                    aide=t("Une ou plusieurs adresses séparées par des virgules."))
        ttk.Checkbutton(f, text=t("Envoyer le compte rendu après chaque traitement, y compris en cas de succès "
                                  "(dates traitées et leur état)"),
                        variable=self._var("courriel.envoyer_si_succes", bool(c.get("envoyer_si_succes", True)),
                                           tk.BooleanVar)).grid(row=10, column=1, sticky="w", pady=6)
        self.sortie_courriel = self._sortie(f, 4)
        ttk.Button(f, text=t("Envoyer un courriel de test"), command=self.tester_courriel).grid(
            row=11, column=1, sticky="w", pady=6)
        self.sortie_courriel.grid(row=12, column=0, columnspan=3, sticky="nsew")
        f.rowconfigure(12, weight=1)

    def _onglet_automatisation(self) -> None:
        a = self.config_toml.get("automatique", {})
        f = self._cadre(t("4. Automatisation"))
        self._titre(f, t("Traitement automatique quotidien"))
        self._champ(f, 1, t("Heure du traitement"), "auto.heure", a.get("heure", "01:00"),
                    aide=t("HH:MM. L'ordinateur doit être allumé et la session Windows ouverte ; Sage peut être fermé."))
        boutons = ttk.Frame(f)
        boutons.grid(row=3, column=1, sticky="w", pady=8)
        ttk.Button(boutons, text=t("Installer la tâche planifiée"), command=self.installer_tache).pack(side="left")
        ttk.Button(boutons, text=t("Retirer la tâche"), command=self.retirer_tache).pack(side="left", padx=6)
        ttk.Button(boutons, text=t("État de la tâche"), command=self.etat_tache).pack(side="left")
        ttk.Button(boutons, text=t("Créer un raccourci sur le Bureau"), command=self.raccourci).pack(side="left", padx=6)
        ttk.Button(f, text=t("Reprendre une configuration existante…"), command=self.reprendre).grid(
            row=5, column=1, sticky="w", pady=(8, 0))
        ttk.Label(f, text=t("Copie config.toml, la correspondance des articles et les articles à relier depuis un "
                            "autre dossier (ex. le dossier du projet). Les mots de passe restent dans le coffre-fort."),
                  foreground="#777", wraplength=600).grid(row=6, column=1, sticky="w")
        self.sortie_auto = self._sortie(f, 10)
        self.sortie_auto.grid(row=4, column=0, columnspan=3, sticky="nsew")
        f.rowconfigure(4, weight=1)

    def _onglet_correspondance(self) -> None:
        from .page_correspondance import PageCorrespondance

        self.page_correspondance = PageCorrespondance(self.onglets, self.racine, TITRE)
        self.onglets.add(self.page_correspondance, text=t("5. Correspondance des articles"))

    def _onglet_tableau(self) -> None:
        f = self._cadre(t("6. Tableau de bord"))
        haut = ttk.Frame(f)
        haut.pack(fill="x")
        ttk.Button(haut, text=t("Lancer maintenant"), command=lambda: self.lancer(False)).pack(side="left")
        ttk.Button(haut, text=t("Simulation (sans import)"), command=lambda: self.lancer(True)).pack(side="left", padx=6)
        ttk.Button(haut, text=t("Ouvrir la correspondance des articles"),
                   command=lambda: self.ouvrir(self.racine / "donnees" / "correspondance_articles.xlsx")).pack(side="left")
        ttk.Button(haut, text=t("Dossier des données"),
                   command=lambda: self.ouvrir(self.racine / "donnees")).pack(side="left", padx=6)
        ttk.Button(haut, text=t("Actualiser"), command=self.actualiser_tableau).pack(side="right")
        self.resume_tableau = ttk.Label(f, text="", font=("Segoe UI", 10), padding=(0, 10))
        self.resume_tableau.pack(fill="x")
        self.sortie_tableau = self._sortie(f, 18)
        self.sortie_tableau.pack(fill="both", expand=True)

    # ---------------------------------------------------------------- actions
    def enregistrer(self) -> bool:
        v = {k: var.get() for k, var in self.vars.items()}
        heure = str(v["auto.heure"]).strip()
        try:
            date.fromisoformat(str(v["auto.date_depart"]).strip())
            h, m = heure.split(":")
            assert 0 <= int(h) < 24 and 0 <= int(m) < 60
            int(str(v["courriel.port"]).strip() or 587)
        except (ValueError, AssertionError):
            messagebox.showerror(TITRE, t("Vérifiez la date (AAAA-MM-JJ), l'heure (HH:MM) et le port du courriel."))
            return False
        c = self.config_toml
        c.setdefault("clover", {}).update(merchant_id=str(v["clover.merchant_id"]).strip())
        c["clover"].setdefault("base_url", "https://api.clover.com")
        c["clover"].pop("api_token", None)
        c.setdefault("general", {}).setdefault("fuseau_horaire", "America/Toronto")
        c["general"]["langue"] = langues.courante()
        fichier = str(v["sage.fichier"]).strip()
        c.setdefault("sage_base", {}).update(utilisateur=str(v["sage.utilisateur"]).strip(), fichier_entreprise=fichier)
        c["sage_base"].pop("mot_de_passe", None)
        c["sage_base"].setdefault("port", 13540)
        c.setdefault("sage_import", {}).update(fichier_entreprise=fichier)
        for cle, defaut in (("version", "12001"), ("pays", "1"), ("position_numero", 3)):
            c["sage_import"].setdefault(cle, defaut)
        c.setdefault("automatique", {}).update(date_depart=str(v["auto.date_depart"]).strip(), heure=heure)
        c["automatique"].setdefault("delai_import", 3600)
        c.setdefault("courriel", {}).update(
            serveur=str(v["courriel.serveur"]).strip(), port=int(str(v["courriel.port"]).strip() or 587),
            securite=v["courriel.securite"], utilisateur=str(v["courriel.utilisateur"]).strip(),
            expediteur=str(v["courriel.expediteur"]).strip(), destinataires=str(v["courriel.destinataires"]).strip(),
            envoyer_si_succes=bool(v["courriel.envoyer_si_succes"]))
        for cle_var, cle_coffre in (("secret.clover", coffre.CLOVER_JETON), ("secret.sage_lecture", coffre.SAGE_LECTURE),
                                    ("secret.sage_import", coffre.SAGE_IMPORT), ("secret.courriel", coffre.COURRIEL)):
            valeur = str(v[cle_var])
            if valeur and valeur != MASQUE:
                coffre.ecrire(cle_coffre, valeur)
                self.vars[cle_var].set(MASQUE)
        ecrire_config(self.chemin_config, c)
        self.etat.config(text=t("Configuration enregistrée."))
        return True

    def tester_clover(self) -> None:
        if not self.enregistrer():
            return

        def test():
            from .__main__ import charger_config
            from .api_clover import ClientClover

            client = ClientClover(charger_config(self.chemin_config))
            return t("connecté à « {nom} »", nom=client.marchand().get("name", "?"))

        self._tache(t("Test Clover"), test, self.sortie_clover)

    def tester_sage(self) -> None:
        if not self.enregistrer():
            return

        def test():
            from .__main__ import executable_import, ouvrir_base_sage
            from .automatique import lire_etat_sage
            from .facture import CLIENT
            from .sage_auto import lire_pendant_connexion

            config = lire_config(self.chemin_config)
            fichier = Path(config["sage_import"]["fichier_entreprise"])
            if not fichier.is_file():
                raise RuntimeError(t("fichier introuvable : {fichier}", fichier=fichier))

            def lecture():
                with ouvrir_base_sage(config, fichier) as base:
                    return lire_etat_sage(base, CLIENT)

            try:
                etat = lecture()
                mode = t("Sage ouvert")
            except Exception:
                exe = executable_import()
                if not exe:
                    raise RuntimeError("Sage_SA_import.exe ?")
                etat = lire_pendant_connexion(exe, fichier, lecture)
                mode = t("Sage fermé : base ouverte puis refermée automatiquement")
            client = "OK" if etat.client_configure else t(
                "À RÉGLER : cocher « Ce client utilise mes n° articles » dans la fiche du client")
            sans_compte = sum(1 for a in etat.articles if not a.compte_revenus and a.type == "Inventory")
            return t("{mode}. {n} articles. Dernière facture journalière : {derniere}. Client « {client} » : {etat}. "
                     "Articles sans compte de produits : {sans}.", mode=mode, n=len(etat.articles),
                     derniere=etat.derniere_date or t("aucune"), client=CLIENT, etat=client, sans=sans_compte)

        self._tache(t("Test Sage"), test, self.sortie_sage)

    def tester_courriel(self) -> None:
        if not self.enregistrer():
            return

        def test():
            from .courriel import envoyer

            envoyer(lire_config(self.chemin_config), t("MVOGMBI_Sync : courriel de test"),
                    t("Ce courriel confirme que les alertes de MVOGMBI_Sync sont bien configurées."))
            return t("courriel envoyé")

        self._tache(t("Courriel de test"), test, self.sortie_courriel)

    def installer_tache(self) -> None:
        if not self.enregistrer():
            return
        from . import planification

        heure = str(self.vars["auto.heure"].get()).strip()
        self._tache(t("Installation de la tâche"), lambda: planification.installer(self.racine, heure), self.sortie_auto)

    def retirer_tache(self) -> None:
        from . import planification

        if messagebox.askyesno(TITRE, t("Retirer la tâche planifiée ? Les ventes ne seront plus importées automatiquement.")):
            self._tache(t("Retrait de la tâche"), planification.retirer, self.sortie_auto)

    def etat_tache(self) -> None:
        from . import planification

        self._tache(t("État de la tâche"), planification.etat, self.sortie_auto)

    def raccourci(self) -> None:
        bureau = Path(os.environ.get("USERPROFILE", "~")).expanduser() / "Desktop"
        cible = (str(Path(sys.executable).resolve()) if getattr(sys, "frozen", False)
                 else str(Path(sys.executable).with_name("pythonw.exe")))
        arguments = "" if getattr(sys, "frozen", False) else "-m mvogmbi_sync interface"
        script = (f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut("{bureau / "MVOGMBI_Sync.lnk"}");'
                  f'$s.TargetPath="{cible}";$s.Arguments="{arguments}";$s.WorkingDirectory="{self.racine}";$s.Save()')
        self._tache(t("Raccourci sur le Bureau"),
                    lambda: subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True) and t("créé"),
                    self.sortie_auto)

    def reprendre(self) -> None:
        import shutil

        dossier = filedialog.askdirectory(title=t("Dossier contenant config.toml (et le sous-dossier donnees)"))
        if not dossier:
            return
        source = Path(dossier)
        copies = []
        if (source / "config.toml").exists():
            ancienne = lire_config(source / "config.toml")
            # Secrets encore en clair dans l'ancienne configuration : transférés dans le coffre-fort
            jeton = ancienne.get("clover", {}).pop("api_token", "")
            mdp = ancienne.get("sage_base", {}).pop("mot_de_passe", "")
            if jeton and not coffre.present(coffre.CLOVER_JETON):
                coffre.ecrire(coffre.CLOVER_JETON, jeton)
            if mdp and not coffre.present(coffre.SAGE_LECTURE):
                coffre.ecrire(coffre.SAGE_LECTURE, mdp)
            ecrire_config(self.chemin_config, ancienne)
            copies.append("config.toml")
        for nom in ("correspondance_articles.xlsx", "articles_a_relier.csv", "journal_imports.csv", "articles_sage.csv"):
            if (source / "donnees" / nom).exists():
                (self.racine / "donnees").mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / "donnees" / nom, self.racine / "donnees" / nom)
                copies.append(nom)
        if not copies:
            messagebox.showwarning(TITRE, t("Aucun fichier de configuration trouvé dans ce dossier."))
            return
        messagebox.showinfo(TITRE, t("Repris : {fichiers}.\nL'application va se fermer : rouvrez-la.",
                                     fichiers=", ".join(copies)))
        self.destroy()

    def lancer(self, simulation: bool) -> None:
        if not self.enregistrer():
            return
        if not simulation and not messagebox.askyesno(
                TITRE, t("Lancer le traitement maintenant ? Les factures manquantes seront importées dans Sage.")):
            return
        zone = self.sortie_tableau
        zone.delete("1.0", "end")

        def traitement():
            from .__main__ import commande_moteur

            commande = commande_moteur() + ["auto"]
            if simulation:
                commande.append("--simulation")
            processus = subprocess.Popen(commande, cwd=self.racine, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, encoding="utf-8", errors="replace",
                                         env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for ligne in processus.stdout:
                self.file_messages.put((zone, ligne.rstrip()))
            return t("réussi") if processus.wait() == 0 else t("terminé avec des points à corriger (voir ci-dessus)")

        self._tache(t("Simulation") if simulation else t("Traitement"), traitement, zone)

    def ouvrir(self, chemin: Path) -> None:
        if chemin.exists():
            os.startfile(chemin)
        else:
            messagebox.showinfo(TITRE, t("Introuvable pour l'instant : {chemin}", chemin=chemin))

    def actualiser_tableau(self) -> None:
        journal = self.racine / "donnees" / "journal_imports.csv"
        derniere = t("aucune")
        if journal.exists():
            lignes = [l for l in journal.read_text(encoding="utf-8-sig").splitlines()[1:] if ";importée" in l]
            if lignes:
                derniere = lignes[-1].split(";")[1]
        from . import planification

        try:
            tache = t("installée") if "non installée" not in planification.etat() else t("NON installée")
        except Exception:
            tache = "?"
        self.resume_tableau.config(text=t("Dernière facture importée : {derniere}     •     Tâche planifiée : {tache}",
                                          derniere=derniere, tache=tache))
        log = self.racine / "donnees" / "journal_automatique.log"
        if log.exists() and not self.sortie_tableau.get("1.0", "end").strip():
            self.sortie_tableau.insert("end", "\n".join(log.read_text(encoding="utf-8").splitlines()[-60:]))
            self.sortie_tableau.see("end")


def lancer_interface(racine: Path) -> None:
    (racine / "donnees").mkdir(parents=True, exist_ok=True)
    try:  # affichage net sur les écrans à mise à l'échelle (125 %, 150 %…)
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    while True:  # un changement de langue reconstruit la fenêtre
        application = Application(racine)
        application.mainloop()
        if not application.relancer:
            break
