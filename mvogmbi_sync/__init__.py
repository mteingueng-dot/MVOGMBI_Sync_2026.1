"""Synchronisation des ventes Clover vers Sage 50 — Marché MVOG-MBI Sherbrooke."""

from .securite import installer_protections as _installer_protections

_installer_protections()  # texte « =… » jamais écrit comme une formule dans les fichiers Excel (2026-11-13)
