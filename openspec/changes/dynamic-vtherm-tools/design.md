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

1. **Découvrir dynamiquement par intégration, pas par nom d'outil.** À chaque construction ou actualisation de l'agent, le backend découvre les outils annoncés par le serveur MCP officiel et détermine ceux qui appartiennent à VTherm par l'identifiant d'intégration ou son espace de noms documenté. Il transmet à l'agent les noms, descriptions et schémas des outils de cette intégration, sans maintenir une liste de noms d'outils VTherm dans le code. L'identification du propriétaire doit être vérifiée pour les versions ciblées ; un outil dont l'origine ne peut pas être établie n'est pas assimilé à un outil VTherm.

2. **Conserver une sélection fixe et restrictive hors VTherm.** Les outils MCP standard Home Assistant sont séparés du catalogue dynamique VTherm. Seuls les outils de consultation explicitement retenus, par exemple pour les états et l'historique, sont transmis à l'agent. Leurs requêtes restent liées au VTherm sélectionné et à ses dépendances établies ; aucune découverte générale ou opération d'écriture Home Assistant n'est exposée.

3. **Refuser par défaut toute écriture sans consentement lié à l'appel.** Avant chaque exécution, un contrôle backend classe l'outil et ses effets. Une indication d'annotation ou de description MCP ne suffit pas à prouver qu'un outil est sans effet de bord ; si la lecture seule n'est pas établie, l'outil est traité comme potentiellement modifiant. Pour une écriture, le système présente à l'utilisateur le VTherm ciblé, l'opération et les paramètres exacts, puis suspend l'appel. Une confirmation distincte est liée à l'utilisateur, à la conversation, à l'appel en attente et à ses paramètres canoniques ; elle est consommée une seule fois. Un refus, un délai dépassé, un changement de cible ou de paramètre, ou une confirmation ambiguë annule l'appel et exige une nouvelle confirmation.

4. **Valider les descriptions et schémas avant de les proposer au modèle.** Les métadonnées publiées par le serveur sont des données non fiables, pas des instructions. Les schémas sont vérifiés et adaptés aux contraintes des fournisseurs sans changer la sémantique des paramètres. Les secrets connus sont masqués dans les arguments, résultats, confirmations et journaux. Si un schéma ne peut pas être représenté ou validé, le système signale l'indisponibilité plutôt que d'inventer une déclaration ou d'appeler l'outil avec des arguments non vérifiés.

5. **Actualiser la découverte et isoler les appels.** Les outils sont redécouverts lors de la création/actualisation d'une session d'agent et après reconnexion MCP ; le système ne conserve pas un catalogue global partagé entre utilisateurs. Chaque appel est vérifié à nouveau contre la liste découverte pour la session et les droits en vigueur. Les outils de logs et de plugins reçoivent un seul VTherm cible par appel, conformément à leur contrat.

6. **Ne pas bloquer toute la conversation pour un outil incompatible.** Un outil absent, invalide ou incompatible avec un fournisseur reste indisponible pour cette session et sa raison est rapportée sans contenu brut ni secret. Les autres outils validés continuent de fonctionner.

## Risks / Trade-offs

- **Un nom ou une annotation ne permet pas toujours d'identifier le propriétaire ou les effets d'un outil** → Vérifier l'espace de noms/les métadonnées publiés et les implémentations sur les versions supportées ; refuser les outils d'origine incertaine et traiter les effets incertains comme des écritures.
- **Un fournisseur peut ne pas accepter un schéma dynamique donné** → Tester les adaptateurs et les modèles ; ne pas exposer un outil dont les arguments ne peuvent pas être représentés fidèlement.
- **Une confirmation pourrait être réutilisée pour un appel différent** → Lier le consentement à l'utilisateur, à l'appel et aux arguments exacts, avec usage unique et expiration ; refaire la demande au moindre changement.
- **Une écriture peut réussir sans pouvoir être annulée** → Afficher la portée exacte avant confirmation et rapporter le résultat observé sans promettre de rollback.
- **La découverte dynamique ouvre un ensemble d'actions plus large côté VTherm** → Ne jamais exposer implicitement les outils Home Assistant génériques ; vérifier les droits effectifs, auditer les écritures confirmées sans journaliser secrets ni contenus sensibles, et tester les refus côté backend.
- **Le contexte OpenSpec du dépôt affirme encore que l'assistant ne modifie pas l'installation et que les outils disponibles sont limités à la lecture** → Cette contradiction n'est pas résolue par ce changement, car la modification d'`openspec/config.yaml` n'est pas incluse dans le périmètre autorisé ; elle doit être réglée avant l'implémentation.

## Migration Plan

Aucune migration de données n'est attendue. La découverte dynamique et les appels d'écriture doivent être activés seulement après validation du propriétaire des outils, des schémas, de la classification des effets et du contrôle de consentement de bout en bout. Le repli consiste à désactiver les nouveaux appels, en conservant la conversation et les outils de lecture déjà validés. La politique de contexte du dépôt doit être réconciliée séparément avant l'application du changement.

## Open Questions

- Quel identifiant ou espace de noms stable permet de distinguer tous les outils publiés par l'intégration VTherm des outils Assist ou d'autres intégrations sur les versions supportées ?
- Quelles métadonnées fiables, au-delà d'une simple description, permettent de classifier les effets en lecture seule ou en écriture ? Par défaut, les effets incertains exigent une confirmation.
- Quels fournisseurs et modèles acceptent fidèlement les schémas dynamiques publiés par les versions VTherm ciblées ?
- Le catalogue d'outils doit-il être rafraîchi à chaque tour ou seulement lors de l'ouverture/reconnexion d'une session d'agent ? Le choix précis peut être fixé après mesure, sans changer l'exigence de découverte dynamique.