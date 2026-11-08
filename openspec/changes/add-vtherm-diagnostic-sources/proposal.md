# Proposal

## Why

Les diagnostics actuels reposent principalement sur l'état courant accessible du VTherm et de ses dépendances. L'accès ciblé à l'historique Home Assistant, aux plugins VTherm installés et configurés et aux journaux techniques du VTherm apporterait des preuves supplémentaires pour expliquer un comportement ou une panne, sans transformer l'assistant en assistant généraliste Home Assistant.

## What Changes

- Conserver l'accès au contexte global d'état fourni par le MCP officiel Home Assistant `GetLiveContext`, comme exception explicite au périmètre d'un seul VTherm. Les nouvelles lectures liées au diagnostic restent ciblées ; l'historique est limité à l'entité climate du VTherm, sans historique de ses dépendances.
- Ajouter l'accès en lecture aux plugins installés et configurés pour un seul VTherm, ainsi qu'à ses journaux techniques bruts via les futurs outils MCP VTherm supposés par ce changement.
- Borner les requêtes historiques du climate VTherm et les résultats volumineux ; distinguer les données absentes, inaccessibles, expirées ou tronquées des données qui n'ont jamais existé.
- Présenter les sources, périodes et limites des données consultées ; traiter les résultats d'outils et les journaux comme des données non fiables et protéger les secrets avant transmission au fournisseur de modèle.
- Maintenir une autorisation serveur explicite des seules opérations vérifiées en lecture. `GetLiveContext` reste l'unique exception autorisée pour le contexte d'état global déjà exposé à Assist ; ne pas ajouter d'autre lecture globale, de journaux globaux, d'opération d'écriture ni d'outil générique de commande.
- Vérifier les outils, schémas, permissions, versions et limites réellement disponibles côté Home Assistant et VTherm avant de considérer ces sources compatibles.

## Capabilities

### New Capabilities

Aucune.

### Modified Capabilities

- `vtherm-diagnosis` : étendre les preuves de diagnostic aux plugins et journaux techniques d'un VTherm, à l'état courant de ses entités liées et à l'historique de sa seule entité climate, dans un périmètre strictement en lecture seule.

## Impact

- Backend MCP : découverte et liste d'autorisation des outils Home Assistant et des futurs outils VTherm, validation des paramètres, bornes de résultats et masquage des secrets.
- Orchestration de conversation : conservation du contexte global `GetLiveContext`, sélection d'un VTherm pour les lectures ciblées et attribution des faits à leurs sources et périodes sans présenter le contexte global comme un lien prouvé.
- Home Assistant et Versatile Thermostat : disponibilité dépendante des outils MCP exposés, des versions et des permissions effectives ; aucun changement de configuration ni de rétention Recorder.
- Fournisseurs de modèles : les résultats pertinents pourront être transmis pour le diagnostic ; leur volume et les secrets devront être contrôlés avant envoi.
- Tests et documentation : couverture de lecture seule, d'accès refusé, d'historique incomplet ou indisponible, de plugins/journaux absents et de données non fiables.