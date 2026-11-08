# Sources diagnostiques VTherm via MCP

## Etat de verification au 2026-11-08

- Home Assistant Core `2026.10.4` fournit `homeassistant__GetLiveContext`. Sans filtre, il retourne le contexte des entites exposees a Assist. Son champ `name` accepte aussi un `entity_id` exact ; les tests Core couvrent ce filtrage. Dans le client local, l'outil reste autorise comme contexte global et peut aussi etre appele avec `name` cible, uniquement apres verification du lien par VTherm pour une lecture ciblee.
- Le VTherm installe sur la cible est `10.6.3` ; cette version ne fournit pas `get_history`. Le code source du tag `10.6.4.beta1` contient `get_history` et les outils d'analyse TPI. Les nouveaux outils logs/plugins de la branche `2208-feature-request---add-more-diagnostic-tools-for-ai-assistant` ne sont pas dans ce tag. La pre-release n'est pas la version installee sur la cible.
- Dans le tag `10.6.4.beta1`, `get_history` cible un seul climate VTherm expose a Assist et soumis a une permission de lecture HA. Les bornes sont des dates ISO 8601 avec fuseau, la periode maximale est de 14 jours, la pagination utilise `offset` (defaut 0) et `limit` (defaut 500, maximum 500). Les tests amont couvrent permissions, pagination et lecture Recorder ; ils ne constituent pas un essai sur l'instance HA de la cible.
- Les outils `get_logs` et `get_plugins` ont ete verifies uniquement sur la branche `2208-feature-request---add-more-diagnostic-tools-for-ai-assistant`, commit `4aeb6e9c540c8b911cd64778fd2e2dd06c5e059b`. Ils ne sont pas presents dans le code source du tag `10.6.4.beta1` ni dans la version installee `10.6.3`. Le client n'autorise leurs noms exacts que s'ils sont annonces par le serveur connecte ; leur absence les rend indisponibles a l'agent.
- `get_logs` exige un `entity_id` VTherm ; `start_time`, `end_time` et `min_level` sont facultatifs, avec `DEBUG` par defaut. Il retourne au plus 5000 entrees, avec le niveau, le nom du logger, le message, la periode et les compteurs de troncature. Ses erreurs couvrent notamment les parametres/periodes invalides, cible absente/non exposee/non chargee ou modifiee, collecteur absent/incompatible et echec de lecture.
- `get_plugins` exige uniquement l'`entity_id` d'un VTherm et retourne les plugins/configurations rattaches parmi sept domaines connus, avec liens, faits, diagnostics et erreurs. La couverture amont declare explicitement qu'elle n'est pas exhaustive pour les plugins tiers ou futurs. Les tests de branche couvrent sept adaptateurs et les erreurs de decouverte/lecture sans divulguer leur detail prive.
- Le client autorise les noms exacts `versatile_thermostat__get_history` et `assist__versatile_thermostat__get_history` uniquement lorsqu'ils sont annonces par le serveur. L'historique reste limite au climate VTherm selectionne ; aucune dependance n'est historiquee. Il borne chaque periode a 14 jours, chaque page a 500 et les reponses projetees a 100 elements et 64 Kio. Les etats Recorder ne sont pas des echantillons reguliers ; la retention, les exclusions, les valeurs nulles et les lacunes limitent leur couverture. Les erreurs connues d'acces refuse ou de Recorder indisponible sont conservees comme codes structures ; les autres corps d'erreur non fiables sont remplaces par un message generique.
- Les outils de journaux et plugins sont egalement autorises uniquement sous leurs noms exacts, lorsqu'ils sont annonces. Les journaux verifies ont une limite amont de 5000 entrees ; couverture et troncature sont projetees. La decouverte des plugins tiers ou futurs n'est pas exhaustive. Les erreurs structurees utiles sont projetees, sans retransmettre le corps de texte libre.
- Les outils de modification ne sont jamais exposes, y compris si un serveur leur attribue une indication de lecture seule. Une source absente de la decouverte n'est pas annoncee comme disponible ; un appel refuse ou indisponible ne doit pas etre interprete comme une reponse vide valide. Les resultats vides, incomplets, tronques, les erreurs et les donnees accessibles doivent rester distingues dans la reponse de l'assistant.

## Identifiants lies et minimisation des donnees

Pour un VTherm `10.6.3`, les champs de publication qui etablissent une relation sont `vtherm_over_switch.underlying_entities`, `vtherm_over_valve.underlying_entities` et `vtherm_over_climate.underlying_entities`, selon le type. Pour un `over_climate`, `vtherm_over_climate.temp_synchronisation.sync_entity_ids` ajoute les entites de synchronisation lorsqu'elles sont publiees. Ces identifiants servent uniquement a cibler un etat via `GetLiveContext` avec `name` egal a l'`entity_id` exact ; ils n'autorisent pas une recherche generale ni un historique de dependance. Les autres attributs contenant des cles d'entite, le nom, la piece, la configuration et le contexte global ne prouvent pas de relation.

`get_status` et `diagnose` retournent des reponses plus larges que ces identifiants, notamment la configuration et les temperatures de presets. Le masquage applicatif ne couvre que les secrets connus et ne filtre pas les champs. En consequence, une reponse brute ne doit pas etre transmise au modele : il faut une projection explicite, testee, des seuls champs de diagnostic necessaires. Les sections `configuration` et `preset_temperatures`, les configurations de plugins et les journaux bruts sont exclus tant qu'une projection specifique n'a pas ete verifiee. La projection logicielle et ses tests relevent de la tache OpenSpec 2.3 ; les identifiants ci-dessus suffisent a etablir les liens sans lire ni transmettre la configuration.

Cette note de verification remplace la proposition historique ci-dessous. Elle
decrit le contrat local et les versions source examinees, pas une certification
de bout en bout sur l'installation HA cible. Sur VTherm `10.6.3`, les outils
d'historique, de journaux et de plugins ne sont pas annonces ; l'agent ne peut
donc pas les appeler. Les validations reelles restent a effectuer.

## Proposition historique (remplacée)

Permettre à l'assistant de consulter les événements déjà enregistrés pour un
thermostat et les entités pertinentes de son installation, sur une période
explicite, sans action ni modification de Home Assistant, de VTherm ou de la
rétention Recorder. L'outil doit être exposé par le serveur MCP officiel HA,
et non par un second serveur.

## Opération proposée

Un outil en lecture seule, par exemple `versatile_thermostat__get_history`
(nom définitif à convenir), reçoit :

- l'identifiant du thermostat VTherm et les identifiants des entités demandées ;
- le début inclus et la fin exclue de la période, avec fuseau horaire explicite ;
- une taille de page bornée et un curseur opaque facultatif.

Il renvoie :

- les entités effectivement consultées et la période effectivement couverte ;
- les événements ordonnés de manière stable, avec identifiant d'entité,
  horodatage, état et attributs réellement disponibles ;
- un curseur de page suivante, ou une indication explicite de fin ;
- les données manquantes ou inaccessibles et leur raison lorsqu'elle peut être
  révélée sans divulguer une entité non autorisée ;
- toute troncature ou limite de couverture connue, sans confondre absence
  d'événement et absence d'enregistrement.

Un curseur doit rester associé à la même requête et éviter les doublons ou
omissions entre pages, y compris pour des événements de même horodatage. Le
comportement en cas de curseur expiré ou invalide doit être explicite. Les
formats et limites précis sont à arrêter avec le responsable VTherm.

## Périmètre et sécurité

La couverture doit permettre de retrouver les événements du thermostat et de
ses dépendances pertinentes, notamment températures, consignes, modes,
actionneurs et causes d'inhibition lorsqu'ils sont enregistrés et accessibles.
Une valeur ou un attribut non conservé ne doit pas être reconstruit.

La découverte et la lecture doivent respecter les droits HA et l'exposition
des entités au serveur MCP officiel. Le jeton utilisé par l'assistant peut être
un jeton administrateur distinct de l'utilisateur ingress : l'outil ne doit
pas supposer qu'il délègue automatiquement l'identité de cet utilisateur.
Les erreurs d'autorisation ne doivent pas révéler de données non accessibles.
Aucun service de commande ni outil d'écriture ne doit être nécessaire.

## Critères de vérification

- Périodes, fuseaux, frontières et pagination vérifiés sur plusieurs pages.
- États et attributs disponibles restitués avec leurs horodatages et sources.
- Historique absent, partiel, expiré ou non enregistré signalé explicitement.
- Entités non exposées et accès refusés testés sans fuite de données.
- Aucun changement de VTherm, de Home Assistant ou de la rétention Recorder.
- Absence de l'outil détectée et signalée par l'assistant sur les versions qui
  ne le fournissent pas, dont VTherm 10.6.3 tant que cela reste le cas.

La disponibilité effective de l'outil, ses permissions, ses effets de bord
et sa compatibilité avec les versions HA/VTherm restent à vérifier une fois
l'évolution livrée.