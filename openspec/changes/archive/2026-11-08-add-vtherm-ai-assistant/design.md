# Design

## Context

Voir la proposition pour le besoin et les limites fonctionnelles. Le dépôt ne contient actuellement que des documents OpenSpec et un README minimal : il n'existe ni backend, ni carte, ni tests à réutiliser dans ce projet.

La [PR VTherm #2160](https://github.com/jmcollin78/versatile_thermostat/pull/2160) fournit des outils natifs de liste, d'état et de diagnostic, mais aussi des outils de commande. Ils passent par l'API LLM de Home Assistant, utilisent les VTherm exposés à Assist et ne garantissent pas à eux seuls que l'ensemble de l'assistant soit en lecture seule. Les capacités et conditions d'accès effectives devront être vérifiées sur les versions prises en charge. L'historique Home Assistant et la recherche documentaire sont retirés du périmètre courant le 2026-11-08 et reportés au change suivant.

## Goals / Non-Goals

**Goals:**

- Séparer l'interface de l'app, le traitement, l'accès MCP aux données et les fournisseurs de modèle pour faciliter leur évolution.
- Garantir lecture seule, confidentialité des identifiants et signalement des données indisponibles.
- Permettre l'utilisation sous Home Assistant OS et Container, sans supposer que le système d'apps HA existe sous Container.

**Non-Goals:**

- Remplacer Assist, contrôler les thermostats ou conserver un historique des conversations précédentes.
- Garantir l'accès à la configuration privée de tout plugin tiers.
- Intégrer ou valider dans ce lot l'historique Home Assistant et la recherche documentaire pour les diagnostics ; ne pas reconstruire le passé à partir des seuls états actuels.
- Fournir une carte de tableau de bord ou intégrer un serveur MCP tiers tel que ha-mcp.
- Choisir dès ce design les bibliothèques de modèles ou le mécanisme d'intégration propre à Home Assistant Container.

## Decisions

### App et interface intégrée

Une app Home Assistant héberge l'interface web et le traitement. Elle comporte une page de conversation et une page distincte de configuration du fournisseur et de ses paramètres. La dernière conversation de chaque utilisateur est restaurée à son retour dans l'app, y compris après un redémarrage ; un bouton permet d'effacer sa conversation et d'en commencer une nouvelle. Sous Home Assistant OS, l'accès passe par ingress et l'app peut être affichée dans la barre latérale, sans ajouter de carte aux tableaux de bord. L'interface permet de saisir les clés des fournisseurs mais ne les conserve pas ; le traitement les protège, contrôle l'accès aux sources, gère la conversation et dialogue avec le modèle. Cette solution évite la distribution et la configuration d'une carte, mais nécessite toujours une interface web et son backend.

En première version, l'app réserve les conversations, la configuration et les requêtes aux administrateurs HA dont l'identité et les droits sont vérifiés. Sous HA OS, ingress peut transmettre l'identifiant via `X-Remote-User-Id` ; l'app n'accepte les connexions ingress que du Supervisor afin de ne pas faire confiance à des en-têtes forgés. Le statut administrateur doit être vérifié à partir d'une source HA fiable ; l'identifiant seul ne le démontre pas. Une piste consiste à consulter la liste des utilisateurs HA par WebSocket avec un accès administrateur protégé et à vérifier le compte correspondant, son activité et ses droits. Sous Container, chaque utilisateur se connecte à son compte HA par OAuth avec PKCE ; son identité et son statut administrateur sont vérifiés auprès de HA, notamment par `auth/current_user`. Les jetons et la session sont protégés et les accès sont refusés lorsque la session ou les droits ne sont plus valides. Si l'identité ou les droits ne peuvent pas être vérifiés, aucune conversation sauvegardée n'est exposée et aucune requête n'est exécutée. Une interface vierge peut être affichée sans accès aux données privées. Vérifier ces mécanismes, notamment les redirections OAuth, la révocation, l'isolation des sessions et le refus des en-têtes forgés, sur les versions HA prises en charge.

### Accès aux données et preuves

Le traitement est client du seul serveur MCP officiel de Home Assistant ; ha-mcp n'est pas retenu. Il s'authentifie auprès du MCP avec un jeton administrateur HA protégé par l'app, indépendamment de l'identité ingress : ce jeton ne délègue pas automatiquement les droits de l'utilisateur connecté. L'accès à l'app reste donc réservé aux administrateurs vérifiés et les outils utilisables restent limités à la lecture. Vérifier le mécanisme de connexion MCP et la compatibilité des versions retenues. Le traitement utilise les outils VTherm natifs disponibles et les autres outils de lecture exposés par ce serveur pour les états actuels des dépendances, selon les versions et autorisations. Si cette couverture est insuffisante, faire évoluer les outils MCP/LLM de VTherm et les exposer par le serveur officiel, plutôt qu'ajouter un second serveur MCP. Vérifier la faisabilité de chaque évolution ; une donnée inaccessible reste signalée comme telle.

Présenter les données actuelles avec leur source et leurs instants connus ; ne pas en déduire un historique non consulté. La configuration d'un plugin tiers n'est utilisable que si une interface autorisée la rend accessible. Une réponse partielle doit expliquer ses limites plutôt que déduire une règle cachée.

L'intégration et la validation de l'outil d'historique, de sa pagination et des données Recorder sont reportées au change suivant, sans modification de Recorder. La recherche documentaire automatique, ses locales, ses sources et ses scénarios d'erreur seront également finalisés dans ce prochain périmètre. Cette révision des artefacts ne supprime pas le contrat d'historique déjà rédigé ni l'outil documentaire déjà présent dans le code, et n'en certifie pas le fonctionnement. Les contenus externes restent des données non fiables, jamais des instructions prioritaires.

### Isolation en lecture seule

Le traitement ne met à disposition du modèle que des opérations de lecture explicitement autorisées et refuse les autres appels côté serveur. Les services génériques de commande et les outils VTherm d'écriture ne font pas partie de cette liste, même s'ils sont disponibles dans HA. Les droits de l'utilisateur HA et l'exposition des entités doivent être vérifiés ; le simple prompt ou les annotations des outils ne constituent pas une barrière suffisante. Toute interface de diagnostic doit aussi être contrôlée pour ses effets de bord.

### Conversation sauvegardée et confidentialité

La dernière conversation et son contexte sont conservés localement dans un stockage protégé pour chaque utilisateur identifié, afin de les reprendre après navigation ou redémarrage de l'app. L'accès est réservé à son propriétaire autorisé ; le backend détermine celui-ci à partir de l'identité vérifiée, et non d'un identifiant fourni librement par le client. Le bouton de nouvelle conversation supprime uniquement les messages et le contexte de cet utilisateur du stockage de l'app ; aucun historique des conversations précédentes n'est conservé par l'assistant. Les données Recorder restent indépendantes de cette mémoire. Les identifiants sont configurés et conservés dans le composant de confiance, avec contrôle d'accès et masquage dans les sorties et journaux. Le fournisseur distant peut appliquer sa propre politique de conservation : l'utilisateur en est informé et la suppression locale ne garantit pas celle des données chez ce fournisseur. Limiter les données transmises au strict nécessaire.

### Horodatage et inventaire de début de conversation

Conserver les instants des messages en UTC dans les données protégées de la conversation : envoi de la question et premier fragment affichable de la réponse. Transmettre ces instants avec les messages restaurés et les événements progressifs ; ne pas utiliser la date de rechargement ou de fin pour remplacer celle du début de réponse. Le navigateur utilise `Intl.DateTimeFormat` avec sa langue et son fuseau pour placer la date et l'heure en petits caractères avant « Vous » ou « Assistant ». L'instant reste stable pendant le streaming ; sa présentation suit les changements d'heure et les paramètres actuels du navigateur. Une migration doit préserver les messages existants sans inventer de dates lorsque leur instant est inconnu.

À la première conversation vierge et après une nouvelle conversation réussie, le backend appelle directement l'outil MCP VTherm de liste déjà autorisé, avec le jeton personnel de l'utilisateur vérifié. Aucun fournisseur génératif n'est nécessaire : l'inventaire est un affichage déterministe du nombre, des noms et des identifiants `climate` retournés, construit sans HTML externe ni limite arbitraire. L'application respecte l'exposition Assist et ne modifie aucune entité. L'inventaire et son instant d'obtention sont rattachés à cette conversation dans le stockage protégé ; la restauration ne les duplique pas et ne les présente pas comme une garantie d'accessibilité actuelle. Les appels ultérieurs restent soumis aux autorisations effectives.

Afficher le chargement avant la première question et distinguer liste vide, jeton absent, outil manquant et échec de lecture, avec les messages sûrs et actions de relance du contrat d'erreurs. Un échec ne devient pas une liste vide ou inventée. Une relance complète l'inventaire initial de la même conversation sans créer de doublon ni reprendre les données d'une conversation supprimée. Ces données restent isolées par utilisateur et sont effacées avec leur conversation.

### Erreurs intelligibles et traçabilité sécurisée

L'application, et non le modèle, classe les erreurs prises en charge sur tous les parcours : authentification, configuration, réseau, MCP, fournisseur, streaming, chargement, restauration et stockage. Elle transforme les métadonnées vérifiées en messages compréhensibles indiquant l'action en échec, le composant identifié et une correction ou relance pertinente. Les catégories et actions proviennent d'une correspondance contrôlée ; une cause inconnue reste explicitement inconnue, sans recopier une réponse externe ni présenter une hypothèse comme un diagnostic établi. Le signalement respecte les droits d'accès, ne transforme pas un échec en succès et ne supprime pas de données valides du seul fait de l'erreur.

Chaque erreur signalée reçoit une référence d'incident opaque, distincte des identifiants d'utilisateur, de session et des secrets. Lorsque la requête atteint le backend, cette référence relie le message visible aux diagnostics des couches concernées. Ces diagnostics conservent uniquement l'opération, l'étape, le type d'erreur, le statut HTTP et le code reconnus lorsqu'ils sont disponibles ; les valeurs inconnues sont indiquées comme telles. Une panne purement locale au navigateur dispose d'un signalement local sans promettre de trace backend. Les messages et journaux excluent les secrets, les messages bruts des services externes, les corps HTTP et les contenus de conversation ou d'outils ; leur enrichissement ne doit pas désactiver les protections des transports.

### Modèles interchangeables

L'utilisateur confirme le 2026-11-08 avoir testé OpenAI Luna, Terra et Sol et les considérer compatibles avec son assistant. Cette preuve de fonctionnement nominal reste distincte des tests simulés et ne certifie pas les autres modèles ou fournisseurs, ni les futurs outils. Seul l'identifiant `gpt-6-luna` est déjà relevé ; les identifiants exacts de Terra et Sol ne sont pas inventés à partir de leurs noms rapportés.

Prendre en charge dès la première version OpenAI, Claude (Anthropic), Gemini (Google) et Ollama, avec une interface de fournisseur pour les modèles distants avec clé et les modèles locaux compatibles. Pour chaque gamme de chaque fournisseur, viser la dernière génération et la précédente lorsqu'elle existe. La documentation distingue les modèles dont la compatibilité est vérifiée, les incompatibilités connues et les modèles non encore vérifiés, y compris pour Ollama. La réutilisation des intégrations HA existantes ou la création d'adaptateurs dédiés reste à étudier. Le choix des adaptateurs et la prise en charge effective des appels d'outils, du français et d'un affichage progressif doivent être vérifiés par fournisseur et modèle ; tous les modèles individuels ne sont pas nécessairement compatibles. Une solution figée sur un fournisseur serait contraire au besoin.

Le catalogue de modèles est obtenu par un parcours backend authentifié, distinct d'une requête de génération : API officielle OpenAI `GET /v1/models`, Anthropic `GET /v1/models`, Gemini `GET /v1beta/models`, ou Ollama `GET /api/tags` à l'URL configurée. Les clés personnelles enregistrées restent au backend ; aucune conversation ni donnée HA n'est envoyée pour obtenir le catalogue. Les références des contrats sont les documentations [OpenAI](https://developers.openai.com/api/reference/resources/models/methods/list), [Anthropic](https://platform.claude.com/docs/en/api/models-list), [Gemini](https://aistudio.google.com/api-reference/models) et [Ollama](https://docs.ollama.com/api/tags).

Gérer la pagination prévue par chaque API, dédupliquer les identifiants et borner les appels réseau ; une récupération incomplète reste signalée comme telle. Séparer les modèles disponibles selon le fournisseur ou installés sur Ollama de leur statut dans la matrice de compatibilité de l'assistant. Les métadonnées de capacités peuvent exclure les incompatibilités établies, mais une absence de preuve ne devient pas une compatibilité vérifiée. Ne déclencher ni génération de test payante ni installation Ollama pour remplir cette liste.

Le formulaire conserve une saisie manuelle en complément de la sélection. Sans paramètres enregistrés ou en cas d'échec, proposer un catalogue prédéfini maintenu avec la documentation de compatibilité, clairement identifié comme suggestions sans garantie d'accès ou d'installation. Différencier chargement, liste vide et erreur ; protéger les messages d'erreur comme les autres échanges fournisseur. Isoler tout cache par utilisateur, fournisseur et configuration ; invalider les résultats après changement de clé ou d'URL et ignorer les réponses tardives après changement de fournisseur. Un modèle configuré absent du catalogue reste conservé et n'est jamais remplacé automatiquement.

### Versions minimales

La première version cible Home Assistant 2026.10 ou ultérieur et Versatile Thermostat 10.6.3 ou ultérieur. La version 10.6.3 de VTherm inclut les outils LLM/MCP natifs. La compatibilité effective et la couverture des outils restent à vérifier sur la matrice des versions prises en charge.

### Orchestration agentique

Google ADK est retenu pour l'orchestration, sans prototype ni preuve de concept comparatifs. L'implémentation doit vérifier les quatre fournisseurs, les appels d'outils et l'affichage progressif selon les modèles, ainsi que la connexion et l'authentification auprès du MCP officiel de Home Assistant. Les dépendances, le déploiement dans l'app, la conservation de la dernière conversation et l'application effective des contrôles de lecture seule doivent également être vérifiés. La sécurité et la confidentialité restent sous la responsabilité de l'application.

### Déploiement selon l'installation HA

L'app et ingress constituent le parcours retenu pour Home Assistant OS. Home Assistant Container ne dispose pas du système d'apps ni d'ingress : un déploiement autonome réutilisant le traitement et l'interface est à étudier, avec l'authentification OAuth HA de chaque utilisateur et, si souhaité, une intégration distincte pour la barre latérale. Cette présence dans HA n'est pas automatique sous Container. Aucun accès entrant à HA depuis un fournisseur externe n'est requis : les appels vers les modèles distants sont initiés par le traitement local.

## Risks / Trade-offs

- [Droits insuffisants ou API native indisponible] → Détecter la limite, ne pas la contourner et restituer un diagnostic partiel.
- [Question sur le passé sans historique consulté] → Signaler cette limite du périmètre courant ; ne pas inventer l'évolution passée.
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
- Quels outils du MCP officiel exposent effectivement les états actuels et les règles des plugins ciblés, et quelles évolutions VTherm sont nécessaires ?
- Quelles limites de contexte conviennent pour les messages de conversation et les résultats d'outils transmis au modèle ?