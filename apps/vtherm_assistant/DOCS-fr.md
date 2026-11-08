# Assistant VTherm : exploitation Home Assistant OS

Cette documentation prend la release `1.0.0` et ses fonctions récentes comme
référence. L'app s'ouvre par ingress et reste réservée aux administrateurs HA.
Elle utilise uniquement le serveur MCP officiel de Home Assistant ; elle ne
demande ni port hôte ni carte de tableau de bord.

## Fonctionnement et limites

L'assistant découvre dynamiquement tous les outils VTherm annoncés par le
serveur MCP dont le schéma est accepté, en lecture comme en écriture. Il peut
ainsi lire l'état et le diagnostic d'un climate VTherm, les informations
publiées sur son algorithme, ses plugins, son historique et ses journaux, ainsi
que l'état d'entités liées, si les versions HA/VTherm et la configuration les
publient.
Les historiques sont limités à 14 jours par requête et les résultats sont
bornés. Plugins, historique et journaux ne sont disponibles que si la version
de VTherm et la configuration MCP les exposent. L'assistant distingue une
observation d'une hypothèse ; il ne garantit pas la cause d'une panne et ne
modifie pas librement les paramètres internes de l'algorithme.

Les outils d'écriture VTherm découverts à l'exécution peuvent permettre de
modifier les actions usuelles publiées par l'intégration, par exemple le mode
HVAC, la température de consigne, un preset ou l'état marche/arrêt. La liste
varie selon les versions et le thermostat. Aucun outil générique d'écriture
Home Assistant n'est autorisé.

Les exemples ne sont pas une liste exhaustive : les possibilités varient selon
la version de VTherm et les outils MCP effectivement publiés.

L'assistant dispose aussi d'un outil de recherche dans la documentation en
ligne officielle de VTherm sur
[versatile-thermostat.org](https://www.versatile-thermostat.org/). La recherche
prend en charge le français, l'anglais et l'allemand et renvoie des extraits
ciblés avec les liens des pages sources ; elle ne parcourt pas le site sans
limite.

**Chaque écriture requiert une confirmation distincte, obligatoire et
préalable.** L'interface affiche le nom de l'outil, le VTherm cible et les
arguments exacts. La demande dans la conversation ne vaut pas accord. En cas de
refus, de cible ambiguë ou de confirmation expirée, aucune écriture n'est
exécutée. Après approbation, l'app rapporte le résultat réellement retourné par
MCP. Vérifiez systématiquement l'état et l'effet dans Home Assistant : une
confirmation ou une réponse ne garantit pas que le chauffage fonctionne comme
prévu.

## Prérequis et installation

Utilisez Home Assistant OS avec un compte administrateur actif, le serveur MCP
configuré et une intégration Versatile Thermostat fonctionnelle. Les entités
climate VTherm ciblées doivent être exposées à Assist pour apparaître dans
l'inventaire. Exposez uniquement les entités nécessaires.

Catalogue : `https://github.com/jmcollin78/vtherm_assistant#ha-app`.

1. Dans **Paramètres > Apps > Boutique d'apps > Dépôts**, ajoutez l'URL du
   catalogue ci-dessus, avec le suffixe `#ha-app`.
2. Installez **Assistant VTherm** (release `1.0.0`), démarrez-le et activez son
   affichage dans la barre latérale.
3. Ouvrez l'app par ingress avec un compte administrateur HA.

L'app ne demande ni accès Docker, ni montage de la configuration HA, ni
privilège Supervisor supplémentaire. L'API Core sert à vérifier l'identité et
les droits d'accès ; elle ne remplace pas le jeton MCP personnel.

## Configurer MCP dans Home Assistant

1. Dans **Paramètres > Appareils et services > Ajouter une intégration**,
   ajoutez **Model Context Protocol** (serveur MCP Home Assistant).
2. Ouvrez la configuration de cette intégration et publiez les APIs/outils
   VTherm nécessaires à l'assistant. N'activez que les ensembles d'outils
   utiles. L'assistant n'accepte qu'une sélection limitée de lectures HA et
   les outils VTherm identifiés par leurs namespaces MCP.
3. Dans la gestion des entités exposées à Assist, activez seulement les climates
   VTherm que l'assistant doit découvrir.
4. Pour l'historique, vérifiez aussi que Recorder a conservé la période
   demandée. L'absence de données ne prouve pas qu'aucun événement n'a eu lieu.

La configuration des APIs, des outils et des options peut varier selon la
version de Home Assistant. Consulter la
[documentation officielle MCP](https://www.home-assistant.io/integrations/mcp_server/).
L'adresse interne de Core utilisée par l'app est `ha_internal_url`, par défaut
`http://homeassistant:8123`. Elle doit être une URL de base HTTP ou HTTPS, sans
chemin, identifiants, paramètres ni fragment. N'ajoutez aucun jeton à l'URL.
En HTTP, jetons et données circulent en clair sur le réseau interne ; utilisez
un réseau de confiance ou HTTPS avec un certificat vérifiable.

## Jeton longue durée

Chaque administrateur enregistre son jeton MCP personnel dans les paramètres
de l'app :

1. Dans Home Assistant, ouvrez votre **profil utilisateur > Sécurité**.
2. Descendez à **Jetons d'accès longue durée**, sélectionnez **Créer un jeton**
   et donnez-lui un nom explicite, par exemple `Assistant VTherm`.
3. Copiez le jeton à sa création ; il ne sera plus affiché ensuite.
4. Dans les paramètres de l'assistant, collez-le dans le champ **Jeton Home
   Assistant**, puis enregistrez.

Le jeton doit appartenir à un administrateur actif. Il est distinct de la
session ingress et de `SUPERVISOR_TOKEN`, que l'app utilise uniquement pour
vérifier les droits via Core. Ne transmettez aucun de ces jetons dans une
conversation, un rapport de bug ou un journal. Révoquez le jeton dans le profil
Home Assistant s'il n'est plus nécessaire. Voir aussi la
[documentation d'authentification HA](https://www.home-assistant.io/docs/authentication/).

## Fournisseur et modèle

Dans les paramètres de l'app, choisissez Google Gemini, OpenAI, Anthropic
Claude ou Ollama. Choisissez un modèle dans le catalogue ou entrez son
identifiant manuellement. Le catalogue peut afficher des modèles retournés par
le fournisseur ou des suggestions ; le statut `non vérifié` signifie que leur
compatibilité d'appels d'outils et de streaming n'est pas certifiée.

Pour un fournisseur distant, enregistrez la clé dans le champ dédié. Pour
Ollama, indiquez une URL accessible depuis le conteneur de l'app et un modèle
déjà installé sur ce serveur. Après enregistrement, testez avec une question de
lecture. Le modèle enregistré n'est pas remplacé automatiquement par une
suggestion.

## Confidentialité et secrets

Les conversations et les résultats MCP utiles au contexte sont conservés dans
la base locale de l'app. Lors d'une génération, le texte de la conversation et
les résultats nécessaires sont envoyés au fournisseur du modèle sélectionné ;
sa politique détermine leur traitement et leur conservation. Le masquage des
secrets connus ne peut pas identifier une information privée inconnue.

**Ne saisissez jamais dans une conversation une clé API, un nom d'utilisateur,
un mot de passe, un jeton, un code de retour, une adresse privée sensible ou un
autre secret.** Les secrets doivent être saisis uniquement dans les champs
dédiés. Les secrets sauvegardés sont stockés en clair dans SQLite ; toute
sauvegarde incluant la base doit donc être protégée et ne doit pas être jointe
à une issue ou à une PR.

## Reprise de la conversation

L'app enregistre la conversation courante et son contexte pour chaque
administrateur. Après redémarrage ou remplacement du conteneur, elle reprend la
dernière conversation enregistrée. Les conversations précédentes ne sont pas
archivées : **Nouvelle conversation** remplace la session courante de cet
utilisateur, sans supprimer ses secrets. Les réponses interrompues ne sont pas
conservées comme des réponses complètes.

Cette reprise automatique est distincte d'une sauvegarde HA exportable. Une
sauvegarde de l'app contient la base et donc les secrets qu'elle stocke.

## Sauvegarde de l'app

Le manifeste utilise `backup: cold` : Supervisor arrête temporairement l'app
pour sauvegarder sa base sans écriture concurrente, puis la remet en route si
elle fonctionnait. Cela peut interrompre une conversation en cours, mais ne
demande pas d'arrêter Home Assistant ni le chauffage.

1. Avant l'opération, confirmez l'interruption temporaire de l'app.
2. Dans **Paramètres > Système > Sauvegardes**, créez une sauvegarde manuelle et
   sélectionnez **Assistant VTherm uniquement** pour cet essai.
3. Vérifiez que l'archive contient l'app et protégez-la comme un secret. Si elle
   est chiffrée, gardez sa clé de récupération hors du chat et des journaux.
4. Vérifiez que l'app redémarre et retrouve sa conversation.

## Restauration

La restauration remplace les conversations, réglages et secrets de l'app par
ceux de l'archive ; les changements depuis cette date seront perdus. Une
sauvegarde existante n'autorise pas automatiquement une restauration.

1. Vérifiez l'archive, la version de l'app et la disponibilité de sa clé de
   déchiffrement. Confirmez séparément la restauration et l'écrasement des
   données courantes.
2. Si nécessaire, sauvegardez d'abord l'état actuel de l'app.
3. Dans la restauration partielle Home Assistant, sélectionnez uniquement
   **Assistant VTherm** et ses données. Ne restaurez pas la configuration HA,
   Recorder, VTherm ou d'autres apps pour récupérer cette conversation.
4. Après redémarrage, vérifiez ingress, la conversation, le modèle et MCP. Un
   jeton restauré peut avoir été révoqué ; remplacez-le dans les paramètres si
   nécessaire.

Ne restaurez pas une ancienne image sur une base migrée sans compatibilité
documentée. Un changement de version d'image seul ne restaure pas les données.