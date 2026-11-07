# Assistant VTherm : exploitation HA OS

## Prerequisites et compatibilite

Utiliser Home Assistant OS avec Supervisor, un compte administrateur actif,
le serveur MCP officiel configure et une integration Versatile Thermostat qui
fournit les outils VTherm attendus. Verifier les entites exposees au MCP ;
n'exposer que les donnees choisies, jamais toute l'instance automatiquement.
L'assistant est limite aux outils de lecture autorises, sans commande de chauffage.

HA 2026.10 et VTherm 10.6.3 sont des cibles a verifier, pas des compatibilites
deja prouvees. Les images Linux aarch64 et amd64, imports, ressources, stockage
et arret sont testes localement ; ingress, droits Supervisor et streaming
reel restent a verifier sur HA OS. Le test amd64 local utilise l'emulation.
Le packaging HA Container autonome est hors de ce lot.

## Installation et barre laterale

Le catalogue et l'image de cette version ne sont pas encore publies. Apres
publication et accord pour l'installation :

1. Dans Parametres > Apps > Boutique d'apps > Depots, ajouter l'URL du catalogue
   propre indiquee dans la release. Ne pas ajouter le depot source brut qui
   contient `openspec/config.yaml`.
2. Choisir Assistant VTherm, verifier la version experimentale et l'architecture,
   puis installer l'image preconstruite. Ne pas compiler sur HA principal.
3. Verifier l'option d'adresse Core, demarrer l'app et activer son affichage
   dans la barre laterale. Ouvrir l'interface Web ou Assistant VTherm dans
   cette barre ; aucun port externe, certificat propre ou carte n'est necessaire.
4. Verifier la session administrateur HA. Un refus ingress ne propose pas OAuth :
   verifier les droits et le passage par Supervisor, pas un acces IP direct.

L'app ne demande ni montage de configuration HA, acces Docker, materiel,
reseau hote ni role administrateur Supervisor. L'acces a l'API Core sert a
verifier les droits et ne remplace pas le jeton utilisateur MCP.

## Configuration

Dans les options de l'app, `ha_internal_url` designe la base de Core depuis
le conteneur, par defaut `http://homeassistant:8123`. Utiliser HTTP ou HTTPS
sans chemin, identifiants, parametres ni fragment. Un port personnalise est
accepte ; Core avec TLS demande une URL HTTPS et un certificat verifiable.
Ne jamais placer un jeton dans cette URL ni desactiver la verification TLS.
HTTP transmet les donnees et jetons en clair sur le reseau interne : utiliser
uniquement un reseau de confiance, ou HTTPS.

Supervisor fournit `/data/options.json` avant le chargement du backend.
Ces options sont prioritaires sur l'environnement ; une valeur invalide,
un fichier illisible ou absent sous Supervisor bloque le lancement sans
afficher son contenu brut. Corriger les options puis redemarrer seulement l'app.

Dans l'interface, chaque administrateur configure son modele, les cles du
fournisseur et son jeton HA personnel administrateur pour MCP. Le jeton
`SUPERVISOR_TOKEN`, fourni par HA au backend, sert uniquement au controle
des droits Core et n'est jamais une cle MCP ni une cle de modele. Ne pas
copier ces secrets dans les options globales, le manifeste ou les journaux.

Une erreur MCP exige de verifier son integration, l'adresse interne et le
jeton personnel ; une erreur fournisseur exige de verifier le modele et
la cle. Utiliser la verification de connexion et reessayer la question apres
correction. Ne pas arreter HA ou le chauffage pour simuler une panne.
Un rapport de bug ne doit contenir ni jeton, cle, archive ni conversation privee.

## Donnees et confidentialite

Les conversations, modeles et secrets de chaque administrateur restent dans
`/data/vtherm-assistant/conversations.sqlite3`. Le repertoire est prive `0700`
et la base `0600`, avec un proprietaire UID 0 stable. Le stockage mal protege
est refuse sans reparation automatique. Le volume persiste apres redemarrage
ou remplacement du conteneur ; aucune donnee du Mac n'est importee.

Les jetons HA et cles fournisseur ne sont pas chiffres dans SQLite. Les
sauvegardes qui contiennent cette base contiennent donc aussi ces secrets.
Proteger les archives, leurs copies et les cles de recuperation ; ne jamais
les joindre a un rapport de bug. Une sauvegarde exportee par l'interface HA
est dechiffree lors du telechargement et doit etre traitee comme un secret.

## Sauvegarde de l'app

Le manifeste utilise `backup: cold` : Supervisor arrete temporairement l'app
pour sauvegarder sa base sans ecriture concurrente, puis la remet en route
si elle fonctionnait. Les conversations en cours peuvent etre interrompues.
Cela ne demande pas d'arreter Home Assistant ni le chauffage.

Avant une mise a jour, suppression de donnees ou desinstallation :

1. Obtenir l'accord pour une sauvegarde et annoncer l'interruption de l'app.
2. Dans Parametres > Systeme > Sauvegardes, creer une sauvegarde manuelle et
   choisir uniquement Assistant VTherm. Verifier le contenu reel de l'archive ;
   ne pas inclure les reglages Home Assistant, Recorder, autres apps ou dossiers
   pour cet essai isole.
3. Relever version de l'app et date. Verifier la fin de la sauvegarde et la
   disponibilite de la cle du kit d'urgence si l'archive est chiffree, sans
   transmettre cette cle a un assistant ou a un journal.
4. Conserver un point de recuperation utilisable dans un emplacement choisi
   et protege, puis verifier que l'app redemarre et retrouve ses donnees.

La creation de cette procedure n'est pas une validation de sauvegarde reelle.

## Restauration isolee et retour de version

Une restauration ecrase les conversations, reglages et secrets de l'app par
ceux de l'archive. Les changements depuis sa date seront perdus. Une sauvegarde
existante n'autorise pas automatiquement cette operation.

1. Verifier que l'archive contient Assistant VTherm, sa version et ses donnees,
   et que sa cle de dechiffrement est disponible. Verifier aussi que l'image
   de cette version est encore accessible.
2. Faire confirmer separement la restauration de cette app et la perte des
   changements depuis l'archive. Sauvegarder son etat actuel avant de l'ecraser
   si une autre recuperation pourrait etre necessaire.
3. Choisir une restauration partielle et selectionner uniquement Assistant
   VTherm et ses donnees. Ne pas selectionner les reglages HA, Recorder, autres
   apps ou dossiers. Ne jamais lancer une restauration complete de HA pour
   revenir sur cette app.
4. Apres redemarrage de l'app, verifier sa version, ingress, les conversations,
   le modele et la connexion MCP. Les jetons restaures peuvent avoir ete revoques
   ou avoir expire ; les ressaisir dans l'interface si necessaire.

Un changement de tag d'image seul n'est pas une restauration des donnees.
Ne pas appliquer une ancienne image a une base migree sans compatibilite
explicitement documentee. Pour un retour de version, preferer une archive de
l'app prise avant la mise a jour et conserver une image versionnee immutable.
Ne pas toucher aux configurations VTherm ni au chauffage pour ce retour.

Aucune sauvegarde ou restauration sur HA OS n'a encore ete testee dans ce lot.

## Suppression et desinstallation

Avant une suppression irreversible, faire confirmer le perimetre et la perte
des donnees, et proposer une sauvegarde utilisable avant l'action.

Dans l'interface, Nouvelle conversation efface les echanges du compte courant.
Supprimer la cle retire sa cle du fournisseur selectionne ; Supprimer le jeton
retire son jeton MCP stocke dans l'app. Ces actions ne suppriment pas les donnees
des autres administrateurs ni les copies deja presentes dans les sauvegardes.
Revoquer aussi les jetons aupres de HA ou du fournisseur si l'objectif est
d'invalider des copies anciennes, pas uniquement de retirer le stockage local.

Pour retirer toutes les donnees et l'app, confirmer la desinstallation
d'Assistant VTherm uniquement, puis utiliser la page de cette app dans HA.
Verifier la suppression de ses donnees dans l'option de desinstallation.
Cela ne retire pas VTherm, MCP ou les configurations de chauffage. Les archives
existantes restent sensibles : leur suppression est une operation distincte
qui demande son propre accord et un examen des points de recuperation restants.