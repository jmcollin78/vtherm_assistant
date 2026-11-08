# Spec Delta

## ADDED Requirements

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