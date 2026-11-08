# Design

## Context

Voir `proposal.md` pour la motivation. Le client MCP actuel découvre les outils annoncés, mais n'expose à l'agent qu'une liste locale de noms VTherm et de schémas codés dans l'application. La spécification de conversation interdit actuellement toute écriture ; cette évolution la remplace par un consentement obligatoire et vérifié avant chaque écriture VTherm.

## Goals / Non-Goals

**Goals:**

- Découvrir les outils publiés par l'intégration VTherm à l'exécution, sans inventaire local de noms, et les rendre disponibles aux fournisseurs compatibles.
- Garantir par un contrôle hors modèle qu'aucune écriture VTherm ne s'exécute sans consentement explicite lié à l'appel exact.
- Garder séparés les outils VTherm et l'ensemble limité des outils de consultation Home Assistant standards.
- Traiter les paramètres et résultats de sources MCP comme des données non fiables et protéger les secrets.

**Non-Goals:**

- Exposer tous les outils Home Assistant, les services génériques ou des outils d'écriture Home Assistant hors VTherm.
- Modifier les outils MCP du serveur, les droits Home Assistant, les règles de consentement ou les capacités publiées par VTherm.
- Garantir qu'un outil découvert est compatible avec tous les fournisseurs ou versions avant vérification.

## Decisions
**Faits vérifiés et compromis provisoire (HA Core 2026.10.4 / VTherm 10.6.4).** VTherm renseigne `Tool.integration = DOMAIN` et nomme ses outils avec le domaine `versatile_thermostat`; HA ajoute `slug(api.name)__` quand plusieurs APIs sont fusionnées, ce qui explique des formes comme `assist__versatile_thermostat__...`. Toutefois, le serveur MCP HA ne sérialise dans `tools/list` que le nom, le titre, la description, le schéma et les annotations, pas le champ `integration`. Le serveur expose les outils de l'API MCP sélectionnée; le client suit les curseurs `nextCursor` et refuse les curseurs répétitifs. Les sources vérifiées sont [HA LLM helpers](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/helpers/llm.py), [HA MCP server](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/mcp_server/server.py) et [VTherm LLM tools](https://github.com/jmcollin78/versatile_thermostat/tree/10.6.4/custom_components/versatile_thermostat/llm). À la demande de l'utilisateur, l'implémentation ne bloque pas sur la transmission future de cette provenance : les namespaces documentés `versatile_thermostat__` et `assist__versatile_thermostat__` sont un filtre provisoire, pas une preuve d'origine vérifiée. Une autre API pourrait publier le même préfixe. Cette limite doit rester visible jusqu'à ce que HA transmette une métadonnée de propriétaire fiable.


1. **Découvrir dynamiquement par namespace provisoire, pas par liste de noms d'outils.** À chaque construction ou actualisation de l'agent, le backend découvre les outils annoncés par le serveur MCP officiel et retient les noms commençant par `versatile_thermostat__` ou `assist__versatile_thermostat__`. Cette règle est une identification provisoire convenue avec l'utilisateur, et non une preuve d'origine. Le backend transmet les noms, descriptions et schémas découverts sans maintenir une liste exhaustive de noms d'outils VTherm. Les outils de ces namespaces restent soumis aux contrôles de schéma, d'effets et de consentement ; aucun préfixe ne doit être qualifié d'identité vérifiée dans l'interface ou les journaux.

2. **Conserver une sélection fixe et restrictive hors VTherm.** Le seul outil MCP standard Home Assistant retenu est `homeassistant__GetLiveContext`, séparé du catalogue VTherm. Une requête avec `name` doit fournir l'entity_id exact d'une entité liée, établie par le dernier état/diagnostic VTherm; `area` et `domain` ne servent pas à cibler une entité. L'appel sans argument reste global et ne peut pas être présenté comme une lecture ciblée. Les lectures d'historique sont des outils VTherm distincts. Aucune découverte générale d'outils HA ni opération d'écriture Home Assistant n'est exposée.

**Permissions et données de consultation.** Le client MCP utilise le jeton administrateur HA enregistré pour l'utilisateur et vérifie son statut avant chaque session; il n'utilise pas une identité HA non-admin déléguée. Les restrictions d'entité ciblée sont donc des contrôles backend de l'application, pas une preuve d'isolation par permissions HA. `GetLiveContext` peut lire un contexte global sans filtre; cette réponse reste explicitement globale et ne doit pas étayer une conclusion ciblée. `versatile_thermostat__get_history` est borné aux climates VTherm de l'inventaire, à une période zonée explicite de 14 jours maximum et à 500 états par page. Recorder retourne des changements/états conservés, pas des échantillons réguliers; rétention, exclusions et trous empêchent de conclure à l'absence d'événement. Les codes `recorder_unavailable` et `read_permission_denied` restent des erreurs explicites. Le contrôle VTherm de `POLICY_READ` est présent dans l'intégration 10.6.4, mais son contexte utilisateur effectif via MCP n'a pas été vérifié en direct.

3. **Refuser par défaut toute écriture sans consentement lié à l'appel.** Avant chaque exécution, un contrôle backend classe l'outil et ses effets. Une indication d'annotation ou de description MCP ne suffit pas à prouver qu'un outil est sans effet de bord ; si la lecture seule n'est pas établie, l'outil est traité comme potentiellement modifiant. Pour une écriture, le système présente à l'utilisateur le VTherm ciblé, l'opération et les paramètres exacts, puis suspend l'appel. Une confirmation distincte est liée à l'utilisateur, à la conversation, à l'appel en attente et à ses paramètres canoniques ; elle est consommée une seule fois. Un refus, un délai dépassé, un changement de cible ou de paramètre, ou une confirmation ambiguë annule l'appel et exige une nouvelle confirmation.

4. **Valider les descriptions et schémas avant de les proposer au modèle.** Les métadonnées publiées par le serveur sont des données non fiables, pas des instructions. Les schémas sont vérifiés et adaptés aux contraintes des fournisseurs sans changer la sémantique des paramètres. Les secrets connus sont masqués dans les arguments, résultats, confirmations et journaux. Si un schéma ne peut pas être représenté ou validé, le système signale l'indisponibilité plutôt que d'inventer une déclaration ou d'appeler l'outil avec des arguments non vérifiés.

**Compatibilité locale des schémas (sans appel fournisseur).** Gemini reçoit `types.FunctionDeclaration` directement; OpenAI, Anthropic et Ollama passent dans cette application par l'adaptateur LiteLLM commun, qui sérialise la même déclaration en schéma de fonction. Le backend accepte un sous-ensemble JSON Schema commun (objets, chaînes, nombres, booléens, tableaux, énumérations et contraintes usuelles), retire de la déclaration modèle `additionalProperties`, `title` et `default` quand ces annotations/contraintes sont gérées côté backend, et refuse notamment `$ref`, unions et mots-clés hors sous-ensemble. Les tests vérifient les deux chemins d'adaptateur, l'ajout/retrait, le rejet des schémas non représentables et le blocage des arguments invalides avant `tools/call`. Cela vérifie la sérialisation ADK locale; l'acceptation par des modèles distants reste à tester en 5.3.

5. **Actualiser la découverte et isoler les appels.** Les outils sont redécouverts lors de la création/actualisation d'une session d'agent et après reconnexion MCP ; le système ne conserve pas un catalogue global partagé entre utilisateurs. Chaque appel est vérifié à nouveau contre la liste découverte pour la session et les droits en vigueur. Les outils de logs et de plugins reçoivent un seul VTherm cible par appel, conformément à leur contrat.

6. **Ne pas bloquer toute la conversation pour un outil incompatible.** Un outil absent, invalide ou incompatible avec un fournisseur reste indisponible pour cette session et sa raison est rapportée sans contenu brut ni secret. Les autres outils validés continuent de fonctionner.

## Risks / Trade-offs

- **Le namespace peut être usurpé tant que HA n'expose pas l'intégration propriétaire** → Compromis provisoire explicite : filtrer par les deux namespaces VTherm documentés, ne jamais prétendre que l'origine est vérifiée, exiger le consentement exact pour toute écriture et réévaluer ce filtre dès que HA transmet l'identité d'intégration.
- **Un fournisseur peut ne pas accepter un schéma dynamique donné** → Tester les adaptateurs et les modèles ; ne pas exposer un outil dont les arguments ne peuvent pas être représentés fidèlement.
- **Une confirmation pourrait être réutilisée pour un appel différent** → Lier le consentement à l'utilisateur, à l'appel et aux arguments exacts, avec usage unique et expiration ; refaire la demande au moindre changement.
- **Une écriture peut réussir sans pouvoir être annulée** → Afficher la portée exacte avant confirmation et rapporter le résultat observé sans promettre de rollback.
- **La découverte dynamique ouvre un ensemble d'actions plus large côté VTherm** → Ne jamais exposer implicitement les outils Home Assistant génériques ; vérifier les droits effectifs, auditer les écritures confirmées sans journaliser secrets ni contenus sensibles, et tester les refus côté backend.
- **Le contexte global pourrait autoriser des écritures au-delà de VTherm** → `openspec/config.yaml` limite provisoirement les candidats d'écriture aux namespaces VTherm documentés et exige le consentement explicite lié à l'action et à ses paramètres exacts ; les outils Home Assistant hors de ces namespaces restent en consultation uniquement.

## Migration Plan

Aucune migration de données n'est attendue. La découverte dynamique peut avancer avec le filtre provisoire par namespace décidé par l'utilisateur, en documentant qu'il ne vérifie pas le propriétaire MCP. Les schémas, la classification des effets et le contrôle de consentement doivent néanmoins être validés avant d'activer les appels d'écriture. Le mécanisme de provenance fiable de HA reste un suivi à transmettre à VTherm/HA; lorsqu'il sera disponible, il devra remplacer le filtre provisoire. Le repli consiste à désactiver les nouveaux appels, en conservant la conversation et les outils de lecture déjà validés.

## Open Questions

- Quel mécanisme de provenance fiable le serveur MCP officiel exposera-t-il pour remplacer le filtre provisoire par namespace ? HA Core 2026.10.4 omet le champ interne `Tool.integration` de `tools/list`; le préfixe ne vérifie donc pas l'origine.
- Quelles métadonnées fiables, au-delà d'une simple description, permettent de classifier les effets en lecture seule ou en écriture ? Par défaut, les effets incertains exigent une confirmation.
- Quels fournisseurs et modèles acceptent fidèlement les schémas dynamiques publiés par les versions VTherm ciblées ?
- Le catalogue d'outils doit-il être rafraîchi à chaque tour ou seulement lors de l'ouverture/reconnexion d'une session d'agent ? Le choix précis peut être fixé après mesure, sans changer l'exigence de découverte dynamique.