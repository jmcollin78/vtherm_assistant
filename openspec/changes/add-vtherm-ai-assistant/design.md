# Design

## Context

Voir la proposition pour le besoin et les limites fonctionnelles. Le dépôt ne contient actuellement que des documents OpenSpec et un README minimal : il n'existe ni backend, ni carte, ni tests à réutiliser dans ce projet.

La [PR VTherm #2160](https://github.com/jmcollin78/versatile_thermostat/pull/2160) fournit des outils natifs de liste, d'état et de diagnostic, mais aussi des outils de commande. Ils passent par l'API LLM de Home Assistant, utilisent les VTherm exposés à Assist et ne garantissent pas à eux seuls que l'ensemble de l'assistant soit en lecture seule. La branche principale VTherm contient également un outil d'historique ; sa disponibilité dépend de la version installée et des données enregistrées. Les capacités et conditions d'accès effectives devront être vérifiées sur les versions prises en charge.

## Goals / Non-Goals

**Goals:**

- Séparer l'interface de l'app, le traitement, l'accès MCP aux données et les fournisseurs de modèle pour faciliter leur évolution.
- Garantir lecture seule, confidentialité des identifiants et signalement des données indisponibles.
- Permettre l'utilisation sous Home Assistant OS et Container, sans supposer que le système d'apps HA existe sous Container.

**Non-Goals:**

- Remplacer Assist, contrôler les thermostats ou conserver un historique des conversations précédentes.
- Garantir l'accès à la configuration privée de tout plugin tiers, ni reconstruire un historique non enregistré.
- Fournir une carte de tableau de bord ou intégrer un serveur MCP tiers tel que ha-mcp.
- Choisir dès ce design les bibliothèques de modèles ou le mécanisme d'intégration propre à Home Assistant Container.

## Decisions

### App et interface intégrée

Une app Home Assistant héberge l'interface web et le traitement. Elle comporte une page de conversation et une page distincte de configuration du fournisseur et de ses paramètres. La dernière conversation de chaque utilisateur est restaurée à son retour dans l'app, y compris après un redémarrage ; un bouton permet d'effacer sa conversation et d'en commencer une nouvelle. Sous Home Assistant OS, l'accès passe par ingress et l'app peut être affichée dans la barre latérale, sans ajouter de carte aux tableaux de bord. L'interface permet de saisir les clés des fournisseurs mais ne les conserve pas ; le traitement les protège, contrôle l'accès aux sources, gère la conversation et dialogue avec le modèle. Cette solution évite la distribution et la configuration d'une carte, mais nécessite toujours une interface web et son backend.

En première version, l'app réserve les conversations, la configuration et les requêtes aux administrateurs HA dont l'identité et les droits sont vérifiés. Sous HA OS, ingress peut transmettre l'identifiant via `X-Remote-User-Id` ; l'app n'accepte les connexions ingress que du Supervisor afin de ne pas faire confiance à des en-têtes forgés. Le statut administrateur doit être vérifié à partir d'une source HA fiable ; l'identifiant seul ne le démontre pas. Une piste consiste à consulter la liste des utilisateurs HA par WebSocket avec un accès administrateur protégé et à vérifier le compte correspondant, son activité et ses droits. Sous Container, chaque utilisateur se connecte à son compte HA par OAuth avec PKCE ; son identité et son statut administrateur sont vérifiés auprès de HA, notamment par `auth/current_user`. Les jetons et la session sont protégés et les accès sont refusés lorsque la session ou les droits ne sont plus valides. Si l'identité ou les droits ne peuvent pas être vérifiés, aucune conversation sauvegardée n'est exposée et aucune requête n'est exécutée. Une interface vierge peut être affichée sans accès aux données privées. Vérifier ces mécanismes, notamment les redirections OAuth, la révocation, l'isolation des sessions et le refus des en-têtes forgés, sur les versions HA prises en charge.

### Accès aux données et preuves

Le traitement est client du seul serveur MCP officiel de Home Assistant ; ha-mcp n'est pas retenu. Il s'authentifie auprès du MCP avec un jeton administrateur HA protégé par l'app, indépendamment de l'identité ingress : ce jeton ne délègue pas automatiquement les droits de l'utilisateur connecté. L'accès à l'app reste donc réservé aux administrateurs vérifiés et les outils utilisables restent limités à la lecture. Vérifier le mécanisme de connexion MCP et la compatibilité des versions retenues. Le traitement utilise les outils VTherm natifs disponibles et les autres outils de lecture exposés par ce serveur pour les dépendances et l'historique, selon les versions et autorisations. Si cette couverture est insuffisante, faire évoluer les outils MCP/LLM de VTherm et les exposer par le serveur officiel, plutôt qu'ajouter un second serveur MCP. Vérifier la faisabilité de chaque évolution ; une donnée inaccessible reste signalée comme telle.

Présenter les données avec leur source et leur période ; distinguer les valeurs actuelles des événements enregistrés. La configuration d'un plugin tiers n'est utilisable que si une interface autorisée la rend accessible. Une réponse partielle doit expliquer ses limites plutôt que déduire une règle cachée.

Pour les questions sur le passé, utiliser l'historique déjà disponible et accessible pour la période pertinente, sans modifier la durée de rétention de Recorder. La période effectivement exploitable dépend des données enregistrées et des outils disponibles ; signaler les données manquantes ou inaccessibles.

Les outils natifs renvoient des liens documentaires ; leur présence n'implique pas que le modèle lise automatiquement les pages. La consultation de la documentation doit disposer d'un mécanisme explicite ou, à défaut, fournir les liens avec une limite clairement indiquée. La documentation et les sorties externes sont des données non fiables, jamais des instructions prioritaires.

### Isolation en lecture seule

Le traitement ne met à disposition du modèle que des opérations de lecture explicitement autorisées et refuse les autres appels côté serveur. Les services génériques de commande et les outils VTherm d'écriture ne font pas partie de cette liste, même s'ils sont disponibles dans HA. Les droits de l'utilisateur HA et l'exposition des entités doivent être vérifiés ; le simple prompt ou les annotations des outils ne constituent pas une barrière suffisante. Toute interface de diagnostic doit aussi être contrôlée pour ses effets de bord.

### Conversation sauvegardée et confidentialité

La dernière conversation et son contexte sont conservés localement dans un stockage protégé pour chaque utilisateur identifié, afin de les reprendre après navigation ou redémarrage de l'app. L'accès est réservé à son propriétaire autorisé ; le backend détermine celui-ci à partir de l'identité vérifiée, et non d'un identifiant fourni librement par le client. Le bouton de nouvelle conversation supprime uniquement les messages et le contexte de cet utilisateur du stockage de l'app ; aucun historique des conversations précédentes n'est conservé par l'assistant. Les données Recorder restent indépendantes de cette mémoire. Les identifiants sont configurés et conservés dans le composant de confiance, avec contrôle d'accès et masquage dans les sorties et journaux. Le fournisseur distant peut appliquer sa propre politique de conservation : l'utilisateur en est informé et la suppression locale ne garantit pas celle des données chez ce fournisseur. Limiter les données transmises au strict nécessaire.

### Erreurs intelligibles et traçabilité sécurisée

L'application, et non le modèle, classe les erreurs prises en charge sur tous les parcours : authentification, configuration, réseau, MCP, fournisseur, streaming, chargement, restauration et stockage. Elle transforme les métadonnées vérifiées en messages compréhensibles indiquant l'action en échec, le composant identifié et une correction ou relance pertinente. Les catégories et actions proviennent d'une correspondance contrôlée ; une cause inconnue reste explicitement inconnue, sans recopier une réponse externe ni présenter une hypothèse comme un diagnostic établi. Le signalement respecte les droits d'accès, ne transforme pas un échec en succès et ne supprime pas de données valides du seul fait de l'erreur.

Chaque erreur signalée reçoit une référence d'incident opaque, distincte des identifiants d'utilisateur, de session et des secrets. Lorsque la requête atteint le backend, cette référence relie le message visible aux diagnostics des couches concernées. Ces diagnostics conservent uniquement l'opération, l'étape, le type d'erreur, le statut HTTP et le code reconnus lorsqu'ils sont disponibles ; les valeurs inconnues sont indiquées comme telles. Une panne purement locale au navigateur dispose d'un signalement local sans promettre de trace backend. Les messages et journaux excluent les secrets, les messages bruts des services externes, les corps HTTP et les contenus de conversation ou d'outils ; leur enrichissement ne doit pas désactiver les protections des transports.

### Modèles interchangeables

Prendre en charge dès la première version OpenAI, Claude (Anthropic), Gemini (Google) et Ollama, avec une interface de fournisseur pour les modèles distants avec clé et les modèles locaux compatibles. Pour chaque gamme de chaque fournisseur, viser la dernière génération et la précédente lorsqu'elle existe. La documentation distingue les modèles dont la compatibilité est vérifiée, les incompatibilités connues et les modèles non encore vérifiés, y compris pour Ollama. La réutilisation des intégrations HA existantes ou la création d'adaptateurs dédiés reste à étudier. Le choix des adaptateurs et la prise en charge effective des appels d'outils, du français et d'un affichage progressif doivent être vérifiés par fournisseur et modèle ; tous les modèles individuels ne sont pas nécessairement compatibles. Une solution figée sur un fournisseur serait contraire au besoin.

### Versions minimales

La première version cible Home Assistant 2026.10 ou ultérieur et Versatile Thermostat 10.6.3 ou ultérieur. La version 10.6.3 de VTherm inclut les outils LLM/MCP natifs. La compatibilité effective et la couverture des outils restent à vérifier sur la matrice des versions prises en charge.

### Orchestration agentique

Google ADK est retenu pour l'orchestration, sans prototype ni preuve de concept comparatifs. L'implémentation doit vérifier les quatre fournisseurs, les appels d'outils et l'affichage progressif selon les modèles, ainsi que la connexion et l'authentification auprès du MCP officiel de Home Assistant. Les dépendances, le déploiement dans l'app, la conservation de la dernière conversation et l'application effective des contrôles de lecture seule doivent également être vérifiés. La sécurité et la confidentialité restent sous la responsabilité de l'application.

### Déploiement selon l'installation HA

L'app et ingress constituent le parcours retenu pour Home Assistant OS. Home Assistant Container ne dispose pas du système d'apps ni d'ingress : un déploiement autonome réutilisant le traitement et l'interface est à étudier, avec l'authentification OAuth HA de chaque utilisateur et, si souhaité, une intégration distincte pour la barre latérale. Cette présence dans HA n'est pas automatique sous Container. Aucun accès entrant à HA depuis un fournisseur externe n'est requis : les appels vers les modèles distants sont initiés par le traitement local.

## Risks / Trade-offs

- [Droits insuffisants ou API native indisponible] → Détecter la limite, ne pas la contourner et restituer un diagnostic partiel.
- [Historique absent, tronqué ou attributs non conservés] → Préciser la période et les données manquantes ; ne pas inventer l'évolution passée.
- [Accès trop large ou injection dans des données externes] → Appliquer une liste d'opérations en lecture seule côté serveur, vérifier les permissions et traiter les contenus externes comme des données.
- [Identité ingress absente ou statut administrateur invérifiable] → Refuser l'accès aux données privées et les requêtes ; tester la vérification et l'isolation par utilisateur sur les versions prises en charge.
- [Jeton MCP administrateur partagé] → Réserver l'app aux administrateurs vérifiés, protéger le jeton et appliquer les restrictions de lecture seule côté serveur sans supposer une délégation des droits individuels.
- [Couverture insuffisante du MCP officiel] → Vérifier les outils disponibles, faire évoluer ceux de VTherm lorsque c'est possible et signaler les données qui restent inaccessibles.
- [Absence d'apps et d'ingress sous Container] → Vérifier le parcours OAuth distinct et sa sécurité sans promettre une entrée automatique dans la barre latérale.
- [Données envoyées à un modèle externe] → Informer l'utilisateur et limiter le contexte transmis ; ne pas promettre la politique de conservation du fournisseur.
- [Latence ou coûts du modèle] → Mesurer la latence et limiter le contexte ; étudier l'affichage progressif et l'état d'attente sans promettre un temps de réponse donné.
- [Variabilité des plugins et modèles] → Tester une matrice explicite de versions et signaler les éléments non pris en charge.

## Migration Plan

Projet neuf : aucune migration de données n'est prévue. L'installation devra prévoir le retrait de l'app et de ses éventuels composants associés sans modifier les configurations VTherm existantes ; les secrets et la conversation sauvegardée propres à l'assistant devront pouvoir être supprimés.

## Open Questions

- Comment valider les mécanismes d'identité et de vérification des droits sous HA OS et Container sur les versions prises en charge, notamment les redirections OAuth, la révocation et l'isolation des sessions ?
- Quels modèles et versions de chaque gamme des quatre fournisseurs sont compatibles avec l'assistant, et quelles incompatibilités doivent être documentées ?
- Quels outils du MCP officiel exposent effectivement les règles des plugins ciblés et l'historique utile, et quelles évolutions VTherm sont nécessaires ?
- Quelles limites de contexte conviennent pour exploiter l'historique disponible ?