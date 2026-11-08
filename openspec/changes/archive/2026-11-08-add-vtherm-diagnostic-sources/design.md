# Design

## Context

Voir `proposal.md` pour la motivation. Le client actuel utilise le serveur MCP officiel Home Assistant et n'expose au modèle que les outils dont le nom figure dans une liste d'autorisation locale ; les schémas et descriptions utilisés par l'agent sont contrôlés par l'application. L'état courant, le statut et le diagnostic VTherm sont déjà accessibles. Une branche de développement VTherm fournit un outil d'historique Recorder pour une seule entité climate, ainsi que des outils de plugins et de journaux ; leur compatibilité avec les versions prises en charge reste à vérifier.

## Goals / Non-Goals

**Goals:**

- Ajouter des lectures complémentaires à la demande, uniquement pour le VTherm sélectionné et les entités explicitement liées.
- Limiter l'historique Recorder à l'entité climate du VTherm sélectionné ; ne pas demander l'historique de ses entités dépendantes.
- Conserver `GetLiveContext` comme exception unique pour fournir au modèle le contexte global d'état déjà exposé à Assist.
- Conserver un contrôle serveur de lecture seule, l'authentification existante et le masquage des secrets avant envoi aux fournisseurs.
- Fournir à l'agent assez de provenance et de limites pour distinguer observation, hypothèse et absence de données.

**Non-Goals:**

- Fournir un assistant général Home Assistant, ajouter une recherche globale au-delà de `GetLiveContext` ou agréger plusieurs VTherm dans un appel de logs ou de plugins.
- Consulter l'historique Recorder des entités dépendantes du VTherm.
- Lire ou modifier directement la base Recorder, appeler des services Home Assistant, changer une configuration, installer un plugin ou modifier la rétention.
- Lancer une collecte périodique ou transmettre systématiquement toutes les sources au modèle.

## Decisions

1. **Conserver le serveur MCP officiel et une liste d'autorisation locale.** L'application n'expose pas tous les outils que le serveur annonce. `GetLiveContext` est l'unique exception globale, conservée pour le contexte d'état déjà disponible. Chaque autre nouvel outil doit être identifié et validé en lecture seule, déclaré explicitement côté application et appelé uniquement s'il est découvert. Les annotations, descriptions et schémas reçus du serveur ne constituent pas une preuve suffisante qu'un outil est sûr.

2. **Ancrer les nouvelles lectures sur un VTherm sélectionné.** Les outils de plugins et de journaux reçoivent un seul VTherm par appel. Pour lire l'état d'une dépendance, `GetLiveContext` reçoit son `entity_id` exact dans le champ `name` ; le lien doit d'abord être établi par les données VTherm. Les seuls champs faisant foi sont `vtherm_over_switch.underlying_entities`, `vtherm_over_valve.underlying_entities` ou `vtherm_over_climate.underlying_entities`, selon le type publié, ainsi que `vtherm_over_climate.temp_synchronisation.sync_entity_ids` lorsqu'il existe. Les clés d'autres dictionnaires, noms, pièces, configuration et contexte global ne créent pas de lien. Sans filtre, `GetLiveContext` peut fournir le contexte global distinct ; une entité présente dans ce contexte n'est pas, de ce seul fait, considérée comme liée au VTherm. L'historique Recorder ne porte que sur l'entité climate du VTherm ; l'historique d'une dépendance n'est pas demandé.

3. **Appeler les sources selon la question, pas en collecte globale.** Le contexte global `GetLiveContext` est conservé comme source ambiante existante ; les plugins, journaux et historiques ne sont demandés que lorsqu'ils sont pertinents pour la question. Les appels ciblés ne consultent pas d'autres thermostats, et leurs résultats restent associés à leur source et au VTherm concerné.

4. **Borner chaque lecture et préserver sa provenance.** Les requêtes d'historique utilisent une période explicite et ciblent uniquement l'entité climate du VTherm ; les journaux et configurations sont limités aux données renvoyées pour le thermostat ciblé. L'application conserve ou transmet les horodatages, la période réellement couverte et les indications d'accès refusé, d'absence, de pagination ou de troncature fournies par les outils. Les limites du contrat observé sur la branche VTherm sont candidates, mais leur disponibilité doit être vérifiée sur les versions prises en charge avant activation.

5. **Traiter les retours comme des données non fiables et minimiser ce qui sort.** Les secrets connus sont masqués avant la génération du modèle, mais ce masquage ne détecte pas les secrets inconnus. Les réponses complètes `get_status`/`diagnose`, notamment `configuration` et `preset_temperatures`, ne sont donc pas transmissibles telles quelles : avant tout envoi au modèle, l'application doit construire une projection explicite des seuls champs diagnostiques nécessaires. Les configurations de plugins et les journaux bruts suivent la même règle de minimisation ; en l'absence de projection vérifiée, ils ne sont pas transmis. Les valeurs d'identifiants servant à établir les liens sont limitées aux champs énumérés dans la décision 2. Les données retenues ne sont jamais interprétées comme des instructions. Les résultats d'outils ne sont pas relus depuis d'anciennes conversations pour établir un état actuel ; en cas de donnée manquante ou de résultat trop volumineux, l'application indique la limite au lieu de fabriquer une conclusion.

6. **Dégrader proprement si une source n'existe pas.** Un outil absent, non autorisé ou incompatible ne bloque pas la consultation des autres sources. L'assistant distingue l'outil indisponible, l'accès refusé, l'historique non conservé et une réponse vide valide. Les nouveaux outils sont activés seulement pour les noms, schémas, permissions et versions vérifiés.

## Risks / Trade-offs

- **Un outil annoncé comme lecture seule peut avoir des effets non vérifiés** → Vérifier son implémentation et ses effets sur les versions prises en charge ; conserver le refus par défaut et l'autorisation locale exacte.
- **Le masquage ne connaît que les secrets enregistrés ; les journaux bruts et attributs de plugins peuvent contenir des secrets inconnus, des données sans rapport ou du texte hostile** → Ne pas transmettre de réponse brute ; exiger une projection explicite des champs nécessaires, borner le volume et traiter le contenu retenu comme une donnée non fiable.
- **Le contexte global peut contenir des entités sans lien avec le VTherm** → Le conserver uniquement via `GetLiveContext`, le distinguer des sources ciblées et ne pas inférer de relation à partir de sa seule présence.
- **La configuration d'un plugin peut être absente ou contenir des options sensibles** → Ne transmettre aucune configuration brute ; n'ajouter que des champs explicitement autorisés par une projection vérifiée, et signaler les éléments inaccessibles sans les deviner.
- **Recorder peut ne pas avoir conservé l'état ou les attributs demandés** → Rapporter la couverture réelle, la période et les exclusions connues ; ne pas assimiler l'absence de données à l'absence d'événement.
- **Les outils futurs peuvent différer selon les versions de VTherm et Home Assistant** → Découvrir les outils réellement présents, documenter la matrice testée et laisser les sources indisponibles désactivées.

## Migration Plan

Aucune migration de données ni modification de configuration HA n'est requise. Déployer l'élargissement uniquement après validation des outils MCP sur les versions ciblées. En cas de problème, retirer leurs entrées de la liste d'autorisation ; l'état courant et le diagnostic VTherm déjà disponibles restent utilisables. Aucune modification de la rétention Recorder n'est effectuée.

## Open Questions

- Quelles versions prises en charge exposent l'outil d'historique climate et les outils VTherm de consultation des plugins et journaux observés sur la branche de développement, avec quels schémas et permissions ?
- Quels outils exacts du serveur MCP officiel permettent de lire l'état courant des entités liées, et quelles permissions et versions les exposent ?
- Quelles bornes de période, de résultats et de pagination sont compatibles avec les outils réels sans dépasser le contexte des fournisseurs ?
- Quels champs non sensibles des configurations de plugins justifieraient une projection dédiée ? En attendant cette vérification, aucune configuration de plugin n'est transmise.