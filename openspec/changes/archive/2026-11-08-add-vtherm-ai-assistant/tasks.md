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
- [ ] 4.6 Compléter la matrice de compatibilité réelle des quatre fournisseurs, en partant des modèles OpenAI Luna, Terra et Sol validés par l'utilisateur ; documenter les autres modèles/générations compatibles testés, les incompatibilités connues et les modèles non vérifiés, avec versions et capacités d'outils, de français et d'affichage progressif. Les trois validations OpenAI ne clôturent pas la matrice de tous les fournisseurs.
- [ ] 4.7 Limiter les messages de conversation et les résultats d'outils transmis selon la capacité du modèle et signaler les données tronquées ; tester les limites, la préservation des éléments nécessaires et l'absence d'envoi superflu.
- [x] 4.8 Vérifier pour Gemini, OpenAI, Claude et Ollama le parcours conversationnel en streaming utilisé par l'app avec les adaptateurs installés ; ajouter des tests simulés reproductibles couvrant réponse simple, préambule puis appel d'outil et conclusion, appels d'outils successifs, interruption et erreur ; vérifier l'absence de duplication, l'événement de fin et la sauvegarde uniquement en cas de réponse complète. Distinguer ces tests de la matrice de compatibilité réelle de 4.6.

- [x] 4.9 Ajouter le catalogue de modèles par fournisseur via le backend et les API officielles, avec paramètres personnels enregistrés, liste des modèles installés sur Ollama, suggestions prédéfinies identifiées en secours et saisie manuelle. Tester pagination, récupération incomplète, chargement, liste vide, identifiants absents, échecs sans secrets, isolation du cache et réponses tardives après changement de fournisseur ; conserver le modèle configuré et distinguer disponibilité, suggestions et compatibilité vérifiée, sans génération ni installation implicite.

## 5. MCP officiel et lecture seule

- [x] 5.1 Connecter le backend au seul serveur MCP officiel HA avec un jeton administrateur protégé ; tester l'authentification, les erreurs et la reconnexion sans présumer d'une délégation des droits ingress.
- [x] 5.2 Découvrir et autoriser explicitement les seules opérations de lecture vérifiées ; tester le refus côté serveur des commandes génériques, des outils VTherm d'écriture et des outils inconnus, même si le modèle tente de les appeler.
- [ ] 5.3 Vérifier les droits, l'exposition des entités et les effets de bord des outils autorisés ; tester les entités non exposées, les accès refusés et l'absence de modification HA ou VTherm.
- [ ] 5.4 Relever les capacités MCP et VTherm sur les versions prises en charge pour les états actuels et les dépendances ; vérifier et documenter les outils disponibles, les lacunes et les données inaccessibles.
- [ ] 5.8 Documenter la configuration du serveur MCP officiel, les entités exposées et les limites de lecture ; vérifier les étapes décrites sans activer d'outil de commande pour l'assistant.

## 6. Diagnostic et orchestration

- [ ] 6.1 Orchestrer avec ADK la recherche du VTherm et de ses dépendances pertinentes ; tester la demande de clarification lorsque plusieurs thermostats ou intentions sont possibles.
- [ ] 6.2 Construire les réponses à partir des états actuels accessibles avec leurs sources et instants connus ; tester les données présentes et les informations absentes ou inaccessibles, sans reconstruire le passé.
- [ ] 6.3 Faire distinguer faits observés, hypothèses et informations manquantes ; tester notamment le thermostat en attente, l'inhibition sans règle accessible et la puissance isolée à 50 %.
- [ ] 6.4 Fournir des conseils étayés par les informations accessibles sans modifier l'installation ; tester les recommandations de réglage et de plugin ainsi que les limites de compatibilité, sans prétendre avoir consulté une documentation non vérifiée.
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

- [x] 7.10 Ajouter la date et l'heure en petits caractères avant « Vous » et « Assistant », avec instants conservés en UTC et formatage dans la langue et le fuseau du navigateur. Tester envoi de question, premier fragment de réponse et stabilité pendant le streaming, navigation, rechargement, redémarrage, changement de fuseau, changements d'heure et messages anciens sans date connue ; vérifier lisibilité sur ordinateur et mobile sans date inventée.
- [x] 7.11 Ajouter l'inventaire déterministe des VTherm au début de la première conversation vierge et de chaque nouvelle conversation, avant la première question, via le seul outil MCP de liste autorisé et le jeton personnel. Afficher compte, noms et identifiants climate ; tester exposition et droits, absence de clé fournisseur, chargement, liste vide, jeton absent, outil manquant, erreurs sûres et relance, conservation de l'inventaire initial et de son instant sans doublon à la restauration, suppression et isolation entre utilisateurs. Ne pas utiliser le modèle ni modifier l'exposition ou HA ; tester aussi les réponses tardives d'une conversation remplacée et l'affichage ordinateur/mobile.

## 8. Déploiement et vérification intégrée

- [ ] 8.1 Préparer l'app HA OS avec ingress et l'accès optionnel à la barre latérale ; vérifier l'installation, les chemins relatifs et l'accès sans carte de tableau de bord.
- [ ] 8.2 Préparer le déploiement autonome pour HA Container et son accès OAuth sécurisé ; vérifier l'installation et le parcours de connexion distinct sans supposer la présence d'ingress.
- [ ] 8.3 Documenter l'installation, la configuration, les prérequis de versions et la désinstallation pour les deux parcours ; vérifier les procédures et la suppression possible des secrets et conversations sans modifier VTherm.
- [ ] 8.4 Vérifier de bout en bout, sur les versions HA et VTherm prises en charge, la connexion administrateur, l'isolation de deux utilisateurs, la reprise après redémarrage et le refus des utilisateurs non autorisés.
- [ ] 8.5 Vérifier de bout en bout les diagnostics sur les états actuels, la lecture seule et les erreurs de données ou de fournisseur avec les outils MCP effectivement disponibles ; consigner les versions et les limites observées.

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

## Révision d'affichage validée le 2026-11-08

- Règles validées par l'utilisateur : horodatages dans la langue et le fuseau du navigateur, catalogue de modèles dynamique avec secours et saisie manuelle, inventaire MCP au début d'une nouvelle conversation sans doublon à la restauration.
- Tâches ajoutées et non implémentées : 4.9, 7.10 et 7.11. Les tâches déjà cochées restent inchangées ; ces nouveaux comportements ne sont pas couverts par leur validation antérieure.
- Avancement après ajout : 34 sur 55 tâches. Cette révision concerne uniquement les artefacts de planification ; aucun code, déploiement ou publication n'est effectué.

## Implémentation du lot d'affichage du 2026-11-08

- Tâches 4.9, 7.10 et 7.11 terminées ; avancement : 37 sur 55. Les autres tâches ouvertes conservent leurs critères et limites de validation réelle.
- Dates : instants UTC ajoutés aux messages JSON sans inventer ceux de l'historique ancien ; question horodatée à l'envoi et réponse au premier fragment affichable. Tests de route, streaming, reprise après redémarrage, trois locales/fuseaux, changement d'heure et nouveau fuseau de reprise sur ordinateur/mobile.
- Catalogue : GET officiels des quatre fournisseurs, identifiants personnels enregistrés, pagination bornée et récupération partielle signalée ; pas de cache partagé, de génération ou d'installation. Suggestions documentées et saisie manuelle conservée. Tests d'erreurs sans secrets, clés/URL remplacées, isolation et réponses tardives ; disponibilité distincte de la compatibilité réelle toujours ouverte en 4.6.
- Inventaire : lecture MCP autorisée, noms et identifiants affichés sans HTML externe, compte validé, résultat vide distinct d'une erreur ; sauvegarde protégée avec la version de conversation, reprise sans doublon et refus des résultats après suppression. Tests de droits, jeton absent sans substitution Supervisor, outil manquant, absence de génération, erreurs, relance, isolation et affichage ordinateur/mobile.
- Commandes : `arch -arm64 .venv/bin/python -m pytest -q --ignore=tests/test_frontend.py --ignore=tests/test_packaging.py --tb=short` : 253 tests réussis ; `arch -arm64 .venv/bin/python -m pytest -q tests/test_frontend.py tests/test_packaging.py --tb=short` : 92 réussis et 12 contrôles Docker ignorés sans image de test. Total : 345 réussites ; avertissements de dépendances distincts des échecs.
- Captures Playwright temporaires inspectées pour les dates, l'inventaire et le catalogue sur ordinateur/mobile ; logo chargé et absence de débordement horizontal vérifiés. Ces preuves utilisent des services simulés, sans lecture de conversations privées ni essai des nouveaux parcours sur HA OS réel.
- Aucun changement d'exposition, de chauffage, de version publiée, de catalogue public ou d'image de release. Les tags `0.1.0` et `0.1.1` restent inchangés.

## Clôture du 2026-11-08

- L'utilisateur autorise explicitement la synchronisation des trois specs principales et l'archivage avec réserves sous `openspec/changes/archive/2026-11-08-add-vtherm-ai-assistant/`.
- Le bilan reste 36 tâches terminées sur 51. Les 15 cases ouvertes sont conservées comme travaux ou validations restant à reprendre ; la clôture ne les transforme pas en succès et ne certifie pas toutes les exigences du référentiel.
- Les preuves locales et les confirmations HA réelles restent distinctes. Luna, Terra et Sol ainsi que les trois évolutions de `0.1.2` gardent leurs validations consignées, sans élargissement aux autres modèles ou scénarios non vérifiés.
- L'historique Home Assistant et la recherche documentaire restent reportés au change suivant. Leurs preuves et composants déjà livrés ne sont pas supprimés. Aucun nouveau change, code, commit, push, publication ou opération HA n'est inclus dans cette clôture.

## Réduction de périmètre et preuves du 2026-11-08

- L'utilisateur retire l'historique Home Assistant et la recherche documentaire du périmètre courant pour les reprendre dans le change suivant. Les tâches actives 5.5, 5.6, 5.7 et 6.5 sont retirées, pas cochées à tort ; les références à ces numéros dans les bilans antérieurs sont historiques et restent conservées. Les notices d'installation/sécurité, la mémoire de conversation et les horodatages restent dans le lot.
- L'ancien 5.5 était un contrat déjà livré ; il reste conservé dans le dépôt et dans les preuves antérieures. Les anciens 5.6 et 5.7 restent à intégrer/vérifier dans le prochain périmètre. L'ancien 6.5 reste à finaliser : recherche officielle FR/EN/DE, citations, limites de sources, erreurs et données externes non fiables. Aucun report n'est une validation de ces fonctionnalités.
- OpenAI Luna, Terra et Sol : compatibilité nominale confirmée par les essais de l'utilisateur. L'identifiant `gpt-6-luna` est relevé ; les identifiants exacts de Terra et Sol et une matrice détaillée de capacités ne sont pas inventés. 4.6 reste ouverte pour les modèles et fournisseurs non vérifiés.
- L'utilisateur confirme également les trois évolutions déployées en `0.1.2` : catalogue dynamique, horodatages et inventaire initial. La publication a passé 357 tests locaux avec Docker et une CI réussie ; ces résultats restent distincts de ses observations HA réelles.
- Nouveau comptage : 36 tâches terminées sur 51, soit 15 ouvertes. La baisse d'une tâche cochée vient du retrait du contrat d'historique 5.5, pas d'une régression. Aucun code, commit, push, archivage ou synchronisation des specs n'est effectué par cette révision.