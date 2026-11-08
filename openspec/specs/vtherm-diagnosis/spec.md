# vtherm-diagnosis Specification

## Purpose

Expliquer le fonctionnement et les comportements des VTherm à partir des états actuels accessibles de l'installation et de leurs dépendances pertinentes.

Les scénarios sont des exemples représentatifs et ne limitent pas les diagnostics ou questions couverts par les exigences.

L'accès à l'historique Home Assistant et la recherche documentaire pour un diagnostic sont retirés du périmètre courant le 2026-11-08, à la demande de l'utilisateur. Leur intégration et leur validation sont reportées au change suivant ; ce report ne supprime ni les horodatages ni la sauvegarde de la conversation.

## Requirements

### Requirement: Diagnostic contextualisé
Le système MUST examiner les informations disponibles et pertinentes pour répondre à la question de l'utilisateur sur le fonctionnement ou le comportement du VTherm concerné.

#### Scenario: Thermostat en attente
- **WHEN** le VTherm est en mode chauffage mais sans demande de chauffe
- **THEN** l'assistant décrit cet état sans affirmer que le thermostat est éteint

### Requirement: Dépendances pertinentes
Le système MUST prendre en compte, lorsque leurs données sont accessibles et pertinentes, les entités associées au VTherm, ses appareils sous-jacents, ainsi que les plugins et cartes concernés par la question.

#### Scenario: Inhibition par un plugin
- **WHEN** les données accessibles indiquent qu'un plugin inhibe le VTherm selon une règle liée à une climatisation
- **THEN** l'assistant identifie le plugin et, si la règle et les données temporelles le permettent, explique la condition et son déclenchement

#### Scenario: Configuration du plugin inaccessible
- **WHEN** l'inhibition est visible mais que sa règle ou les états nécessaires ne sont pas accessibles
- **THEN** l'assistant indique cette limite et ne prétend pas connaître la condition de déclenchement

### Requirement: Conclusions étayées
Le système MUST distinguer les faits observés, les hypothèses et les informations manquantes, sans présenter une corrélation ou une valeur isolée comme une cause démontrée.

#### Scenario: Puissance de chauffe à 50 pour cent
- **WHEN** la température de consigne n'est pas atteinte et que la puissance indiquée est de 50 pour cent
- **THEN** l'assistant ne conclut pas sur cette seule base que la puissance est la cause du froid

### Requirement: Conseils contextualisés
Le système MUST proposer des pistes compatibles avec les informations vérifiées et préciser leurs limites, sans prétendre avoir consulté une source documentaire absente des preuves disponibles ni installer ou configurer un plugin.

#### Scenario: Réglage ou plugin proposé
- **WHEN** l'utilisateur demande comment améliorer le chauffage
- **THEN** l'assistant présente les options étayées et leurs limites, sans inventer une valeur de coefficient ni supposer la compatibilité d'un plugin

### Requirement: Données indisponibles
Le système MUST indiquer les informations manquantes ou inaccessibles lorsqu'elles empêchent un diagnostic fiable et proposer une vérification complémentaire lorsqu'elle est possible.

#### Scenario: Capteur indisponible
- **WHEN** une information nécessaire au diagnostic est inconnue ou indisponible
- **THEN** l'assistant le signale et limite sa conclusion aux éléments disponibles

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

### Requirement: Découverte dynamique des outils VTherm
Le système MUST découvrir à l'exécution tous les outils publiés par l'intégration Versatile Thermostat et les rendre disponibles à l'assistant sans liste locale fixe de noms. Cette découverte MUST inclure les outils de lecture et d'écriture.

#### Scenario: Nouvel outil VTherm publié
- **WHEN** l'intégration VTherm publie un outil qui n'était pas présent lors d'une découverte précédente
- **THEN** l'outil est découvert et disponible à l'assistant à la prochaine actualisation, sans ajout manuel de son nom dans l'application

#### Scenario: Outil d'écriture découvert
- **WHEN** un outil VTherm découvert peut modifier l'installation
- **THEN** l'outil est disponible à l'assistant, mais son exécution reste soumise à la confirmation explicite requise par la spécification de conversation

#### Scenario: Outil VTherm retiré ou indisponible
- **WHEN** un outil précédemment publié n'est plus annoncé ou ne peut pas être appelé
- **THEN** le système ne prétend pas l'avoir exécuté et signale son indisponibilité sans inventer de résultat

### Requirement: Outils Home Assistant standards limités
Le système MUST limiter les outils MCP hors VTherm à une sélection explicite d'opérations de consultation. Cette sélection MAY inclure la lecture d'état ou d'historique du VTherm sélectionné et de ses entités liées, sans ouvrir l'accès général à Home Assistant.

#### Scenario: Lecture d'état ou d'historique liée
- **WHEN** l'assistant consulte un outil Home Assistant standard retenu pour le diagnostic d'un VTherm
- **THEN** la requête porte uniquement sur le VTherm sélectionné ou une entité dont le lien avec lui est établi

#### Scenario: Outil standard hors sélection
- **WHEN** le modèle tente d'appeler un outil MCP Home Assistant hors VTherm qui n'appartient pas à la sélection explicite de consultation
- **THEN** le système refuse l'appel avant toute opération

### Requirement: Appels de logs et de plugins ciblés
Les outils VTherm de consultation des journaux techniques et des plugins MUST recevoir un seul VTherm cible par appel et MUST NOT retourner les journaux ou la configuration de plusieurs VTherm dans le même appel.

#### Scenario: Consultation ciblée
- **WHEN** l'assistant demande les journaux ou les plugins d'un VTherm
- **THEN** l'appel cible ce seul VTherm et les résultats sont attribués à son identifiant

#### Scenario: Plusieurs VTherm concernés
- **WHEN** la question porte sur plusieurs VTherm et nécessite des journaux ou des plugins
- **THEN** l'assistant traite chaque VTherm dans un appel distinct, après avoir identifié les thermostats concernés

#### Scenario: Bilan général incluant les plugins
- **WHEN** l'utilisateur demande un bilan général d'un VTherm identifié et que l'outil de consultation des plugins est disponible
- **THEN** l'assistant consulte les plugins de ce seul VTherm et rapporte les plugins connectés, leur statut et la couverture retournée

#### Scenario: État des plugins indisponible
- **WHEN** l'outil de consultation des plugins est absent, indisponible ou retourne des données incomplètes
- **THEN** l'assistant signale cette limite sans conclure qu'aucun plugin n'est connecté

#### Scenario: Changement explicite de VTherm
- **WHEN** l'utilisateur demande explicitement de passer à un autre VTherm identifié
- **THEN** l'assistant sélectionne d'abord ce climate par son état ou son diagnostic, puis effectue les lectures complémentaires sur cette nouvelle cible sans échouer à cause de la sélection précédente

#### Scenario: Nouvelle cible ambiguë
- **WHEN** la demande de changement ne permet pas d'identifier un seul VTherm
- **THEN** l'assistant demande une précision avant toute lecture ciblée