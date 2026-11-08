# model-configuration Specification

## Purpose

Permettre à l'utilisateur de choisir un modèle compatible tout en protégeant ses identifiants et en explicitant les échanges de données.

## Requirements

### Requirement: Page de configuration du modèle
L'app MUST proposer une page de configuration distincte de la page de conversation, permettant de choisir le fournisseur et de saisir ses paramètres, notamment la clé API et l'URL lorsqu'elles sont nécessaires.

#### Scenario: Configuration du fournisseur
- **WHEN** l'utilisateur ouvre la page de configuration du modèle
- **THEN** il peut choisir le fournisseur et renseigner les paramètres nécessaires sans utiliser la page de conversation

#### Scenario: Retour à la conversation
- **WHEN** l'utilisateur revient à la page de conversation depuis la configuration
- **THEN** les messages de la conversation en cours restent affichés

### Requirement: Choix d'un modèle compatible
Le système MUST permettre de configurer OpenAI, Claude (Anthropic), Gemini (Google) et Ollama dès la première version, avec une clé personnelle pour les fournisseurs distants et un modèle Ollama local compatible.

#### Scenario: Fournisseurs pris en charge
- **WHEN** l'utilisateur choisit un fournisseur pour configurer l'assistant
- **THEN** OpenAI, Claude, Gemini et Ollama sont proposés

#### Scenario: Modèle distant
- **WHEN** l'utilisateur sélectionne un fournisseur distant compatible et renseigne les paramètres nécessaires
- **THEN** les demandes de l'assistant utilisent le modèle configuré avec les identifiants de cet utilisateur

#### Scenario: Modèle local
- **WHEN** l'utilisateur sélectionne un modèle local compatible qui ne nécessite pas de clé
- **THEN** la configuration ne requiert pas de clé de fournisseur distant

### Requirement: Catalogue de modèles par fournisseur
Le système MUST proposer un catalogue dynamique pour le fournisseur choisi, récupéré par le backend sans exposer de secrets, avec des suggestions prédéfinies identifiées en secours et une saisie manuelle toujours disponible. Il MUST distinguer disponibilité et compatibilité vérifiée avec l'assistant. L'interface MUST distinguer chargement, liste vide et erreur sans remplacer automatiquement le modèle configuré.

#### Scenario: Catalogue distant
- **WHEN** l'utilisateur choisit OpenAI, Claude ou Gemini et dispose des identifiants personnels nécessaires enregistrés
- **THEN** le backend récupère les modèles annoncés par l'API officielle et l'interface propose ceux du fournisseur sélectionné
- **AND** les statuts de compatibilité vérifiée, d'incompatibilité connue ou de modèle non vérifié restent distincts de cette disponibilité

#### Scenario: Catalogue Ollama
- **WHEN** l'utilisateur choisit Ollama avec une URL configurée et accessible
- **THEN** la liste dynamique présente les modèles installés retournés par ce serveur, sans clé de fournisseur distant obligatoire ni téléchargement de modèle

#### Scenario: Catalogue inaccessible ou identifiants absents
- **WHEN** l'API de catalogue est inaccessible ou que les paramètres nécessaires ne sont pas encore enregistrés
- **THEN** l'interface signale cette limite sans secret, propose des suggestions prédéfinies identifiées comme telles et conserve la saisie manuelle
- **AND** elle ne prétend pas que ces suggestions sont accessibles avec les identifiants de l'utilisateur ou installées sur Ollama

#### Scenario: Changement de fournisseur et configuration existante
- **WHEN** l'utilisateur change de fournisseur ou que le catalogue est actualisé
- **THEN** aucune réponse tardive du fournisseur précédent n'est affichée comme le catalogue du nouveau fournisseur
- **AND** le modèle configuré n'est pas remplacé automatiquement, même s'il n'apparaît pas dans le catalogue

#### Scenario: Catalogue vide
- **WHEN** l'API renvoie avec succès une liste vide
- **THEN** l'interface indique qu'aucun modèle n'a été retourné, sans présenter une panne comme certaine, et laisse la saisie manuelle disponible

### Requirement: Compatibilité des générations de modèles
Pour chaque gamme de chaque fournisseur, le système MUST prendre en charge la dernière génération et la précédente lorsqu'elles existent et sont compatibles. Les modèles et versions pris en charge MUST être vérifiés et documentés. La documentation MUST distinguer les modèles vérifiés compatibles, les incompatibilités connues et les modèles non encore vérifiés.

#### Scenario: Générations d'une gamme
- **WHEN** une gamme d'un fournisseur propose une dernière génération et une génération précédente compatibles avec l'assistant
- **THEN** les deux générations sont prises en charge et leur compatibilité est vérifiée et documentée

#### Scenario: Modèle incompatible ou non vérifié
- **WHEN** un modèle d'une gamme, y compris une famille Ollama, est incompatible ou n'a pas encore été vérifié
- **THEN** la documentation indique son incompatibilité connue ou son statut non vérifié, sans présenter ce dernier comme une incompatibilité

### Requirement: Protection des identifiants
Le système MUST protéger les clés contre l'exposition dans l'interface de l'app, les réponses, les journaux et la configuration visible par des utilisateurs non autorisés.

#### Scenario: Clé enregistrée
- **WHEN** une clé de fournisseur est enregistrée
- **THEN** elle n'est pas réaffichée en clair et n'apparaît ni dans les réponses ni dans les journaux

#### Scenario: Échec du fournisseur
- **WHEN** un fournisseur renvoie une erreur contenant des informations sensibles
- **THEN** l'erreur présentée et journalisée ne divulgue pas la clé

### Requirement: Transparence des échanges distants
Le système MUST informer l'utilisateur qu'un modèle distant reçoit les éléments de conversation et les données de l'installation nécessaires à la réponse et que leur conservation dépend du fournisseur.

#### Scenario: Configuration d'un modèle distant
- **WHEN** l'utilisateur configure un fournisseur distant
- **THEN** il est informé des données susceptibles d'être transmises et du rôle du fournisseur dans leur conservation

### Requirement: Erreur de configuration
Le système MUST signaler une configuration de modèle invalide ou inaccessible sans révéler d'identifiant secret.

#### Scenario: Clé invalide
- **WHEN** le fournisseur refuse la clé configurée
- **THEN** l'utilisateur reçoit un message d'erreur exploitable sans que la clé soit affichée