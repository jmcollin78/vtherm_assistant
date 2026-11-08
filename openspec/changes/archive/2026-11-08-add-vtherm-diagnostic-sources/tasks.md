# Tasks

## 1. Vérifier les contrats et compatibilités

- [x] 1.1 Documenter le schéma et les permissions de `GetLiveContext` (contexte global sans filtre, cible exacte via `name: entity_id`) et de l'outil VTherm d'historique du climate seul ; consigner les versions et vérifier par test qu'aucun ne modifie l'installation.
- [x] 1.2 Vérifier dans les versions VTherm ciblées les outils MCP de plugins et de journaux, leurs champs et erreurs ; confirmer qu'un appel cible exactement un VTherm et consigner les versions, sans activer d'outil non vérifié.
- [x] 1.3 Définir les champs VTherm faisant foi pour établir les liens (`underlying_entities` selon le type, et `sync_entity_ids` pour la synchronisation climate), exclure toute inférence depuis le contexte global et interdire la transmission des configurations brutes ; réserver les tests de projection effective à 2.3.

## 2. Ajouter les lectures MCP contrôlées

- [x] 2.1 Conserver le contexte global de `GetLiveContext` comme exception, utiliser son filtre `name: entity_id` pour lire l'état d'entités explicitement liées et ajouter l'historique du seul climate VTherm ; tester l'absence de relation inférée depuis le contexte global, le refus d'historique des dépendances, la période, la pagination, Recorder incomplet/absent, les accès refusés et l'absence d'écriture.
- [x] 2.2 Autoriser les outils VTherm vérifiés de plugins et de journaux, un seul VTherm par appel ; tester outil absent, schéma invalide, accès refusé, appel multi-VTherm, outil inconnu et refus des outils modifiant l'installation.
- [x] 2.3 Projeter les réponses `get_status`/`diagnose`, journaux et configurations sur une liste explicite de champs nécessaires, exclure `configuration` et `preset_temperatures`, borner les résultats, préserver source/horodatages/période/couverture et masquer les secrets connus ; tester secrets connus et inconnus, champs exclus, troncature, résultats volumineux et texte hostile traité comme donnée.

## 3. Orchestrer le diagnostic VTherm

- [x] 3.1 Faire sélectionner ou clarifier le VTherm avant les lectures ciblées et appeler les sources uniquement quand elles sont pertinentes ; tester que le contexte `GetLiveContext` reste global sans être présenté comme ciblé et qu'aucune lecture ciblée ne porte sur une entité non liée ou un autre VTherm.
- [x] 3.2 Faire distinguer les observations d'état, d'historique, de plugin et de journal des hypothèses et des absences de données ; tester les résultats discordants, incomplets et les outils indisponibles sans conclusion fabriquée.
- [x] 3.3 Documenter les sources accessibles, les versions vérifiées, les limites Recorder et les comportements en cas d'accès refusé ; vérifier que les instructions n'activent aucun outil d'écriture et ne promettent pas une source indisponible.

## 4. Valider l'intégration réelle

- [x] 4.1 Vérifier de bout en bout sur les versions HA/VTherm prises en charge le contexte global `GetLiveContext`, l'historique du seul climate et les outils de plugins/journaux pour un VTherm ; consigner permissions, périodes et limites réelles.
- [x] 4.2 Vérifier de bout en bout le refus des outils d'écriture, l'isolation des données par utilisateur et par VTherm, le masquage des secrets et l'affichage d'un diagnostic limité lorsque des sources manquent ; confirmer qu'aucun état HA ou VTherm n'est modifié.