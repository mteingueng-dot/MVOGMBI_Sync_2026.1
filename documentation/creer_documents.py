"""Documents du projet en PDF à partir de leurs sources Markdown (lisibles aussi sur GitHub) : architecture,
documentation fonctionnelle, plan et rapport de tests, diagramme de projet, workflows d'utilisation, processus
métier (BPM). Même conversion que le document d'architecture (diagrammes Mermaid dessinés par Microsoft Edge).
Aucun de ces documents ne contient de donnée réelle : ils sont publiés.

    python documentation/creer_documents.py [nom…]
"""

from __future__ import annotations

import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from creer_architecture import creer  # noqa: E402

DOCUMENTS = [  # (source, PDF, titre)
    (ICI.parent / "ARCHITECTURE.md", "Architecture_MVOGMBI_Sync.pdf", "Architecture MVOGMBI_Sync"),
    (ICI / "DOCUMENTATION_FONCTIONNELLE.md", "Documentation_fonctionnelle_MVOGMBI_Sync.pdf",
     "Documentation fonctionnelle MVOGMBI_Sync"),
    (ICI / "PLAN_DE_TEST.md", "Plan_de_test_MVOGMBI_Sync.pdf", "Plan et rapport de tests MVOGMBI_Sync"),
    (ICI / "PROJET.md", "Diagramme_de_projet_MVOGMBI_Sync.pdf", "Diagramme de projet MVOGMBI_Sync"),
    (ICI / "WORKFLOWS.md", "Workflows_MVOGMBI_Sync.pdf", "Workflows d'utilisation MVOGMBI_Sync"),
    (ICI / "PROCESSUS_BPM.md", "Processus_BPM_MVOGMBI_Sync.pdf", "Processus métier MVOGMBI_Sync"),
]


def creer_tout(noms: list[str] | None = None) -> list[Path]:
    faits = []
    for source, pdf, titre in DOCUMENTS:
        if noms and not any(n.lower() in pdf.lower() for n in noms):
            continue
        faits.append(creer(ICI / pdf, source, titre))
        print(faits[-1].name)
    return faits


if __name__ == "__main__":
    creer_tout(sys.argv[1:] or None)
