# Proposal

## Why

Les utilisateurs de Versatile Thermostat ont besoin de comprendre leur configuration et les raisons d'un comportement en tenant compte de leur installation réelle. Les réponses génériques ne suffisent pas à relier l'état actuel du thermostat et ses dépendances pertinentes.

## What Changes

- Proposer une app Home Assistant avec une interface de conversation spécialisée VTherm intégrée à l'IHM de l'app, accessible depuis la barre latérale lorsqu'elle y est affichée, sans carte de tableau de bord ni interface Assist.
- Réserver l'accès à l'assistant, en première version, aux administrateurs Home Assistant dont l'identité et les droits sont vérifiés ; refuser les requêtes lorsque cette vérification est impossible.
- Fournir une page de configuration distincte de la conversation pour choisir le fournisseur et saisir ses paramètres, notamment la clé API et l'URL lorsqu'elles sont nécessaires.
- Proposer les modèles du fournisseur sélectionné via un catalogue dynamique récupéré par le backend, avec suggestions prédéfinies en secours et saisie manuelle, en distinguant disponibilité et compatibilité vérifiée.
- Afficher la date et l'heure de chaque question et réponse avant son auteur, en petits caractères, dans la langue et le fuseau du navigateur de l'utilisateur ; conserver les instants après reprise.
- Afficher au début de chaque nouvelle conversation le nombre et la liste des VTherm interrogeables, obtenus par une lecture MCP autorisée sans génération par le modèle ni modification de l'exposition, sans duplication lors d'une restauration.
- Répondre aux questions sur la configuration, les réglages et l'utilisation, et expliquer les diagnostics à partir des états actuels accessibles, y compris les entités associées et les plugins ou cartes pertinents.
- Conserver localement la dernière conversation et son contexte pour chaque utilisateur, y compris après un redémarrage de l'app ; permettre de reprendre sa discussion après navigation dans Home Assistant et de l'effacer en démarrant une nouvelle conversation.
- Permettre de demander des précisions et présenter les limites des données et des conclusions.
- Prendre en charge dès la première version OpenAI, Claude (Anthropic), Gemini (Google) et Ollama, avec la clé personnelle de l'utilisateur pour les fournisseurs distants et un modèle local compatible pour Ollama.
- Donner des conseils étayés par les informations accessibles, sans modifier l'installation ni déclencher de surveillance autonome.
- Utiliser exclusivement le serveur MCP officiel de Home Assistant pour les échanges MCP avec HA et les outils natifs VTherm ; faire évoluer les outils MCP/LLM de VTherm si nécessaire pour couvrir les besoins de diagnostic, tout en garantissant effectivement la lecture seule de l'assistant.

La consultation des issues, discussions et releases GitHub, ainsi que les changements de configuration et la surveillance autonome, sont des pistes futures, hors du périmètre initial.

Le 2026-11-08, l'utilisateur retire du périmètre courant l'accès à l'historique Home Assistant et la recherche documentaire pour les diagnostics ; ces deux volets seront repris dans le change suivant. Les notices d'installation, de sécurité et de configuration restent dans le périmètre. Ce report ne retire pas les horodatages ni la conservation de la dernière conversation et ne supprime pas les composants déjà présents dans le code.

## Capabilities

### New Capabilities

- `vtherm-conversation`: dernière conversation de chaque utilisateur autorisé conservée dans l'interface de l'app Home Assistant et réponses adaptées à son contexte.
- `vtherm-diagnosis`: diagnostic et conseils fondés sur les états actuels accessibles de VTherm et de ses dépendances.
- `model-configuration`: choix et configuration sécurisée d'un modèle compatible distant ou local.

### Modified Capabilities

Aucune.

## Impact

- Nouveau projet : le dépôt ne contient pas encore d'implémentation ni de spécification existante.
- Home Assistant, son serveur MCP officiel, Versatile Thermostat, ses dépendances et leurs sources de données en lecture seule ; disponibilité des outils natifs et compatibilité à vérifier selon les versions.
- App Home Assistant avec interface de discussion intégrée et accès possible par la barre latérale sous Home Assistant OS ; un parcours distinct reste à définir pour Home Assistant Container, qui ne dispose pas du système d'apps.
- Fournisseurs de modèles choisis par l'utilisateur ; des informations de l'installation peuvent être transmises à un fournisseur distant.