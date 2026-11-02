# Tasks

## 1. Fondations

- [x] 1.1 Créer la structure du backend, de l'interface et des tests ; vérifier que les composants démarrent et que les tests de base s'exécutent.
- [x] 1.2 Ajouter Google ADK et les dépendances nécessaires ; vérifier leur installation et le démarrage sans clé de fournisseur.
- [x] 1.3 Documenter les prérequis de développement et les commandes de test ; vérifier leur exécution sur un environnement propre.

## 2. Identité et accès

- [x] 2.1 Implémenter l'identification ingress sous HA OS et le contrôle de provenance Supervisor ; tester les en-têtes absents ou forgés et les accès directs refusés.
- [x] 2.2 Vérifier le statut actif et administrateur de l'utilisateur ingress auprès de HA ; tester les comptes non administrateurs, désactivés, supprimés et les erreurs de vérification.
- [x] 2.3 Implémenter sous HA Container la connexion HA OAuth avec PKCE et la vérification d'identité et des droits ; tester les redirections, les tentatives de falsification et les accès refusés.
- [x] 2.4 Protéger les sessions et les jetons, gérer leur expiration et leur révocation ; tester l'isolation des utilisateurs et le refus après perte des droits ou déconnexion.
- [x] 2.5 Protéger les routes de conversation, de configuration et de requête ; tester qu'aucune donnée privée ni requête n'est accessible sans administrateur vérifié.
- [x] 2.6 Documenter les parcours d'identification HA OS et Container et leurs prérequis ; vérifier les parcours décrits et les messages en cas d'accès refusé.

## 3. Données locales et secrets

- [ ] 3.1 Implémenter un stockage local protégé de la dernière conversation et de son contexte par identité vérifiée ; tester la persistance après redémarrage et l'isolation entre deux utilisateurs.
- [ ] 3.2 Implémenter la suppression de la conversation et de son contexte lors d'une nouvelle conversation ; tester l'absence de reprise et la conservation des données des autres utilisateurs.
- [ ] 3.3 Protéger les identifiants HA et les clés de fournisseurs dans le backend ; tester leur stockage, leur remplacement, leur suppression et l'absence d'accès non autorisé.
- [ ] 3.4 Masquer les secrets dans les réponses et journaux, y compris les erreurs de fournisseurs ; tester des erreurs contenant des clés et des jetons.
- [ ] 3.5 Documenter la persistance locale, la suppression des données et la conservation éventuelle par les fournisseurs ; vérifier que les procédures décrites n'affectent ni Recorder ni VTherm.

## 4. Fournisseurs et modèles

- [ ] 4.1 Implémenter l'interface de fournisseur utilisée par ADK avec une configuration propre à chaque utilisateur ; tester l'isolation des clés et paramètres entre utilisateurs.
- [ ] 4.2 Intégrer Gemini avec sa clé utilisateur ; tester la configuration, les requêtes, les appels d'outils et les erreurs sans divulgation de secret.
- [ ] 4.3 Intégrer OpenAI avec sa clé utilisateur ; tester la configuration, les requêtes, les appels d'outils et les erreurs sans divulgation de secret.
- [ ] 4.4 Intégrer Claude avec sa clé utilisateur ; tester la configuration, les requêtes, les appels d'outils et les erreurs sans divulgation de secret.
- [ ] 4.5 Intégrer Ollama avec son URL et un modèle local sans clé distante obligatoire ; tester la configuration, les appels d'outils et l'indisponibilité du serveur.
- [ ] 4.6 Vérifier pour chaque gamme des quatre fournisseurs la dernière génération et la précédente lorsqu'elles existent ; documenter les modèles compatibles testés, les incompatibilités connues et les modèles non vérifiés, avec versions et capacités d'outils, de français et d'affichage progressif.
- [ ] 4.7 Limiter le contexte et l'historique transmis selon la capacité du modèle et signaler les données tronquées ; tester les limites, la préservation des éléments nécessaires et l'absence d'envoi superflu.

## 5. MCP officiel et lecture seule

- [ ] 5.1 Connecter le backend au seul serveur MCP officiel HA avec un jeton administrateur protégé ; tester l'authentification, les erreurs et la reconnexion sans présumer d'une délégation des droits ingress.
- [ ] 5.2 Découvrir et autoriser explicitement les seules opérations de lecture vérifiées ; tester le refus côté serveur des commandes génériques, des outils VTherm d'écriture et des outils inconnus, même si le modèle tente de les appeler.
- [ ] 5.3 Vérifier les droits, l'exposition des entités et les effets de bord des outils autorisés ; tester les entités non exposées, les accès refusés et l'absence de modification HA ou VTherm.
- [ ] 5.4 Relever les capacités MCP et VTherm sur les versions prises en charge, y compris les dépendances et l'historique ; vérifier et documenter les outils disponibles, les lacunes et les données inaccessibles.
- [ ] 5.5 Fournir au responsable VTherm le contrat nécessaire pour l'outil d'historique en lecture seule : périodes et événements horodatés, pagination, droits et exposition, données manquantes et couverture des entités pertinentes ; vérifier que le contrat distingue les capacités existantes des évolutions nécessaires.
- [ ] 5.6 Intégrer l'historique et ses pages via les outils disponibles du MCP officiel ; tester les périodes, les événements, les attributs manquants, les permissions et l'absence de modification de Recorder.
- [ ] 5.7 Vérifier avec l'outil d'historique livré séparément que les événements et les données des entités pertinentes sont accessibles via le MCP officiel ; tester aussi la détection et le signalement de l'outil absent en VTherm 10.6.3.
- [ ] 5.8 Documenter la configuration du serveur MCP officiel, les entités exposées et les limites de lecture ; vérifier les étapes décrites sans activer d'outil de commande pour l'assistant.

## 6. Diagnostic et orchestration

- [ ] 6.1 Orchestrer avec ADK la recherche du VTherm et de ses dépendances pertinentes ; tester la demande de clarification lorsque plusieurs thermostats ou intentions sont possibles.
- [ ] 6.2 Construire les réponses à partir des états et historiques accessibles avec leurs sources et périodes ; tester les données actuelles, les événements passés et les informations absentes ou inaccessibles.
- [ ] 6.3 Faire distinguer faits observés, hypothèses et informations manquantes ; tester notamment le thermostat en attente, l'inhibition sans règle accessible et la puissance isolée à 50 %.
- [ ] 6.4 Fournir des conseils étayés et des liens documentaires pertinents sans modifier l'installation ; tester les recommandations de réglage et de plugin ainsi que les limites de compatibilité.
- [ ] 6.5 Encadrer la consultation documentaire et traiter les sorties externes comme des données non fiables ; tester les instructions malveillantes et le signalement lorsque le contenu d'une page n'est pas consultable.
- [ ] 6.6 Gérer les erreurs MCP et fournisseur et les réponses incomplètes ; tester les messages exploitables, la possibilité de réessayer et l'absence de conclusion fabriquée.

## 7. Conversation et configuration

- [ ] 7.1 Créer la page de conversation avec saisie, réponses et état en cours ; tester une question, une réponse interrompue, un échec et sa relance.
- [ ] 7.2 Restaurer la dernière conversation et son contexte après navigation ou redémarrage ; tester une question de suivi et la reprise de chaque utilisateur autorisé.
- [ ] 7.3 Ajouter l'action de nouvelle conversation reliée à la suppression locale ; tester que les messages et le contexte précédents ne sont plus repris.
- [ ] 7.4 Créer une page distincte de configuration du fournisseur, du modèle, de l'URL et de la clé si nécessaire ; tester les quatre fournisseurs et le retour à la conversation sans perte des messages.
- [ ] 7.5 Masquer les clés enregistrées et présenter les erreurs de configuration sans secret ; tester l'affichage, une clé invalide et un fournisseur inaccessible.
- [ ] 7.6 Informer des données envoyées aux fournisseurs distants et de leur politique de conservation ; vérifier l'information lors de la configuration et son absence d'affirmation sur la suppression distante.
- [ ] 7.7 Vérifier l'interface de conversation et de configuration sur ordinateur et mobile ; tester la lisibilité, la navigation et les états de chargement et d'erreur.

## 8. Déploiement et vérification intégrée

- [ ] 8.1 Préparer l'app HA OS avec ingress et l'accès optionnel à la barre latérale ; vérifier l'installation, les chemins relatifs et l'accès sans carte de tableau de bord.
- [ ] 8.2 Préparer le déploiement autonome pour HA Container et son accès OAuth sécurisé ; vérifier l'installation et le parcours de connexion distinct sans supposer la présence d'ingress.
- [ ] 8.3 Documenter l'installation, la configuration, les prérequis de versions et la désinstallation pour les deux parcours ; vérifier les procédures et la suppression possible des secrets et conversations sans modifier VTherm.
- [ ] 8.4 Vérifier de bout en bout, sur les versions HA et VTherm prises en charge, la connexion administrateur, l'isolation de deux utilisateurs, la reprise après redémarrage et le refus des utilisateurs non autorisés.
- [ ] 8.5 Vérifier de bout en bout les diagnostics courants et historiques, la lecture seule et les erreurs de données ou de fournisseur avec les outils MCP effectivement disponibles ; consigner les versions et les limites observées.