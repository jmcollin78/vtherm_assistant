# Spec Delta

## Purpose

Permettre aux utilisateurs de dialoguer avec un assistant spécialisé VTherm depuis Home Assistant et de reprendre leur dernière conversation, sans conserver de mémoire entre les conversations distinctes.

## ADDED Requirements

### Requirement: Conversation dans l'interface de l'app
Le système MUST proposer dans l'interface de l'app une conversation permettant d'envoyer des questions écrites et de consulter les réponses, sans carte de tableau de bord ni utilisation de l'interface Assist. L'app MUST pouvoir être affichée dans la barre latérale de Home Assistant lorsque le système d'apps et ingress sont disponibles.

#### Scenario: Question posée dans l'app
- **WHEN** l'utilisateur demande pourquoi un VTherm ne chauffe pas dans l'interface de l'app
- **THEN** la réponse de l'assistant apparaît dans cette même conversation

#### Scenario: Accès depuis la barre latérale
- **WHEN** l'app est installée sur une instance compatible et que son affichage dans la barre latérale est activé
- **THEN** l'utilisateur peut ouvrir la conversation depuis cette barre sans ajouter de carte à un tableau de bord

### Requirement: Accès réservé aux administrateurs identifiés
En première version, le système MUST vérifier l'identité et le statut d'administrateur Home Assistant avant de permettre l'accès aux conversations, à la configuration ou aux requêtes de l'assistant. Il MUST refuser ces accès lorsque l'identité ou les droits ne peuvent pas être vérifiés.

#### Scenario: Administrateur identifié
- **WHEN** un administrateur Home Assistant dont l'identité et les droits sont vérifiés accède à l'app
- **THEN** il peut utiliser l'assistant et accéder à sa propre conversation

#### Scenario: Utilisateur non administrateur
- **WHEN** un utilisateur Home Assistant non administrateur tente d'utiliser l'assistant
- **THEN** l'accès à la conversation, à la configuration et aux requêtes est refusé

#### Scenario: Identité ou droits invérifiables
- **WHEN** l'identité ou le statut d'administrateur ne peut pas être vérifié
- **THEN** aucune conversation sauvegardée n'est affichée et aucune requête de l'assistant n'est exécutée

### Requirement: Conservation de la dernière conversation
Le système MUST conserver localement la dernière conversation et son contexte pour chaque utilisateur autorisé, afin de permettre leur reprise après navigation hors de l'app ou redémarrage de celle-ci. Chaque conversation sauvegardée MUST être accessible uniquement à l'utilisateur qui l'a créée.

#### Scenario: Retour après navigation dans Home Assistant
- **WHEN** l'utilisateur quitte l'app pour naviguer dans Home Assistant puis y revient
- **THEN** la dernière conversation est affichée et son contexte reste disponible pour les questions de suivi

#### Scenario: Retour après redémarrage de l'app
- **WHEN** l'utilisateur rouvre l'app après son redémarrage
- **THEN** la dernière conversation et son contexte sont disponibles

#### Scenario: Conversations de deux utilisateurs
- **WHEN** deux administrateurs identifiés utilisent l'app
- **THEN** chacun retrouve uniquement sa propre dernière conversation et ne peut pas accéder à celle de l'autre

### Requirement: Contexte limité à la conversation
Le système MUST utiliser le contexte de la conversation courante pour interpréter les questions de suivi, sans reprendre la conversation ni la mémoire personnelle d'une conversation précédente.

#### Scenario: Question de suivi
- **WHEN** l'utilisateur demande pourquoi le thermostat mentionné précédemment est inhibé
- **THEN** l'assistant utilise le thermostat et les faits établis dans la conversation active

#### Scenario: Nouvelle conversation
- **WHEN** l'utilisateur active le bouton de nouvelle conversation
- **THEN** les messages et le contexte de sa conversation courante sont supprimés du stockage de l'app et ne sont pas repris dans la nouvelle conversation, sans modifier les conversations des autres utilisateurs

### Requirement: Clarification en cas d'ambiguïté
Le système MUST demander une précision lorsqu'il ne peut pas identifier avec suffisamment de certitude le thermostat ou l'intention de l'utilisateur.

#### Scenario: Plusieurs thermostats possibles
- **WHEN** l'utilisateur évoque le salon et que plusieurs VTherm correspondent
- **THEN** l'assistant demande lequel est concerné avant de conclure

### Requirement: Lecture seule effective
Le système MUST empêcher toute modification de l'installation Home Assistant ou VTherm par l'assistant, y compris via les outils disponibles au modèle ; cette restriction MUST être appliquée en dehors des seules instructions données au modèle.

#### Scenario: Demande de modification
- **WHEN** l'utilisateur demande de modifier une règle d'inhibition ou une consigne
- **THEN** l'assistant ne réalise aucune modification et peut expliquer comment l'utilisateur peut procéder lui-même

#### Scenario: Tentative d'appel d'un outil de commande
- **WHEN** le modèle tente d'appeler un outil ou un service qui modifie l'installation
- **THEN** l'appel est refusé avant toute modification

### Requirement: État et erreurs visibles
L'interface de l'app MUST signaler une réponse en cours et les erreurs empêchant de répondre, sans présenter une réponse incomplète comme terminée.

Pour toute erreur prise en charge, le système MUST fournir une explication intelligible, une action possible et une référence d'incident non sensible, distinguer les causes vérifiées des inconnues et protéger les données et droits d'accès.

#### Scenario: Fournisseur indisponible
- **WHEN** le modèle choisi ne répond pas ou retourne une erreur
- **THEN** l'interface signale l'échec et permet de réessayer

#### Scenario: Erreur intelligible et traçable quelle que soit son origine
- **WHEN** une erreur prise en charge par l'application empêche une action ou la poursuite d'un traitement, qu'elle concerne l'authentification, la configuration, le réseau, MCP, le fournisseur, le streaming, le chargement, la restauration ou le stockage
- **THEN** l'utilisateur reçoit une explication compréhensible de l'échec, du composant identifié et d'une action corrective ou de relance pertinente, sans cause supposée présentée comme certaine ni message uniquement générique lorsque des informations sûres sont disponibles
- **AND** une référence d'incident opaque et non sensible est partagée avec les diagnostics backend lorsque la requête lui parvient ; ces diagnostics précisent l'opération, l'étape et les métadonnées techniques connues et autorisées
- **AND** une erreur purement locale au navigateur est identifiée comme telle, sans prétendre qu'un diagnostic backend existe
- **AND** les messages et diagnostics respectent les droits d'accès et ne divulguent ni secrets, ni messages bruts des services externes, ni corps HTTP, ni contenus de conversation et d'outils
- **AND** l'interface ne présente pas l'action ou la réponse en échec comme terminée avec succès et ne supprime pas de données valides du seul fait du signalement de l'erreur