"""Travaux longs de l'application web (saisies dans Sage, lectures de boîtes de courriel, imports) : lancés dans un
fil, suivis sur la page /tache qui se rafraîchit seule (balise meta, aucun script). Un seul travail sur Sage à la fois
(comme dans l'application Windows : l'application ouvre Sage elle-même, Sage doit être fermé). Chaque travail est
noté dans l'audit avec la personne qui l'a lancé.
"""

from __future__ import annotations

import secrets
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime

from .serveur import Reponse, echapper as e

VERROU_SAGE = threading.Lock()


@dataclass
class Tache:
    ident: str
    titre: str
    personne: str
    retour: str
    debut: str
    etat: str = "En cours"   # En cours / Terminé / Échec
    messages: list[str] = field(default_factory=list)
    resultat: str = ""


def lancer(ctx, titre: str, travail, retour: str, sage: bool = False, noter: bool = True) -> Reponse:
    """travail(journal) -> texte du résultat (lignes) ; redirige vers la page de suivi. Chaque travail est noté au
    récapitulatif des traitements (`noter=False` : le travail lance une commande qui s'y note elle-même)."""
    from .. import audit
    from .serveur import redirection

    taches = ctx.app.memoire.setdefault("taches", {})
    if sage and any(t.etat == "En cours" and t.titre.endswith("(Sage)") for t in taches.values()):
        en_cours = next(t for t in taches.values() if t.etat == "En cours" and t.titre.endswith("(Sage)"))
        return redirection(f"/tache?id={en_cours.ident}")
    t = Tache(secrets.token_urlsafe(8), titre + (" (Sage)" if sage else ""), ctx.u.nom, retour,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    taches[t.ident] = t
    audit.noter(ctx.racine, f"Lancé : {titre}", "Web", utilisateur=ctx.u.nom)

    def journal(texte) -> None:
        t.messages.append(f"{datetime.now():%H:%M:%S}  {texte}")
        del t.messages[:-200]

    def executer() -> None:
        from .. import traitements

        traitements.definir_personne(t.personne)
        try:
            with traitements.suivre(titre if noter else "", ctx.racine, "Web", t.personne) as suivi:
                if sage:
                    with VERROU_SAGE:
                        resultat = travail(journal)
                else:
                    resultat = travail(journal)
                t.resultat = resultat if isinstance(resultat, str) else "\n".join(resultat or [])
                t.etat = "Terminé"
                suivi["detail"] = " ".join(t.resultat.split())[:300]
        except BaseException as erreur:  # noqa: BLE001 — SystemExit compris (jeton absent)
            t.resultat = str(erreur) or type(erreur).__name__
            t.etat = "Échec"
            ctx.app.noter(f"Tâche {t.titre} :\n{traceback.format_exc()}")
        audit.noter(ctx.racine, f"{t.etat} : {titre}", "Web", detail=t.resultat[:300], utilisateur=t.personne)

    threading.Thread(target=executer, daemon=True).start()
    return redirection(f"/tache?id={t.ident}")


def page_tache(ctx) -> Reponse:
    from .pages import _document, page
    from .menu import barre

    t = ctx.app.memoire.get("taches", {}).get(ctx.req.query.get("id", ""))
    if t is None or (t.personne != ctx.u.nom and not ctx.u.est_admin):
        return Reponse(404, page(ctx, "Travail", "<p>Ce travail est introuvable (le serveur a peut-être redémarré).</p>"))
    couleur = {"Terminé": "ok", "Échec": "erreur"}.get(t.etat, "")
    corps = (f"<h1 class='titre-page'>{e(t.titre)}</h1><p>Lancé par {e(t.personne)} le {e(t.debut)} · "
             f"<span class='etat {couleur}'>{e(t.etat)}</span></p>")
    if t.etat == "En cours":
        corps += "<p class='note'>Cette page se met à jour toute seule. Vous pouvez la quitter : le travail continue.</p>"
    if t.resultat:
        corps += f"<div class='carte'><pre class='resultat'>{e(t.resultat)}</pre></div>"
    if t.messages:
        corps += "<h2>Déroulement</h2><div class='carte'><pre class='resultat'>" + e("\n".join(t.messages[-40:])) \
                 + "</pre></div>"
    corps += f"<p><a href='{e(t.retour)}'>◀ Retour</a></p>"
    html = _document(t.titre, corps, ctx, barre(ctx))
    if t.etat == "En cours":
        html = html.replace("<head>", "<head><meta http-equiv='refresh' content='3'>", 1)
    return Reponse(corps=html)


def executer_sage(racine, commande: list[str], journal) -> dict:
    """Commande interne (ex. « depenses-bureau ») lancée sur le bureau caché, comme l'application Windows ; renvoie
    le bilan JSON écrit par la commande."""
    import json
    import tempfile
    from pathlib import Path

    from ..__main__ import commande_moteur
    from ..sage_bureau import executer_sur_bureau_cache, sage_ouvert

    if sage_ouvert():
        raise RuntimeError("Fermez Sage sur le serveur : l'application l'ouvre elle-même.")
    journal("L'application ouvre Sage elle-même…")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as dossier:
        bilan = Path(dossier) / "bilan.json"
        executer_sur_bureau_cache(commande_moteur() + commande + ["--resultat", str(bilan)], racine)
        return json.loads(bilan.read_text(encoding="utf-8")) if bilan.exists() else {"erreur": "Aucun bilan rendu."}
