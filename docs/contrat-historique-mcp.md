# Sources diagnostiques VTherm via MCP

## Etat de verification au 2026-11-08

- L'instance locale exposee sur `8123` utilise Home Assistant Core `2026.10.4`, confirme depuis le conteneur. Le checkout VTherm est au tag Git `10.6.4`. Le manifeste inclus dans ce tag annonce toutefois `"version": "10.6.3"` ; cet ecart de metadonnees est present dans le tag lui-meme et n'a pas ete corrige.
- Le 2026-11-08, une session OAuth administrateur de l'application a obtenu un inventaire MCP de deux climates. `homeassistant__GetLiveContext` sans filtre et le statut de `climate.thermostat_switch_1` ont repondu. Le contexte global est reste distingue d'une lecture ciblee ; aucune dependance n'a ete historiquee.
- L'historique du seul `climate.thermostat_switch_1` a ete lu sur 24 heures, du `2026-11-07T19:15:00Z` au `2026-11-08T19:15:00Z` : 18 lignes, pagination complete et aucune troncature signalee. Cela represente des changements Recorder, pas des echantillons reguliers ; retention, exclusions et lacunes restent des limites.
- `get_plugins` a repondu pour ce seul climate : aucun plugin configure identifie (`configured_plugin_count: 0`), diagnostics non pris en charge. La decouverte est limitee aux categories couvertes et n'est pas exhaustive pour les plugins tiers ou futurs.
- `get_logs` a repondu pour ce seul climate, niveau `DEBUG`, sur la meme fenetre demandee : 140 entrees selectionnees, 100 retournees et 40 omises. Les lignes retournees couvrent `18:59:56.183Z` a `19:14:57.131Z`, donc pas toute la fenetre de 24 heures. La limite amont documentee est de 5000 entrees ; la projection applicative limite les resultats transmis a 100 elements et 64 Kio.
- La permission positive a ete verifiee avec l'identite administrateur utilisee par l'application ; aucun essai de refus non-administrateur n'a ete fait. Une demande de changement de consigne a ete refusee par l'assistant. La relecture a conserve `off`, `7.0` et le meme `last_changed` (`2026-11-08T18:59:57.081703Z`) ; `last_updated` a evolue pendant les observations et ce changement n'est pas attribue au diagnostic. Aucun outil d'ecriture n'est autorise par le client.
- Les outils sont exposes uniquement sous leurs noms exacts lorsqu'ils sont annonces. Les periodes d'historique sont explicites, zonees et limitees a 14 jours ; les pages sont limitees a 500 et les reponses projetees a 100 elements et 64 Kio. Les erreurs structurees d'acces refuse ou Recorder indisponible sont distinguees des reponses vides ; les autres corps d'erreur non fiables sont remplaces par un message generique.
- En validation live, une demande de modification de consigne a ete refusee par l'assistant. La relecture immediate du meme climate a conserve `off`, la consigne `7.0` et `last_changed` `2026-11-08T18:59:57.081703Z` ; aucun outil MCP d'ecriture n'a ete appele et aucun etat HA/VTherm n'a ete modifie par cet essai.
- Les tests integres de l'application, du client MCP, des conversations et des secrets (186 passes le 2026-11-08) couvrent l'isolation de deux identites applicatives, le refus d'un utilisateur different et d'une cible VTherm non selectionnee, le masquage des secrets connus, l'exclusion des champs non projetes, ainsi que l'indisponibilite, les erreurs et les reponses tronquees des sources.
- Les deux identites, les secrets et les sources absentes/inaccessibles sont simules par les tests ; aucune seconde identite HA n'a ete utilisee et aucun secret n'a ete injecte dans les journaux ou plugins de l'instance live. La validation live confirme les parcours effectivement accessibles sans modifier l'installation.

## Identifiants lies et minimisation des donnees

Dans le code VTherm au tag `10.6.4` (dont le manifeste indique `10.6.3`), les champs de publication qui etablissent une relation sont `vtherm_over_switch.underlying_entities`, `vtherm_over_valve.underlying_entities` et `vtherm_over_climate.underlying_entities`, selon le type. Pour un `over_climate`, `vtherm_over_climate.temp_synchronisation.sync_entity_ids` ajoute les entites de synchronisation lorsqu'elles sont publiees. Ces identifiants servent uniquement a cibler un etat via `GetLiveContext` avec `name` egal a l'`entity_id` exact ; ils n'autorisent pas une recherche generale ni un historique de dependance. Les autres attributs contenant des cles d'entite, le nom, la piece, la configuration et le contexte global ne prouvent pas de relation.

`get_status` et `diagnose` retournent des reponses plus larges que ces identifiants, notamment la configuration et les temperatures de presets. Le masquage applicatif ne couvre que les secrets connus et ne filtre pas les champs. En consequence, une reponse brute ne doit pas etre transmise au modele : il faut une projection explicite, testee, des seuls champs de diagnostic necessaires. Les sections `configuration` et `preset_temperatures`, les configurations de plugins et les journaux bruts sont exclus ; les tests de projection de la tache OpenSpec 2.3 couvrent les secrets connus/inconnus et les champs exclus. Les identifiants ci-dessus suffisent a etablir les liens sans lire ni transmettre la configuration.

Cette note de verification remplace la proposition historique ci-dessous. Elle
consigne les reponses observees sur l'instance locale ; l'ecart entre le tag et
la version du manifeste est conserve pour eviter d'attribuer ces capacites a une
autre release. L'isolation entre utilisateurs et les scenarios de sources
manquantes restent a valider separement.

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