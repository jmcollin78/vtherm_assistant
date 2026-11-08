# vtherm-conversation Specification

## Purpose

Permettre aux utilisateurs de dialoguer avec un assistant spécialisé VTherm depuis Home Assistant et de reprendre leur dernière conversation, sans conserver de mémoire entre les conversations distinctes.

## Requirements

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

### Requirement: Horodatage localisé des messages
L'interface MUST afficher la date et l'heure de chaque question et réponse en petits caractères avant le libellé « Vous » ou « Assistant ». Le format MUST respecter la langue et le fuseau horaire du navigateur de l'utilisateur, et non ceux du serveur Home Assistant. L'instant de la question MUST correspondre à son envoi et celui de la réponse à son premier fragment affichable ; ces instants MUST être conservés avec la conversation et ne pas être recalculés à chaque fragment ou rechargement.

#### Scenario: Question et réponse progressive
- **WHEN** l'utilisateur envoie une question et reçoit une réponse progressive
- **THEN** la question et la réponse affichent chacune leur horodatage avant le libellé de leur auteur
- **AND** l'horodatage de la réponse reste celui de son premier fragment pendant toute sa progression

#### Scenario: Fuseau différent du serveur
- **WHEN** le navigateur utilise une langue ou un fuseau horaire différent de celui du serveur HA
- **THEN** les dates et heures respectent les conventions du navigateur, y compris les changements d'heure applicables à chaque instant

#### Scenario: Restauration des horodatages
- **WHEN** l'utilisateur reprend sa conversation après navigation, rechargement ou redémarrage
- **THEN** les instants enregistrés sont conservés et affichés dans la langue et le fuseau actuels de son navigateur
- **AND** un ancien message sans horodatage connu ne reçoit pas une date inventée

### Requirement: Inventaire initial des VTherm interrogeables
Le système MUST afficher avant la première question de chaque nouvelle conversation le nombre et la liste des VTherm interrogeables, avec nom et identifiant `climate`. Cet inventaire MUST provenir de l'outil MCP de liste autorisé avec le jeton personnel de l'utilisateur vérifié, sans génération par le modèle ni modification d'exposition. Le compte MUST correspondre à la liste ; l'interface MUST distinguer chargement, liste vide et échec avec relance.

#### Scenario: Première conversation ou nouvelle conversation
- **WHEN** un utilisateur autorisé accède pour la première fois à une conversation vierge ou active l'action de nouvelle conversation
- **THEN** l'application consulte l'outil MCP de liste en lecture seule et affiche l'inventaire au début de cette conversation avant la première question
- **AND** seuls les VTherm accessibles selon l'exposition Assist et les autorisations effectives sont présentés comme interrogeables

#### Scenario: Restauration sans duplication
- **WHEN** l'utilisateur restaure une conversation existante
- **THEN** l'inventaire initial conservé n'est pas ajouté une seconde fois
- **AND** il reste identifié comme l'inventaire obtenu à l'initialisation, sans garantir que l'accessibilité des entités n'a pas changé depuis

#### Scenario: Liste vide ou lecture impossible
- **WHEN** aucun VTherm n'est retourné, que le jeton MCP manque, que l'outil de liste est absent ou que sa lecture échoue
- **THEN** l'interface distingue une liste vide d'une lecture impossible et propose une action pertinente et une relance en cas d'échec
- **AND** aucun inventaire n'est inventé et aucune clé fournisseur n'est requise pour cette lecture MCP

### Requirement: Clarification en cas d'ambiguïté
Le système MUST demander une précision lorsqu'il ne peut pas identifier avec suffisamment de certitude le thermostat ou l'intention de l'utilisateur.

#### Scenario: Plusieurs thermostats possibles
- **WHEN** l'utilisateur évoque le salon et que plusieurs VTherm correspondent
- **THEN** l'assistant demande lequel est concerné avant de conclure

### Requirement: Lecture seule effective
Le système MUST exiger une confirmation explicite de l'utilisateur, distincte de la demande initiale, avant chaque appel d'outil VTherm qui peut modifier l'installation. La confirmation MUST porter sur l'action et ses paramètres exacts. L'assistant MUST NOT s'autoriser seul à effectuer une écriture. Les outils MCP Home Assistant hors VTherm MUST rester limités à des opérations de consultation autorisées.

#### Scenario: Demande de modification
- **WHEN** l'utilisateur demande de modifier une règle, une consigne ou un autre paramètre VTherm
- **THEN** l'assistant présente le VTherm cible, l'action et les paramètres exacts, puis attend une confirmation explicite avant tout appel d'écriture

#### Scenario: Confirmation de l'action précise
- **WHEN** l'utilisateur confirme explicitement l'action en attente et que sa cible et ses paramètres n'ont pas changé
- **THEN** le système exécute une seule fois l'appel d'écriture correspondant et rapporte son résultat réel

#### Scenario: Confirmation absente, refusée ou ambiguë
- **WHEN** l'utilisateur ne confirme pas, refuse, ou fournit une réponse qui ne confirme pas clairement l'action exacte
- **THEN** aucun outil d'écriture n'est appelé et l'installation reste inchangée par cet appel

#### Scenario: Paramètres modifiés après confirmation
- **WHEN** la cible ou un paramètre de l'appel change après l'obtention de la confirmation
- **THEN** la confirmation précédente n'est plus valide et le système demande une nouvelle confirmation avant d'exécuter l'appel modifié

#### Scenario: Tentative d'appel d'un outil de commande
- **WHEN** le modèle tente d'appeler un outil d'écriture VTherm sans confirmation valide associée à cet appel
- **THEN** le système bloque l'appel avant toute modification

#### Scenario: Outil d'écriture Home Assistant hors VTherm
- **WHEN** le modèle tente d'utiliser un outil MCP standard Home Assistant qui modifie l'installation
- **THEN** le système refuse l'appel, car seuls les outils de consultation retenus sont autorisés hors VTherm

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