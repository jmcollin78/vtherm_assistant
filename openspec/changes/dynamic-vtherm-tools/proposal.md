# Proposal

## Why

L'assistant expose aujourd'hui une liste fixe d'outils VTherm, ce qui l'empêche de suivre les capacités publiées par l'intégration et d'utiliser de nouveaux outils sans modifier l'application. Cette évolution rend tous les outils VTherm découverts accessibles, tout en exigeant une confirmation explicite de l'utilisateur avant chaque opération d'écriture.

## What Changes

- **BREAKING** Remplacer la liste fixe de noms d'outils VTherm par la découverte dynamique de tous les outils publiés par l'intégration Versatile Thermostat ; ne pas maintenir de liste locale exhaustive de ces outils.
- Fournir à l'assistant les outils VTherm découverts, en lecture comme en écriture, avec leurs schémas validés et leurs descriptions.
- Exiger, avant chaque appel d'écriture VTherm, une confirmation explicite portant sur l'action et ses paramètres exacts ; refuser l'appel en cas d'absence, de refus ou d'ambiguïté de confirmation.
- Maintenir pour les outils MCP Home Assistant hors VTherm une sélection explicite et limitée d'outils, notamment des outils de consultation d'état ou d'historique, sans exposer l'ensemble générique des opérations Home Assistant.
- Préserver le périmètre spécialisé VTherm : les lectures d'historique, de plugins et de journaux restent ciblées sur le VTherm sélectionné et ses dépendances selon le contrat de chaque outil.
- Signaler les outils absents, incompatibles ou refusés et vérifier les versions, schémas, permissions et effets réels avant de déclarer une compatibilité.

## Capabilities

### New Capabilities

Aucune.

### Modified Capabilities

- `vtherm-conversation` : remplacer l'interdiction générale d'écriture par une confirmation explicite obligatoire avant chaque appel d'outil VTherm qui modifie l'installation ; limiter les outils MCP Home Assistant hors VTherm à une sélection contrôlée.
- `vtherm-diagnosis` : découvrir dynamiquement tous les outils publiés par l'intégration VTherm, sans liste fixe, et les rendre disponibles à l'assistant, y compris les outils d'écriture sous le contrôle de confirmation défini dans `vtherm-conversation`.

## Impact

- Backend MCP : découverte et présentation dynamiques des outils VTherm et de leurs schémas ; maintien d'une sélection distincte pour les outils Home Assistant hors VTherm.
- Conversation et interface : identification des appels d'écriture, affichage de l'action et de ses paramètres, attente d'une confirmation explicite avant exécution.
- Home Assistant et Versatile Thermostat : l'assistant pourra effectuer des changements VTherm demandés et confirmés ; les droits effectifs du jeton et les capacités publiées par l'intégration bornent les opérations possibles.
- Fournisseurs de modèles : compatibilité des schémas d'outils dynamiques à vérifier pour les fournisseurs pris en charge.
- Le contexte actuel d'`openspec/config.yaml` impose encore une politique générale de lecture seule ; sa conciliation avec cette évolution reste hors des artefacts confirmés ici et devra être résolue avant l'implémentation.