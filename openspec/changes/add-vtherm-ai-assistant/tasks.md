# Tasks

## Bilan de revue du 2026-11-03

La revue a confirmé 123 tests réussis dans le venv Python 3.14 et une validation OpenSpec stricte réussie. Ces résultats ne démontrent pas la compatibilité avec des installations HA, VTherm ou des fournisseurs réels : les échanges externes des tests sont simulés. Les tâches d'intégration et de validation réelle restent ouvertes, notamment 4.6, 5.3 à 5.8 et 8.4 à 8.5, à l'exception du contrat rédigé en 5.5.

Constats initiaux de la revue, avant le lot correctif ci-dessous :

- Streaming ADK : un préambule textuel suivi d'un appel d'outil puis d'une conclusion provoque une erreur de cohérence ; la conclusion est affichée mais l'échange n'est pas sauvegardé. Correction suivie en 6.7 et validation de l'interface en 7.1.
- Formulaires : une erreur réseau pendant l'enregistrement du jeton HA ne produit aucun retour utilisateur. Gestion des rejets de requêtes suivie en 7.9 et validation en 7.4, 7.5 et 7.7.
- Secrets saisis : la clé fournisseur et le jeton HA restent dans les champs masqués après retour à la conversation ; le jeton reste également présent après une erreur réseau. Correction suivie en 7.8 ; aucune fuite interutilisateur n'a été démontrée par ce constat.

Vérifications manquantes lors de la revue initiale :

- Les tests d'appels d'outils OpenAI, Claude et Ollama utilisent le mode non progressif, alors que le parcours conversationnel active le streaming. La couverture du parcours réellement utilisé est suivie en 4.8, sans présumer des compatibilités réelles de 4.6.
- Aucun test navigateur reproductible n'est présent dans la suite du dépôt pour les parcours conversation et configuration ; les contrôles ponctuels de la revue ne remplacent pas cette couverture. Les tâches 7.1, 7.4, 7.5 et 7.7 sont rouvertes pour leur validation restante.
- La persistance, l'isolation, la suppression et la restauration de messages de suivi sont déjà partiellement testées ; 7.2 reste ouverte jusqu'à validation complète de la reprise côté interface et du contexte nécessaire.
- Le contrat d'historique de 5.5 est rédigé et distingue proposition et capacités existantes ; sa transmission effective au responsable VTherm n'est pas vérifiable dans le dépôt et reste à confirmer avant de considérer la remise comme acquise.

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

- [x] 3.1 Implémenter un stockage local protégé de la dernière conversation et de son contexte par identité vérifiée ; tester la persistance après redémarrage et l'isolation entre deux utilisateurs.
- [x] 3.2 Implémenter la suppression de la conversation et de son contexte lors d'une nouvelle conversation ; tester l'absence de reprise et la conservation des données des autres utilisateurs.
- [x] 3.3 Protéger les identifiants HA et les clés de fournisseurs dans le backend ; tester leur stockage, leur remplacement, leur suppression et l'absence d'accès non autorisé.
- [x] 3.4 Compléter et vérifier le masquage des secrets dans les réponses et journaux sur les parcours fournisseur, MCP et authentification ; tester les clés de fournisseurs, jetons HA, jetons OAuth et identifiants de session, y compris les erreurs et les secrets répartis entre fragments de streaming, sans considérer les seuls tests de réponses comme une preuve de protection des journaux.
- [x] 3.5 Documenter la persistance locale, la suppression des données et la conservation éventuelle par les fournisseurs ; vérifier que les procédures décrites n'affectent ni Recorder ni VTherm.

## 4. Fournisseurs et modèles

- [x] 4.1 Implémenter l'interface de fournisseur utilisée par ADK avec une configuration propre à chaque utilisateur ; tester l'isolation des clés et paramètres entre utilisateurs.
- [x] 4.2 Intégrer Gemini avec sa clé utilisateur ; tester la configuration, les requêtes, les appels d'outils et les erreurs sans divulgation de secret.
- [x] 4.3 Intégrer OpenAI avec sa clé utilisateur ; tester la configuration, les requêtes, les appels d'outils et les erreurs sans divulgation de secret.
- [x] 4.4 Intégrer Claude avec sa clé utilisateur ; tester la configuration, les requêtes, les appels d'outils et les erreurs sans divulgation de secret.
- [x] 4.5 Intégrer Ollama avec son URL et un modèle local sans clé distante obligatoire ; tester la configuration, les appels d'outils et l'indisponibilité du serveur.
- [ ] 4.6 Vérifier pour chaque gamme des quatre fournisseurs la dernière génération et la précédente lorsqu'elles existent ; documenter les modèles compatibles testés, les incompatibilités connues et les modèles non vérifiés, avec versions et capacités d'outils, de français et d'affichage progressif.
- [ ] 4.7 Limiter le contexte et l'historique transmis selon la capacité du modèle et signaler les données tronquées ; tester les limites, la préservation des éléments nécessaires et l'absence d'envoi superflu.
- [x] 4.8 Vérifier pour Gemini, OpenAI, Claude et Ollama le parcours conversationnel en streaming utilisé par l'app avec les adaptateurs installés ; ajouter des tests simulés reproductibles couvrant réponse simple, préambule puis appel d'outil et conclusion, appels d'outils successifs, interruption et erreur ; vérifier l'absence de duplication, l'événement de fin et la sauvegarde uniquement en cas de réponse complète. Distinguer ces tests de la matrice de compatibilité réelle de 4.6.

## 5. MCP officiel et lecture seule

- [x] 5.1 Connecter le backend au seul serveur MCP officiel HA avec un jeton administrateur protégé ; tester l'authentification, les erreurs et la reconnexion sans présumer d'une délégation des droits ingress.
- [x] 5.2 Découvrir et autoriser explicitement les seules opérations de lecture vérifiées ; tester le refus côté serveur des commandes génériques, des outils VTherm d'écriture et des outils inconnus, même si le modèle tente de les appeler.
- [ ] 5.3 Vérifier les droits, l'exposition des entités et les effets de bord des outils autorisés ; tester les entités non exposées, les accès refusés et l'absence de modification HA ou VTherm.
- [ ] 5.4 Relever les capacités MCP et VTherm sur les versions prises en charge, y compris les dépendances et l'historique ; vérifier et documenter les outils disponibles, les lacunes et les données inaccessibles.
- [x] 5.5 Fournir au responsable VTherm le contrat nécessaire pour l'outil d'historique en lecture seule : périodes et événements horodatés, pagination, droits et exposition, données manquantes et couverture des entités pertinentes ; vérifier que le contrat distingue les capacités existantes des évolutions nécessaires.
- [ ] 5.6 Intégrer l'historique et ses pages via les outils disponibles du MCP officiel ; tester les périodes, les événements, les attributs manquants, les permissions et l'absence de modification de Recorder.
- [ ] 5.7 Vérifier avec l'outil d'historique livré séparément que les événements et les données des entités pertinentes sont accessibles via le MCP officiel ; tester aussi la détection et le signalement de l'outil absent en VTherm 10.6.3.
- [ ] 5.8 Documenter la configuration du serveur MCP officiel, les entités exposées et les limites de lecture ; vérifier les étapes décrites sans activer d'outil de commande pour l'assistant.

## 6. Diagnostic et orchestration

- [ ] 6.1 Orchestrer avec ADK la recherche du VTherm et de ses dépendances pertinentes ; tester la demande de clarification lorsque plusieurs thermostats ou intentions sont possibles.
- [ ] 6.2 Construire les réponses à partir des états et historiques accessibles avec leurs sources et périodes ; tester les données actuelles, les événements passés et les informations absentes ou inaccessibles.
- [ ] 6.3 Faire distinguer faits observés, hypothèses et informations manquantes ; tester notamment le thermostat en attente, l'inhibition sans règle accessible et la puissance isolée à 50 %.
- [ ] 6.4 Fournir des conseils étayés et des liens documentaires pertinents sans modifier l'installation ; tester les recommandations de réglage et de plugin ainsi que les limites de compatibilité.
- [ ] 6.5 Encadrer la recherche dans la documentation officielle VTherm : choisir la locale française, anglaise ou allemande selon la langue de l'utilisateur, limiter les requêtes à l'hôte et aux pages documentaires officiels, citer les pages sources et distinguer leurs conseils des faits observés. Traiter les résultats externes comme des données non fiables ; tester les trois locales, le contenu contenant des instructions malveillantes, l'absence de résultat et les échecs de consultation sans solution inventée.
- [x] 6.6 Gérer les erreurs MCP et fournisseur et les réponses incomplètes ; tester les messages exploitables sans secret, la possibilité de réessayer, l'absence de conclusion fabriquée et de sauvegarde d'un échange incomplet ; distinguer un véritable échec externe d'une réponse valide contenant des étapes d'outils, corrigée en 6.7.
- [x] 6.7 Corriger l'accumulation du texte progressif entre les étapes ADK pour accepter un préambule suivi d'un ou plusieurs appels d'outils puis d'une conclusion ; ajouter un test de non-régression reproduisant l'échec constaté et vérifier que le texte n'est pas dupliqué, que l'échange complet est sauvegardé et qu'un événement de fin remplace l'erreur injustifiée. Préserver la détection des réponses réellement interrompues ou incohérentes et le masquage entre fragments.
- [ ] 6.8 Généraliser le signalement intelligible et traçable des erreurs à tous les parcours : authentification, configuration, réseau, MCP, fournisseur, streaming, chargement, restauration et stockage. Relier les messages utilisateur aux diagnostics sûrs par une référence d'incident opaque lorsque le backend est joignable ; distinguer les causes vérifiées, les causes inconnues et les erreurs purement locales au navigateur, avec une correction ou relance pertinente. Tester côté backend et navigateur les catégories d'échec, la corrélation, les droits d'accès, l'absence de secrets et de contenus bruts, la conservation des données valides et l'absence de succès annoncé à tort. Les diagnostics techniques déjà ajoutés ne suffisent pas à valider ce scénario utilisateur général.

## 7. Conversation et configuration

- [x] 7.1 Finaliser la validation de la page de conversation existante avec saisie, réponses et état en cours ; tester dans le navigateur une question, une réponse avec préambule et appel d'outil après correction de 6.7, une réponse interrompue, un échec et sa relance, sans présenter une réponse incomplète comme terminée.
- [x] 7.2 Compléter la validation de la restauration de la dernière conversation et de son contexte déjà partiellement implémentée ; tester dans le navigateur le retour après navigation et rechargement, puis la reprise après redémarrage du backend et réauthentification si nécessaire ; vérifier une question de suivi pour chaque utilisateur autorisé, l'isolation et l'absence de reprise après nouvelle conversation. Vérifier quels faits et résultats d'outils nécessaires au suivi sont effectivement conservés, au-delà du seul réaffichage des messages.
- [x] 7.3 Ajouter l'action de nouvelle conversation reliée à la suppression locale ; tester que les messages et le contexte précédents ne sont plus repris.
- [x] 7.4 Finaliser la validation de la page distincte de configuration existante pour le fournisseur, le modèle, l'URL et la clé si nécessaire ; tester les quatre fournisseurs, le retour à la conversation sans perte des messages et les échecs de chargement ou d'enregistrement après correction de 7.9.
- [x] 7.5 Compléter le masquage des clés et la présentation des erreurs de configuration sans secret ; tester l'affichage, une clé invalide, un fournisseur inaccessible et une panne réseau, ainsi que l'effacement des champs sensibles prévu en 7.8.
- [x] 7.6 Informer des données envoyées aux fournisseurs distants et de leur politique de conservation ; vérifier l'information lors de la configuration et son absence d'affirmation sur la suppression distante.
- [x] 7.7 Ajouter au dépôt des tests navigateur reproductibles sur ordinateur et mobile pour la conversation et la configuration ; vérifier la lisibilité, l'absence de débordement, la navigation, les états de chargement et d'erreur, l'interruption et la relance d'une réponse, la nouvelle conversation, la reprise après rechargement et la non-conservation des secrets saisis. Utiliser des services simulés sans secrets réels pour cette couverture et conserver les validations HA réelles en 8.4 et 8.5.
- [x] 7.8 Effacer les champs de clé fournisseur et de jeton HA lors de la sortie de configuration, y compris via une nouvelle conversation, et après chaque tentative d'enregistrement, réussie ou non ; tester aussi les rejets réseau et vérifier qu'aucun secret saisi n'est conservé dans les champs masqués ou recopié dans les messages d'erreur.
- [x] 7.9 Gérer explicitement les erreurs réseau des actions de configuration et de suppression, ainsi que le chargement de la configuration et la nouvelle conversation ; afficher un message exploitable sans secret, permettre une nouvelle tentative et ne pas annoncer un succès ni effacer la conversation affichée si la suppression serveur échoue ; tester les réponses HTTP d'échec et les rejets de requêtes avec les contrôles utilisables après l'erreur.

## 8. Déploiement et vérification intégrée

- [ ] 8.1 Préparer l'app HA OS avec ingress et l'accès optionnel à la barre latérale ; vérifier l'installation, les chemins relatifs et l'accès sans carte de tableau de bord.
- [ ] 8.2 Préparer le déploiement autonome pour HA Container et son accès OAuth sécurisé ; vérifier l'installation et le parcours de connexion distinct sans supposer la présence d'ingress.
- [ ] 8.3 Documenter l'installation, la configuration, les prérequis de versions et la désinstallation pour les deux parcours ; vérifier les procédures et la suppression possible des secrets et conversations sans modifier VTherm.
- [ ] 8.4 Vérifier de bout en bout, sur les versions HA et VTherm prises en charge, la connexion administrateur, l'isolation de deux utilisateurs, la reprise après redémarrage et le refus des utilisateurs non autorisés.
- [ ] 8.5 Vérifier de bout en bout les diagnostics courants et historiques, la lecture seule et les erreurs de données ou de fournisseur avec les outils MCP effectivement disponibles ; consigner les versions et les limites observées.

## Prochain lot prioritaire : fiabilisation de la conversation et des erreurs

Ordre recommandé, sans démarrer le développement dans cette révision :

1. Corriger le streaming multi-étapes en 6.7, puis étendre la couverture des quatre adaptateurs en 4.8.
2. Compléter la protection des sorties et journaux en 3.4 et le traitement des échecs et réponses incomplètes en 6.6.
3. Corriger la gestion des erreurs réseau et la conservation des champs sensibles en 7.8 et 7.9, puis revalider 7.4 et 7.5.
4. Ajouter les tests navigateur de 7.7, revalider 7.1 et terminer les vérifications de reprise de 7.2.

Ce lot ne clôt ni la compatibilité réelle des modèles de 4.6, ni les vérifications MCP et historique de la section 5, ni les essais intégrés de la section 8. L'historique reste dépendant de l'outil livré séparément et de la vérification de son contrat effectif.

## Validation du lot correctif du 2026-11-03

- Tâches clôturées après vérification : 3.4, 4.8, 6.6, 6.7, 7.1, 7.2, 7.4, 7.5, 7.7, 7.8 et 7.9 ; avancement : 34 sur 51.
- Suite complète : 216 tests réussis, dont 52 tests Chromium sur ordinateur et mobile ; 4 avertissements issus des dépendances restent présents.
- Streaming : 36 scénarios sur les adaptateurs installés des quatre fournisseurs, avec réponses simples, préambules, outils successifs, troncatures et erreurs ; appels aux SDK simulés, sans validation de compatibilité réelle des modèles.
- Confidentialité : tests des réponses et journaux, des secrets fragmentés, des transports sensibles et des identifiants OAuth, HA et fournisseur ; champs sensibles vidés lors de la navigation et des tentatives d'enregistrement.
- Reprise : preuves MCP masquées sauvegardées avec les événements utiles à la conversation, sans fragments partiels ni parties de raisonnement interne ; tests navigateur reliés au backend recréé sur le même stockage, isolation de deux utilisateurs et effacement par nouvelle conversation. L'identification HA et les fournisseurs restent simulés dans ces essais.
- Limite toujours ouverte en 4.7 : la borne actuelle sur les messages ne borne pas les résultats d'outils ; la limitation du contexte selon le modèle reste à implémenter.
- La validation de 4.6 nécessite les modèles et environnements réels à tester ; les tâches MCP, historique et déploiement non cochées ne sont pas validées par ce lot.