# Assistant VTherm

![VTherm](logo.png)

App experimentale pour Home Assistant OS, integree par ingress et reservee
aux administrateurs. Elle utilise les outils MCP de lecture autorises pour
les diagnostics VTherm. Aucun port hote ni carte de tableau de bord a ajouter.

Catalogue experimental :
`https://github.com/jmcollin78/vtherm_assistant#ha-app`

L'image GHCR `0.1.0` est publique pour aarch64 et amd64 ; les telechargements
anonymes des deux architectures sont verifies. Le chargement du catalogue
par un vrai Supervisor et l'installation restent a verifier apres accord.
Ne pas ajouter le depot source brut comme catalogue : il contient aussi des
fichiers OpenSpec que Supervisor pourrait interpreter comme une autre app.

Voir [DOCS](DOCS.md) pour les prerequisites, l'installation, la configuration,
les donnees privees, sauvegardes et restaurations limitees a cette app.

Cibles a verifier : HA 2026.10 et VTherm 10.6.3. Seules les constructions
Linux aarch64/amd64 et les regressions locales sont actuellement testees ;
aucune compatibilite reelle HA OS n'est encore certifiee.