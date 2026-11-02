# Spec Delta

## Purpose

Permettre à l'utilisateur de choisir un modèle compatible tout en protégeant ses identifiants et en explicitant les échanges de données.

## ADDED Requirements

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