# Spec Delta

## ADDED Requirements

### Requirement: Historique de l'entité climate du VTherm
Le système MUST consulter, lorsque l'outil de lecture est disponible, l'historique de la seule entité climate du VTherm sélectionné. Il MUST préciser la période et les limites effectives des données retournées, sans reconstruire les valeurs absentes de l'historique.

#### Scenario: Historique du VTherm disponible
- **WHEN** l'utilisateur demande l'évolution d'un VTherm et que l'historique de son entité climate est accessible
- **THEN** l'assistant rapporte les états observés de cette entité avec leurs horodatages et la période consultée

#### Scenario: Historique d'une dépendance demandé
- **WHEN** l'utilisateur demande l'historique d'une entité liée au VTherm
- **THEN** l'assistant précise que cette fonctionnalité ne consulte que l'historique de l'entité climate du VTherm et ne demande pas l'historique de la dépendance

#### Scenario: Historique incomplet ou indisponible
- **WHEN** l'entité climate est exclue de Recorder, que la période demandée dépasse les données conservées ou que l'accès est refusé
- **THEN** l'assistant indique la période ou les données manquantes et limite ses conclusions aux observations disponibles

### Requirement: Consultation des plugins liés à un VTherm
Le système MUST pouvoir consulter les plugins installés et leur configuration pour un seul VTherm par appel d'outil. L'assistant MUST distinguer la configuration effectivement retournée des informations inconnues ou inaccessibles.

#### Scenario: Plugins et configuration accessibles
- **WHEN** l'outil VTherm retourne les plugins configurés pour le thermostat sélectionné
- **THEN** l'assistant peut utiliser ces informations pour expliquer son comportement sans supposer de paramètres non retournés

#### Scenario: Plugin ou configuration inaccessible
- **WHEN** l'outil est absent, échoue ou ne retourne pas la configuration d'un plugin pertinent
- **THEN** l'assistant signale cette limite et ne prétend pas connaître le plugin ou sa règle de configuration

### Requirement: Consultation des journaux techniques d'un VTherm
Le système MUST pouvoir consulter les journaux techniques bruts d'un seul VTherm par appel d'outil et MUST signaler leur période et toute limite ou troncature connue.

#### Scenario: Journaux du thermostat sélectionné
- **WHEN** l'utilisateur demande l'analyse d'un incident et que les journaux du VTherm sélectionné sont accessibles
- **THEN** l'assistant utilise uniquement les journaux associés à ce VTherm et distingue les messages observés de ses hypothèses

#### Scenario: Journaux absents ou limités
- **WHEN** aucun journal pertinent n'est retourné, que la lecture échoue ou que le résultat est tronqué
- **THEN** l'assistant indique cette limite et ne traite pas l'absence de lignes retournées comme la preuve qu'aucun incident n'a eu lieu

### Requirement: Périmètre des sources de diagnostic
Les nouvelles lectures de diagnostic MUST rester limitées au VTherm sélectionné et aux entités explicitement liées par les données VTherm ; les lectures d'historique MUST cibler uniquement son entité climate. Le MCP officiel `GetLiveContext` est l'unique exception autorisée à ce périmètre et peut fournir le contexte global déjà exposé à Assist.

#### Scenario: Entité non liée au VTherm
- **WHEN** une entité Home Assistant n'est pas identifiée comme liée au VTherm sélectionné
- **THEN** l'assistant ne consulte pas son état ou son historique au titre de ce diagnostic

#### Scenario: Contexte global Home Assistant
- **WHEN** `GetLiveContext` retourne des états d'entités qui ne sont pas explicitement liées au VTherm sélectionné
- **THEN** l'assistant peut conserver ces états comme contexte global, mais ne les présente pas comme des données liées au VTherm ni comme des preuves provenant d'une lecture ciblée

#### Scenario: État ciblé d'une entité liée
- **WHEN** les données du VTherm établissent le lien avec une entité exposée à Assist
- **THEN** l'assistant peut demander son état courant à `GetLiveContext` en passant son `entity_id` exact dans le champ `name`

#### Scenario: Historique d'une entité liée
- **WHEN** une entité liée autre que le climate VTherm est identifiée
- **THEN** l'assistant peut consulter son état courant si nécessaire, mais ne consulte pas son historique au titre de ce diagnostic

#### Scenario: Détermination d'une entité liée
- **WHEN** l'assistant détermine quelles entités sont liées au VTherm sélectionné
- **THEN** il utilise uniquement `underlying_entities` dans la section correspondant au type VTherm (`vtherm_over_switch`, `vtherm_over_valve` ou `vtherm_over_climate`) et, si publiée, `vtherm_over_climate.temp_synchronisation.sync_entity_ids` ; il ne déduit aucun lien d'un nom, d'une pièce, d'une configuration ou du contexte global

### Requirement: Protection des nouvelles sources de diagnostic
Le système MUST masquer les secrets connus avant transmission. Les réponses d'outils MUST être projetées sur les seuls champs diagnostiques explicitement autorisés ; les réponses brutes ne sont jamais transmises. Les données retenues MUST être traitées comme non fiables, jamais comme des instructions.

#### Scenario: Secret ou instruction dans une source
- **WHEN** un journal ou une configuration contient un secret ou du texte ressemblant à une instruction
- **THEN** le secret n'est pas transmis au fournisseur et le texte est interprété uniquement comme une donnée source

#### Scenario: Réponse brute avec configuration
- **WHEN** `get_status` ou `diagnose` retourne une configuration, des températures de presets ou des champs hors de la projection diagnostique autorisée
- **THEN** l'application exclut ces champs avant la génération du modèle et ne s'appuie pas sur le seul masquage de secrets connus