# Changelog

## 0.1.1 - Correctif MCP, 2026-11-08

- Accepte les trois outils de lecture VTherm avec le prefixe `assist__` lorsque HA fusionne plusieurs API LLM.
- Conserve les noms sans prefixe utilises lorsqu'une seule API est exposee.
- Commandes d'ecriture toujours interdites ; schemas locaux et controles de securite inchanges.

## 0.1.0 - Release experimentale, 2026-11-08

- Image Python 3.14.10 Debian slim avec dependances de release figees.
- Constructions et tests locaux Linux aarch64 et amd64.
- Image GHCR publique ; telechargements anonymes verifies sur les deux architectures.
- Catalogue propre distribue dans la branche `ha-app`, sans fichiers OpenSpec.
- Interface ingress avec ressources relatives et refus sans connexion OAuth.
- Option d'adresse HA interne ; jetons MCP et fournisseur par utilisateur.
- Stockage prive persistant et sauvegarde cold de l'app.
- Droits Supervisor, streaming et restauration sur HA OS encore a verifier.