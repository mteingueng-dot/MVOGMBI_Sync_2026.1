"""Utilisateurs de l'application et accès par profil (donnees/utilisateurs.json).

Règles du propriétaire (2026-10-26) :
- chacun ouvre l'application avec son nom et son mot de passe ; le mot de passe n'est jamais gardé : seule une
  empreinte PBKDF2-SHA256 salée l'est ;
- un profil = la liste des pages visibles ; une page non cochée disparaît du menu ;
- profils de départ : Administrateur (toutes les pages et la gestion des utilisateurs, non modifiable), Comptable
  (pages 5 à 10), Employé (Accueil, Tableau de bord) ; l'administrateur ajuste les accès et crée d'autres profils ;
- il reste toujours au moins un administrateur actif.

Le traitement de nuit (tâche planifiée) et les commandes en ligne ne passent pas par cette connexion : elle protège
l'interface, pas les fichiers de l'ordinateur.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# Pages de l'interface, dans l'ordre du menu (mêmes rangs que les index de interface.py)
PAGES = ("accueil", "clover", "sage", "courriel", "automatisation", "correspondance", "tableau", "encaissements",
         "fournisseurs", "paiements", "rapprochement", "rapports", "guide", "faq")
UTILISATEURS = "utilisateurs"  # page de gestion : administrateurs seulement

ADMIN = "Administrateur"
PROFILS_DEFAUT = {
    ADMIN: list(PAGES),
    "Comptable": ["accueil", "correspondance", "tableau", "encaissements", "fournisseurs", "paiements",
                  "rapprochement", "rapports", "guide", "faq"],
    "Employé": ["accueil", "tableau", "guide", "faq"],
}
LONGUEUR_MIN = 6
ITERATIONS = 200_000


class ErreurUtilisateur(ValueError):
    """Opération refusée (message à afficher tel quel)."""


@dataclass
class Utilisateur:
    nom: str
    profil: str
    sel: str = ""
    empreinte: str = ""
    actif: bool = True
    cree_le: str = ""
    derniere_connexion: str = ""

    @property
    def est_admin(self) -> bool:
        return self.profil == ADMIN


def empreinte(mot_de_passe: str, sel: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), bytes.fromhex(sel), ITERATIONS).hex()


def _cle(nom: str) -> str:
    return " ".join(nom.split()).casefold()


class Registre:
    def __init__(self, racine: Path):
        self.chemin = Path(racine) / "donnees" / "utilisateurs.json"
        self.journal = Path(racine) / "donnees" / "journal_connexions.log"
        self.profils: dict[str, list[str]] = {k: list(v) for k, v in PROFILS_DEFAUT.items()}
        self.utilisateurs: list[Utilisateur] = []
        if self.chemin.exists():
            donnees = json.loads(self.chemin.read_text(encoding="utf-8"))
            self.profils.update({k: [p for p in v if p in PAGES] for k, v in donnees.get("profils", {}).items()})
            self.profils[ADMIN] = list(PAGES)
            self.utilisateurs = [Utilisateur(**u) for u in donnees.get("utilisateurs", [])]

    # ------------------------------------------------------------------ lecture
    def existe(self) -> bool:
        """Au moins un compte : sinon, premier lancement -> création du compte administrateur."""
        return bool(self.utilisateurs)

    def trouver(self, nom: str) -> Utilisateur | None:
        return next((u for u in self.utilisateurs if _cle(u.nom) == _cle(nom)), None)

    def pages(self, utilisateur: Utilisateur) -> set[str]:
        """Pages visibles ; un profil supprimé entre-temps ne donne que l'accueil."""
        visibles = set(self.profils.get(utilisateur.profil, ["accueil"])) | {"accueil"}
        return visibles | ({UTILISATEURS} if utilisateur.est_admin else set())

    def admins_actifs(self) -> list[Utilisateur]:
        return [u for u in self.utilisateurs if u.est_admin and u.actif]

    # ------------------------------------------------------------------ connexion
    def verifier(self, nom: str, mot_de_passe: str) -> Utilisateur | None:
        u = self.trouver(nom)
        ok = bool(u and u.actif and u.sel and hmac.compare_digest(empreinte(mot_de_passe, u.sel), u.empreinte))
        self._noter(f"{'connexion' if ok else 'échec'} : {nom.strip()}")
        if ok:
            u.derniere_connexion = datetime.now().isoformat(timespec="seconds")
            self.enregistrer()
            return u
        return None

    def _noter(self, texte: str) -> None:
        try:
            self.journal.parent.mkdir(parents=True, exist_ok=True)
            with open(self.journal, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {texte}\n")
        except OSError:
            pass

    # ------------------------------------------------------------------ utilisateurs
    def ajouter(self, nom: str, profil: str, mot_de_passe: str) -> Utilisateur:
        nom = " ".join(nom.split())
        if not nom:
            raise ErreurUtilisateur("Le nom est obligatoire.")
        if self.trouver(nom):
            raise ErreurUtilisateur("Ce nom est déjà utilisé.")
        if profil not in self.profils:
            raise ErreurUtilisateur("Profil inconnu.")
        u = Utilisateur(nom, profil, cree_le=datetime.now().isoformat(timespec="seconds"))
        self._mot_de_passe(u, mot_de_passe)
        self.utilisateurs.append(u)
        self._noter(f"compte créé : {nom} ({profil})")
        return u

    def changer_mot_de_passe(self, nom: str, mot_de_passe: str) -> None:
        self._mot_de_passe(self._exige(nom), mot_de_passe)
        self._noter(f"mot de passe changé : {nom}")

    def _mot_de_passe(self, u: Utilisateur, mot_de_passe: str) -> None:
        if len(mot_de_passe) < LONGUEUR_MIN:
            raise ErreurUtilisateur(f"Le mot de passe doit avoir au moins {LONGUEUR_MIN} caractères.")
        u.sel = secrets.token_hex(16)
        u.empreinte = empreinte(mot_de_passe, u.sel)

    def changer_profil(self, nom: str, profil: str) -> None:
        u = self._exige(nom)
        if profil not in self.profils:
            raise ErreurUtilisateur("Profil inconnu.")
        if u.est_admin and profil != ADMIN and self.admins_actifs() == [u]:
            raise ErreurUtilisateur("Il doit rester au moins un administrateur actif.")
        u.profil = profil

    def activer(self, nom: str, actif: bool) -> None:
        u = self._exige(nom)
        if not actif and u.est_admin and self.admins_actifs() == [u]:
            raise ErreurUtilisateur("Il doit rester au moins un administrateur actif.")
        u.actif = actif

    def supprimer(self, nom: str) -> None:
        u = self._exige(nom)
        if u.est_admin and self.admins_actifs() == [u]:
            raise ErreurUtilisateur("Il doit rester au moins un administrateur actif.")
        self.utilisateurs.remove(u)
        self._noter(f"compte supprimé : {u.nom}")

    def _exige(self, nom: str) -> Utilisateur:
        u = self.trouver(nom)
        if not u:
            raise ErreurUtilisateur("Utilisateur introuvable.")
        return u

    # ------------------------------------------------------------------ profils
    def definir_profil(self, profil: str, pages: list[str]) -> None:
        profil = " ".join(profil.split())
        if not profil:
            raise ErreurUtilisateur("Le nom du profil est obligatoire.")
        if profil == ADMIN:
            raise ErreurUtilisateur("Le profil Administrateur a toujours accès à tout.")
        self.profils[profil] = [p for p in PAGES if p in set(pages) | {"accueil"}]

    def supprimer_profil(self, profil: str) -> None:
        if profil == ADMIN:
            raise ErreurUtilisateur("Le profil Administrateur ne peut pas être supprimé.")
        if any(u.profil == profil for u in self.utilisateurs):
            raise ErreurUtilisateur("Ce profil est encore attribué à des utilisateurs.")
        self.profils.pop(profil, None)

    # ------------------------------------------------------------------ fichier
    def enregistrer(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        temporaire = self.chemin.with_suffix(".tmp")
        temporaire.write_text(json.dumps({"profils": self.profils,
                                          "utilisateurs": [asdict(u) for u in self.utilisateurs]},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporaire, self.chemin)
