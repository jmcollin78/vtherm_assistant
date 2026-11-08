# Spec Delta

## Purpose

Expliquer le fonctionnement et les comportements des VTherm à partir des états actuels accessibles de l'installation et de leurs dépendances pertinentes.

Les scénarios sont des exemples représentatifs et ne limitent pas les diagnostics ou questions couverts par les exigences.

L'accès à l'historique Home Assistant et la recherche documentaire pour un diagnostic sont retirés du périmètre courant le 2026-11-08, à la demande de l'utilisateur. Leur intégration et leur validation sont reportées au change suivant ; ce report ne supprime ni les horodatages ni la sauvegarde de la conversation.

## ADDED Requirements

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