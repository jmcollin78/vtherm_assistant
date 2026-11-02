# Proposition de contrat : historique VTherm via MCP

Ce document est destiné au responsable de Versatile Thermostat. Il décrit une
évolution à concevoir et livrer séparément ; il ne prétend pas qu'un outil
d'historique répondant à ce contrat existe dans VTherm 10.6.3 ou que sa
faisabilité sur le MCP officiel a déjà été vérifiée.

## Objectif

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