"""Écriture ciblée dans config.toml : seules les lignes visées changent (commentaires, autres sections et fins
de ligne gardés). Reprise de ConceptSolutionStock 1.0.49 (sauvegarde dans le cloud)."""

from __future__ import annotations


def ecrire_valeurs(chemin, section: str, valeurs: dict) -> None:
    """Inscrit `valeurs` dans [section] de config.toml en ne changeant que leurs lignes (commentaires, autres
    sections et fins de ligne gardés) ; section ajoutée à la fin si elle manque."""
    from pathlib import Path

    chemin = Path(chemin)
    texte = chemin.read_bytes().decode("utf-8-sig") if chemin.exists() else ""
    lignes = texte.splitlines()
    debut = next((i for i, ligne in enumerate(lignes) if ligne.strip() == f"[{section}]"), None)
    if debut is None:
        if lignes and lignes[-1].strip():
            lignes.append("")
        lignes += [f"[{section}]"] + [_ligne_toml(c, v) for c, v in valeurs.items()]
    else:
        fin = next((i for i in range(debut + 1, len(lignes)) if lignes[i].lstrip().startswith("[")), len(lignes))
        while fin > debut + 1 and not lignes[fin - 1].strip():  # nouvelles lignes avant les lignes vides
            fin -= 1
        for c, v in valeurs.items():
            rang = next((i for i in range(debut + 1, fin) if lignes[i].split("=")[0].strip() == c), None)
            if rang is None:
                lignes.insert(fin, _ligne_toml(c, v))
                fin += 1
            else:
                lignes[rang] = _ligne_toml(c, v)
    fin_de_ligne = "\r\n" if "\r\n" in texte or not texte else "\n"
    chemin.write_text(fin_de_ligne.join(lignes) + fin_de_ligne, encoding="utf-8", newline="")


def _ligne_toml(cle: str, valeur) -> str:
    if isinstance(valeur, bool):
        return f"{cle} = {'true' if valeur else 'false'}"
    return f'{cle} = "' + str(valeur).replace("\\", "\\\\").replace('"', '\\"') + '"'
