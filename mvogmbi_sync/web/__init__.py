"""Application web de MVOGMBI_Sync (demande du propriétaire du 2026-11-03 : version client-serveur, ouverte dans un
navigateur sur PC, Android ou iPhone, servie par SERVDC01 et atteinte par Tailscale).

Les pages réutilisent les modules de l'application (utilisateurs, pointage, planning, statistiques) : mêmes comptes,
mêmes profils, mêmes droits par fonction, mêmes fichiers de donnees/. Aucune bibliothèque de plus : serveur HTTP de
Python (http.server), pages HTML écrites ici.
"""
