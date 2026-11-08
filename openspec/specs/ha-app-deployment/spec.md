# ha-app-deployment Specification

## Purpose

Permettre l'installation et l'exploitation de l'assistant VTherm comme app Home Assistant OS avec ingress, en preservant les controles d'acces, les donnees privees et le lancement autonome existants.

## Requirements

### Requirement: Installation versionnee sur les architectures prises en charge
L'app MUST etre installable depuis un depot HA valide avec une image preconstruite correspondant a sa version. Elle MUST declarer uniquement des architectures dont la construction et le demarrage ont ete verifies et rester experimentale tant que la validation reelle n'est pas acquise.

#### Scenario: Installation sur une architecture declaree
- **WHEN** un utilisateur installe une version sur une instance HA OS compatible d'architecture declaree
- **THEN** le Supervisor telecharge l'image correspondante et peut demarrer l'app sans compilation des dependances sur cette instance
- **AND** la version annoncee correspond a l'image executee

#### Scenario: Architecture non verifiee
- **WHEN** une architecture ne dispose pas d'une image dont la construction et le demarrage sont verifies
- **THEN** cette architecture n'est pas annoncee comme prise en charge

### Requirement: Interface integree par ingress
L'app MUST s'ouvrir depuis Home Assistant par ingress, avec affichage optionnel dans la barre laterale, sans carte de tableau de bord, connexion OAuth supplementaire ni port expose sur l'hote. Ses ressources et requetes MUST rester dans son prefixe ingress.

#### Scenario: Ouverture et navigation sous un prefixe ingress
- **WHEN** un administrateur ouvre l'app depuis HA puis consulte sa configuration et sa conversation
- **THEN** l'interface, le logo et les requetes applicatives utilisent le prefixe de cette installation
- **AND** le rechargement et le retour depuis la barre laterale restent fonctionnels

### Requirement: Maintien des controles d'acces en ingress
Le deploiement MUST conserver l'acces reserve aux administrateurs HA actifs verifies et le controle de provenance Supervisor. Une identite absente, ambigue ou falsifiee, une provenance directe ou des droits invérifiables MUST interdire l'acces aux donnees et aux requetes privees.

#### Scenario: Administrateur reconnu par le vrai Supervisor
- **WHEN** une session ingress transmet une identite d'administrateur actif et que HA confirme ses droits
- **THEN** l'app donne acces uniquement aux donnees de cet utilisateur

#### Scenario: Acces non autorise
- **WHEN** une requete provient directement d'un autre client, forge l'identite ou les en-tetes de proxy, ou concerne un compte non administrateur ou desactive
- **THEN** l'app refuse les routes privees et n'execute aucune requete d'assistant

#### Scenario: Verification indisponible
- **WHEN** le Supervisor ne transmet pas une identite exploitable ou la verification HA echoue
- **THEN** aucune conversation ni configuration privee n'est revelee
- **AND** le refus ne propose pas une connexion OAuth inexistante dans ce mode

### Requirement: Configuration interne HA et separation des identifiants
L'app MUST accepter une adresse HA interne valide depuis sa configuration HA et refuser une valeur invalide sans exposer son contenu sensible. L'identite ingress MUST rester distincte du jeton MCP configure par utilisateur ; aucun jeton Supervisor ne MUST etre transmis au navigateur ou au fournisseur de modele.

#### Scenario: Adresse interne personnalisee
- **WHEN** l'utilisateur configure une adresse HTTP sur un reseau de confiance ou HTTPS avec un port personnalise
- **THEN** les appels MCP utilisent cette adresse apres validation sans desactiver la verification TLS

#### Scenario: Options invalides
- **WHEN** l'adresse interne ou le fichier d'options est invalide
- **THEN** le lancement refuse cette configuration avec un diagnostic sans secret plutot qu'utiliser silencieusement une autre instance HA

#### Scenario: Jeton MCP absent
- **WHEN** un administrateur ingress autorise n'a pas configure son jeton MCP
- **THEN** la requete de donnees signale le jeton manquant et n'utilise pas implicitement le jeton Supervisor

### Requirement: Progression des reponses a travers ingress
L'app MUST conserver l'affichage progressif des reponses a travers ingress et signaler les interruptions sans presenter une reponse incomplete comme terminee.

#### Scenario: Reponse progressive
- **WHEN** le fournisseur produit plusieurs fragments avant la fin d'une reponse ouverte depuis HA
- **THEN** les fragments sont visibles avant la fin de la requete, sans attente du corps complet par le deploiement

#### Scenario: Fournisseur ou MCP indisponible
- **WHEN** un service necessaire a la reponse est indisponible ou le flux est interrompu
- **THEN** l'interface signale l'echec sans secret et permet une nouvelle tentative sans enregistrer la reponse comme complete

### Requirement: Persistance privee pendant le cycle de vie
L'app MUST conserver les conversations, leur contexte et les parametres individuels dans son stockage prive apres redemarrage et mise a jour compatible. Elle MUST conserver l'isolation des utilisateurs et refuser un stockage dont les droits ou le proprietaire ne garantissent pas la confidentialite.

#### Scenario: Redemarrage ou mise a jour compatible
- **WHEN** l'app redemarre ou recoit une mise a jour compatible avec son stockage
- **THEN** chaque administrateur verifie retrouve sa conversation, son contexte et ses parametres sans nouvelle saisie des secrets conserves
- **AND** aucune donnee privee d'un autre utilisateur n'est exposee

#### Scenario: Stockage non protege
- **WHEN** le repertoire ou la base ne satisfait pas les protections attendues
- **THEN** l'app refuse son utilisation sans elargir automatiquement les permissions ni supprimer les donnees

### Requirement: Sauvegarde et restauration coherentes de l'app
Les sauvegardes de l'app MUST contenir une copie coherente de ses donnees privees. La documentation MUST expliquer qu'elles contiennent les secrets enregistres et que leur restauration ecrase les donnees de l'app sauvegardee, sans presenter leur contenu comme chiffre par l'assistant.

#### Scenario: Sauvegarde et restauration isolees
- **WHEN** l'utilisateur autorise une sauvegarde puis une restauration limitees a l'app
- **THEN** l'app reprend ses donnees sauvegardees sans restaurer HA ou VTherm
- **AND** l'utilisateur connait l'interruption eventuelle et le remplacement des donnees de l'app avant ces operations

### Requirement: Exploitation sans privileges superflus
L'app MUST fonctionner sans acces materiel, socket Docker, montage de la configuration HA ou privileges d'administration du Supervisor. Son demarrage, ses journaux et son arret MUST permettre son exploitation sans divulguer de secrets ni modifier les configurations HA ou VTherm.

#### Scenario: Arret depuis le Supervisor
- **WHEN** l'utilisateur arrete l'app depuis HA
- **THEN** le processus s'arrete proprement dans le delai prevu et conserve ses donnees persistantes valides
- **AND** HA et les thermostats continuent de fonctionner independamment de l'app

#### Scenario: Inspection du paquet et des journaux
- **WHEN** le paquet et les diagnostics de lancement ou d'echec sont inspectes
- **THEN** aucun secret preconfigure n'est present dans l'image et aucun jeton, cle ou contenu de conversation n'est revele dans les journaux
- **AND** les permissions du paquet se limitent aux besoins d'ingress et de verification des administrateurs via l'API Core

### Requirement: Distribution et compatibilite documentees
Le depot de distribution MUST identifier l'app sans confondre des configurations de developpement avec des apps. Sa documentation MUST decrire installation, options, prerequis MCP et VTherm, suppression des donnees, mises a jour et limites de compatibilite, en separant versions testees et cibles non verifiees.

#### Scenario: Depot charge par le Supervisor
- **WHEN** le Supervisor inspecte la distribution publiee
- **THEN** il identifie l'app declaree sans traiter la configuration OpenSpec comme une autre app

#### Scenario: Prerequis ou essais incomplets
- **WHEN** MCP, les outils VTherm requis ou une validation de version font defaut
- **THEN** la documentation indique les prerequis manquants et les essais non realises sans annoncer une compatibilite prouvee ni modifier HA automatiquement

#### Scenario: Mise a jour publiee
- **WHEN** une nouvelle version est proposee dans le depot
- **THEN** son image versionnee est deja disponible, son changelog decrit les changements et les precautions de migration eventuelles sont explicites

### Requirement: Preservation du lancement autonome
L'ajout du paquet HA OS MUST conserver le lancement local et le parcours OAuth existants sans exiger la presence du Supervisor ou des options d'une app HA.

#### Scenario: Lancement local sans Supervisor
- **WHEN** l'assistant demarre en mode autonome avec sa configuration locale existante
- **THEN** il conserve son adresse d'ecoute et son parcours OAuth sans lire les options du paquet HA OS ni exiger un jeton Supervisor