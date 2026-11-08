# Tasks

## 1. Vérifier les contrats et compatibilités

- [ ] 1.1 Relever sur les versions HA prises en charge les outils MCP officiels d'état et d'historique, leurs schémas, permissions, périodes et limites ; consigner les versions et confirmer par test qu'ils ne modifient pas l'installation.
- [ ] 1.2 Vérifier dans les versions VTherm ciblées les outils MCP de plugins et de journaux, leurs champs et erreurs ; confirmer qu'un appel cible exactement un VTherm et consigner les versions, sans activer d'outil non vérifié.
- [ ] 1.3 Définir et documenter comment les entités liées et les champs de configuration transmissibles sont déterminés à partir des réponses VTherm ; vérifier qu'aucune recherche générale ni donnée secrète n'est requise.

## 2. Ajouter les lectures MCP contrôlées

- [ ] 2.1 Ajouter les lectures d'état et d'historique des entités liées à un VTherm sélectionné ; tester les identifiants hors périmètre, la période, la pagination, Recorder incomplet/absent, les accès refusés et l'absence d'appel à un outil d'écriture.
- [ ] 2.2 Autoriser les outils VTherm vérifiés de plugins et de journaux, un seul VTherm par appel ; tester outil absent, schéma invalide, accès refusé, appel multi-VTherm, outil inconnu et refus des outils modifiant l'installation.
- [ ] 2.3 Borner les résultats transmis au modèle, préserver source/horodatages/période/couverture et masquer les secrets ; tester troncature, résultats volumineux, secrets dans les journaux/configurations et texte hostile traité comme donnée.

## 3. Orchestrer le diagnostic VTherm

- [ ] 3.1 Faire sélectionner ou clarifier le VTherm avant les lectures complémentaires et appeler les sources uniquement quand elles sont pertinentes ; tester qu'aucune entité non liée ou aucun autre VTherm n'est consulté.
- [ ] 3.2 Faire distinguer les observations d'état, d'historique, de plugin et de journal des hypothèses et des absences de données ; tester les résultats discordants, incomplets et les outils indisponibles sans conclusion fabriquée.
- [ ] 3.3 Documenter les sources accessibles, les versions vérifiées, les limites Recorder et les comportements en cas d'accès refusé ; vérifier que les instructions n'activent aucun outil d'écriture et ne promettent pas une source indisponible.

## 4. Valider l'intégration réelle

- [ ] 4.1 Vérifier de bout en bout sur les versions HA/VTherm prises en charge l'état courant, l'historique et les outils de plugins/journaux pour un VTherm et ses entités liées ; consigner permissions, périodes et limites réelles.
- [ ] 4.2 Vérifier de bout en bout le refus des outils d'écriture, l'isolation des données par utilisateur et par VTherm, le masquage des secrets et l'affichage d'un diagnostic limité lorsque des sources manquent ; confirmer qu'aucun état HA ou VTherm n'est modifié.