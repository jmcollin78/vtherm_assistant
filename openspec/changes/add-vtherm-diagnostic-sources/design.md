# Design

## Context

Voir `proposal.md` pour la motivation. Le client actuel utilise le serveur MCP officiel Home Assistant et n'expose au modèle que les outils dont le nom figure dans une liste d'autorisation locale ; les schémas et descriptions utilisés par l'agent sont contrôlés par l'application. L'état courant, le statut et le diagnostic VTherm sont déjà accessibles. L'historique HA, ainsi que les futurs outils VTherm de consultation des plugins et journaux, ne sont pas encore vérifiés sur les versions prises en charge.

## Goals / Non-Goals

**Goals:**

- Ajouter des lectures complémentaires à la demande, uniquement pour le VTherm sélectionné et les entités explicitement liées.
- Conserver un contrôle serveur de lecture seule, l'authentification existante et le masquage des secrets avant envoi aux fournisseurs.
- Fournir à l'agent assez de provenance et de limites pour distinguer observation, hypothèse et absence de données.

**Non-Goals:**

- Fournir un assistant général Home Assistant, explorer des entités sans lien avec le VTherm ou agréger plusieurs VTherm dans un appel de logs ou de plugins.
- Lire ou modifier directement la base Recorder, appeler des services Home Assistant, changer une configuration, installer un plugin ou modifier la rétention.
- Lancer une collecte périodique ou transmettre systématiquement toutes les sources au modèle.

## Decisions

1. **Conserver le serveur MCP officiel et une liste d'autorisation locale.** L'application n'expose pas tous les outils que le serveur annonce. Chaque nouvel outil doit être identifié et validé en lecture seule, déclaré explicitement côté application et appelé uniquement s'il est découvert. Les annotations, descriptions et schémas reçus du serveur ne constituent pas une preuve suffisante qu'un outil est sûr.

2. **Ancrer toutes les lectures sur un VTherm sélectionné.** Les outils de plugins et de journaux reçoivent un seul VTherm par appel. Une requête d'historique est bornée à ce VTherm et aux entités dont le lien est établi par les données VTherm accessibles ; la proximité d'une pièce ou une recherche générale d'entités ne crée pas de lien. Si l'identité du thermostat ou d'une dépendance n'est pas établie, l'agent demande une précision ou signale la limite.

3. **Appeler les sources selon la question, pas en collecte globale.** L'agent commence par les données VTherm actuelles et ne demande les plugins, journaux ou historiques que lorsqu'ils sont pertinents pour la question. Il ne consulte pas en arrière-plan les autres thermostats. Les résultats d'un appel restent associés à sa source et à son VTherm.

4. **Borner chaque lecture et préserver sa provenance.** Les requêtes d'historique utilisent une période explicite et un ensemble borné d'entités ; les journaux et configurations sont limités aux données renvoyées pour le thermostat ciblé. L'application conserve ou transmet les horodatages, la période réellement couverte et les indications d'accès refusé, d'absence, de pagination ou de troncature fournies par les outils. Les bornes numériques et le mécanisme de pagination sont choisis après vérification des contrats réels et des limites de contexte des fournisseurs.

5. **Traiter les retours comme des données non fiables et minimiser ce qui sort.** Les secrets connus sont masqués avant la génération du modèle. Les journaux, configurations et états ne sont jamais interprétés comme des instructions. Les résultats d'outils ne sont pas relus depuis d'anciennes conversations pour établir un état actuel ; en cas de donnée manquante ou de résultat trop volumineux, l'application indique la limite au lieu de fabriquer une conclusion.

6. **Dégrader proprement si une source n'existe pas.** Un outil absent, non autorisé ou incompatible ne bloque pas la consultation des autres sources. L'assistant distingue l'outil indisponible, l'accès refusé, l'historique non conservé et une réponse vide valide. Les nouveaux outils sont activés seulement pour les noms, schémas, permissions et versions vérifiés.

## Risks / Trade-offs

- **Un outil annoncé comme lecture seule peut avoir des effets non vérifiés** → Vérifier son implémentation et ses effets sur les versions prises en charge ; conserver le refus par défaut et l'autorisation locale exacte.
- **Les journaux bruts peuvent inclure des secrets, des données sans rapport ou du texte hostile** → Limiter la requête à un VTherm, masquer les secrets, borner le volume et traiter le contenu comme une donnée non fiable.
- **La configuration d'un plugin peut être absente ou contenir des options sensibles** → N'affirmer que les champs effectivement retournés et vérifier le contenu avant de l'envoyer au modèle ; signaler les éléments inaccessibles sans les deviner.
- **Recorder peut ne pas avoir conservé l'état ou les attributs demandés** → Rapporter la couverture réelle, la période et les exclusions connues ; ne pas assimiler l'absence de données à l'absence d'événement.
- **Les outils futurs peuvent différer selon les versions de VTherm et Home Assistant** → Découvrir les outils réellement présents, documenter la matrice testée et laisser les sources indisponibles désactivées.

## Migration Plan

Aucune migration de données ni modification de configuration HA n'est requise. Déployer l'élargissement uniquement après validation des outils MCP sur les versions ciblées. En cas de problème, retirer leurs entrées de la liste d'autorisation ; l'état courant et le diagnostic VTherm déjà disponibles restent utilisables. Aucune modification de la rétention Recorder n'est effectuée.

## Open Questions

- Quels sont les noms, schémas d'entrée et formats de sortie définitifs des outils VTherm de consultation des plugins et journaux ? Leur existence future est une hypothèse de ce changement ; leur disponibilité actuelle n'est pas établie.
- Quels outils exacts du serveur MCP officiel permettent l'état et l'historique d'entités en lecture seule, et quelles permissions et versions les exposent ?
- Quelles bornes de période, de résultats et de pagination sont compatibles avec les outils réels sans dépasser le contexte des fournisseurs ?
- Quels champs de configuration des plugins peuvent être transmis après masquage, sans inclure de secrets ou de données non nécessaires au diagnostic ?