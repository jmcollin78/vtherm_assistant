# Proposal

## Why

Les diagnostics actuels reposent principalement sur l'état courant accessible du VTherm et de ses dépendances. L'accès ciblé à l'historique Home Assistant, aux plugins VTherm installés et configurés et aux journaux techniques du VTherm apporterait des preuves supplémentaires pour expliquer un comportement ou une panne, sans transformer l'assistant en assistant généraliste Home Assistant.

## What Changes

- Permettre à l'assistant de consulter l'état courant et l'historique des états du VTherm sélectionné et des seules entités qui lui sont liées.
- Ajouter l'accès en lecture aux plugins installés et configurés pour un seul VTherm, ainsi qu'à ses journaux techniques bruts via les futurs outils MCP VTherm supposés par ce changement.
- Borner les requêtes historiques et les résultats volumineux ; distinguer les données absentes, inaccessibles, expirées ou tronquées des données qui n'ont jamais existé.
- Présenter les sources, périodes et limites des données consultées ; traiter les résultats d'outils et les journaux comme des données non fiables et protéger les secrets avant transmission au fournisseur de modèle.
- Maintenir une autorisation serveur explicite des seules opérations vérifiées en lecture. Ne pas exposer les journaux globaux, les entités sans lien avec le VTherm, les opérations d'écriture ni les outils génériques de commande.
- Vérifier les outils, schémas, permissions, versions et limites réellement disponibles côté Home Assistant et VTherm avant de considérer ces sources compatibles.

## Capabilities

### New Capabilities

Aucune.

### Modified Capabilities

- `vtherm-diagnosis` : étendre les preuves de diagnostic aux plugins et journaux techniques d'un VTherm ainsi qu'à l'historique des états du VTherm et de ses entités liées, dans un périmètre strictement en lecture seule.

## Impact

- Backend MCP : découverte et liste d'autorisation des outils Home Assistant et des futurs outils VTherm, validation des paramètres, bornes de résultats et masquage des secrets.
- Orchestration de conversation : sélection d'un VTherm, consultation de ses seules sources et dépendances liées, et attribution des faits à leurs sources et périodes.
- Home Assistant et Versatile Thermostat : disponibilité dépendante des outils MCP exposés, des versions et des permissions effectives ; aucun changement de configuration ni de rétention Recorder.
- Fournisseurs de modèles : les résultats pertinents pourront être transmis pour le diagnostic ; leur volume et les secrets devront être contrôlés avant envoi.
- Tests et documentation : couverture de lecture seule, d'accès refusé, d'historique incomplet ou indisponible, de plugins/journaux absents et de données non fiables.