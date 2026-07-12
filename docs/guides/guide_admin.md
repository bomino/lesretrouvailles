# Guide administrateur — Les Retrouvailles

Ce guide s'adresse à toute personne avec des droits d'administration : **Super Admin** (le propriétaire de la plateforme, Bomino) ainsi que les **co-administrateurs** que le Super Admin peut désigner. Il complète les runbooks opérationnels (`docs/runbooks/`).

> 🔒 Ce guide contient des actions destructives (suppression de comptes, purge de données). Lisez chaque section avant d'agir, et préférez le **mode aperçu** ou **dry-run** quand il existe.

---

## 1. Deux niveaux d'administration

La plateforme a deux niveaux distincts depuis Gestion v1 (mai 2026) :

### **Super Admin** (un seul compte)
- Accès complet : la console **`/gestion/`** (interface simple) **et** le panneau Django **`/admin/`** (avancé).
- Seul à pouvoir : purger des comptes (RGPD), importer un roster en masse, promouvoir un autre membre comme co-admin, modifier la liste « Nous recherchons aussi », publier des fiches In Memoriam.
- En production aujourd'hui : `bominomla`.

### **Co-administrateur** (1 à 3 comptes prévus)
- Accès uniquement à la console **`/gestion/`** — la zone Django `/admin/` lui est invisible.
- Peut faire toutes les opérations courantes : annuaire des membres, modification de profil, suspendre/réactiver un compte, changer le numéro WhatsApp d'un membre, regénérer un lien de connexion, approuver ou refuser une cooptation.
- Le Super Admin peut promouvoir un membre en co-admin (voir §2.2 ci-dessous).

> 💡 Cette répartition reste gérable par 2-3 administrateurs bénévoles. La plupart des opérations courantes prennent quelques minutes par semaine.

Vos responsabilités selon votre rôle :

- **Onboarder** les nouveaux membres (cooptation publique en `/gestion/cooptations/` ; import en masse — Super Admin uniquement)
- **Modérer** : approuver les candidatures, gérer les demandes de retrait, suspendre les comptes problématiques
- **Soutenir** les membres : répondre aux questions par WhatsApp, renvoyer les liens magiques perdus
- **Curer le contenu** (Super Admin uniquement pour v1) : Mur des souvenirs, In Memoriam, liste publique
- **Surveiller** (Super Admin uniquement) : santé des sauvegardes, rapports DMARC, logs Railway
- **Traiter les demandes RGPD** (Super Admin uniquement) — irréversibles

---

## 2. Accéder aux outils

### 2.1 La console `/gestion/` (utilisée par tous les admins)

C'est l'interface principale, simple et adaptée au mobile, conçue pour ne jamais avoir besoin de la zone Django.

- **Depuis la plateforme** : connectez-vous, cliquez sur **« ⚙ Gestion »** dans la barre de navigation. Le lien n'est visible que pour les comptes admin (`is_staff=True`).
- **Directement** : **https://villageretrouvailles.com/gestion/**.

Vous arrivez sur un tableau de bord avec **quatre compteurs** (membres actifs, cooptations à traiter, comptes suspendus, **souvenirs en brouillon**) et **quatre liens** dans le sous-menu :

- **Membres** — annuaire complet, recherche, modification de profil, suspendre/réactiver, changer le numéro WhatsApp, regénérer un lien de connexion.
- **Cooptations** — file des candidatures (par défaut : « à traiter »), revue détaillée avec parrains et questionnaire, approuver ou refuser.
- **Souvenirs** — gestion du Mur des souvenirs (voir §6) : ajouter une photo, modifier la légende, remplacer l'image, publier ou dépublier.
- **Outils avancés** — visible **uniquement pour le Super Admin**. Lien direct vers `/admin/` pour les actions non couvertes par `/gestion/` (purge RGPD, import en masse, fiches In Memoriam, suppression définitive d'une photo).

> 💡 **Repère visuel** : dans la barre de navigation principale et dans le sous-menu Gestion, la section où vous vous trouvez est surlignée. Pratique pour ne pas se perdre en cliquant d'une page à l'autre.

> 🔒 **Sécurité élémentaire :**
> - Ne partagez **jamais** votre mot de passe d'admin (ni par WhatsApp, ni par email).
> - Changez-le immédiatement si vous l'avez écrit dans une conversation.
> - Déconnectez-vous toujours après usage sur un appareil partagé.
> - Chaque action de `/gestion/` est tracée dans le journal d'audit avec le préfixe `gestion.*` (visible par le Super Admin dans `/admin/auditlog/`).

### 2.2 Promouvoir un co-administrateur (Super Admin uniquement)

Pour donner à un membre actif l'accès à `/gestion/` :

1. Trouvez son `User` dans `/admin/auth/user/` (recherche par email ou nom d'utilisateur).
2. Ouvrez la fiche, cochez **« Staff status »** (mais **pas** « Superuser status »).
3. Sauvegardez.

Effet immédiat : le membre voit maintenant le lien **« ⚙ Gestion »** dans sa barre de navigation et peut accéder à `/gestion/`. Il **ne voit pas** `/admin/` (la console `/admin/` est verrouillée à `is_superuser=True` depuis Phase 0 de Gestion v1).

Pour révoquer : décocher **« Staff status »**. Le membre reste un membre régulier de la plateforme.

> 💡 **Recommandation** : ne donnez le `Staff status` qu'à des personnes que vous connaissez personnellement. Les actions sont auditables, mais une RGPD purge accidentelle reste irréversible — gardez ce pouvoir entre vos mains.

### 2.3 Le panneau Django `/admin/` (Super Admin uniquement)

Réservé au Super Admin pour les actions avancées :
- **Members** — purge RGPD (irréversible), demandes de retrait, journal d'audit complet
- **Cooptation** — questions de connaissance (config), réponses au questionnaire
- **Memoires** — **suppression définitive** d'une photo du Mur des souvenirs (la création, la modification, la publication et la dépublication se font désormais via `/gestion/souvenirs/` ; voir §6)
- **Memoriam** — fiches In Memoriam et modération de nominations
- **Authentication and Authorization** — utilisateurs, groupes, permissions, EmailAddresses Allauth

Tout co-admin qui tente d'accéder à `/admin/` sera redirigé vers la page de connexion Django sans pouvoir y entrer.

---

## 3. Onboarder de nouveaux membres

Trois méthodes selon le contexte :

### 3a. Import en masse (recommandé pour le lancement)

C'est la méthode utilisée pour intégrer les ~200 membres du groupe WhatsApp existant. Tout est documenté dans :

- **Procédure complète** : `docs/runbooks/launch.md`, étapes 2 à 5
- **Format CSV + templates WhatsApp** : `docs/runbooks/onboarding.md`
- **Template CSV vide** : `docs/runbooks/roster_template.csv`

En résumé :

1. Préparez un fichier `roster.csv` avec une ligne par membre (colonnes : prénom, nom, surnom, WhatsApp, email optionnel, années, classes optionnel, ville, pays, profession, photo optionnelle).
2. (Optionnel) Mettez les photos dans un dossier `roster_photos/`.
3. **Aperçu sans changement** :
   ```bash
   python manage.py import_whatsapp_roster roster.csv \
       --photos-dir roster_photos \
       --magic-links-out magic_links.csv \
       --dry-run
   ```
4. Corrigez les erreurs éventuelles dans le CSV.
5. **Exécution réelle** (sans `--dry-run`) : crée les comptes, envoie les emails (pour ceux qui en ont un), écrit les liens magiques pour les autres dans `magic_links.csv`.
6. Pour chaque ligne du `magic_links.csv`, copiez l'URL et envoyez-la en message privé WhatsApp au membre concerné, en utilisant le template du runbook.

### 3b. Cooptation publique (pour les nouveaux candidats hors WhatsApp)

Quelqu'un d'extérieur au groupe WhatsApp découvre la plateforme et veut s'inscrire :

1. Le candidat remplit le formulaire public à `/inscription/`.
2. Il choisit deux parrains parmi les membres existants.
3. Les parrains reçoivent un email les invitant à valider.
4. Quand les deux parrains ont accepté (ou délais expirés), la candidature passe en **« À traiter »**.
5. Vous la voyez dans **`/gestion/cooptations/`** (filtre par défaut : « à traiter »).

Pour approuver (Super Admin **et** co-admins) :

1. Cliquez sur la candidature.
2. Vérifiez les informations (nom, années, classes si renseignées, ville, parrainages, questionnaire).
3. Cliquez **« Approuver »** dans la barre latérale → confirmez le pop-up.
4. Le système crée automatiquement le `User` + `Member` et envoie l'email de définition de mot de passe au candidat.
5. Une entrée `gestion.application.approved` est ajoutée au journal d'audit.

Pour refuser :

1. Cliquez sur **« Rejeter… »** dans la barre latérale (le formulaire se déplie).
2. Saisissez le motif (5 caractères minimum, visible par le candidat dans son email de notification).
3. Cliquez **« Confirmer le rejet »** → confirmez le pop-up.
4. Une entrée `gestion.application.rejected` est ajoutée au journal d'audit.

> 💡 La candidature refusée est conservée 6 mois (rétention RGPD), puis purgée automatiquement.
> 💡 L'approbation est **irréversible** (création d'un compte Membre). Le rejet est techniquement réversible mais douloureux (édition manuelle en `/admin/`) — réfléchissez avant de cliquer.

### 3c. Création manuelle (cas exceptionnels)

Pour ajouter un membre directement sans passer par la cooptation (par exemple : un admin que vous voulez créer sans flux complet) :

1. Allez à **Authentication → Users → Add user**.
2. Saisissez **username** (en chiffres = numéro WhatsApp pour cohérence) et un mot de passe.
3. Sauvegardez. Vous arrivez sur le formulaire complet.
4. Cochez **« Active »**, **« Staff »** et/ou **« Superuser »** selon le besoin.
5. Renseignez l'email si applicable.
6. Sauvegardez.
7. Allez à **Members → Members → Add member**, lié à ce User.
8. Renseignez : nom, prénom, années, ville, etc. (classes facultatives — peut rester vide).
9. Sauvegardez.

> ⚠️ Cette méthode ne crée **pas** automatiquement la `EmailAddress` Allauth nécessaire pour la connexion par email. Préférez l'import en masse ou la cooptation publique chaque fois que possible.

---

## 4. Renvoyer un lien magique pour un membre sans email

C'est le cas le plus fréquent en régime de croisière (rappelez-vous : ~80 % de notre cohorte n'a pas d'email).

### Procédure recommandée — depuis `/gestion/` (Super Admin **et** co-admins)

1. Le membre vous écrit sur WhatsApp : *« J'ai oublié mon mot de passe »* ou *« Le lien ne fonctionne plus »*.
2. Allez à **`/gestion/membres/`**, recherchez le membre par nom, prénom ou numéro WhatsApp, cliquez sur son nom.
3. Sur la fiche, cliquez **« Régénérer un lien de connexion »**.
4. Lisez l'encadré (lien valable 7 jours, l'ancien reste valide jusqu'à expiration), puis cliquez **« Générer un nouveau lien »**.
5. Le lien apparaît dans une boîte verte. Deux options :
   - **« Envoyer par WhatsApp »** — ouvre WhatsApp Web/mobile avec un message déjà rédigé pour ce membre. Vérifiez et envoyez.
     > 💡 Ce bouton n'apparaît que si le numéro WhatsApp du membre est renseigné (champ `Numéro WhatsApp` sur la fiche, format chiffres uniquement avec code pays). Pour les membres coopté·e·s ou les comptes admin créés manuellement, vous devrez peut-être d'abord remplir ce champ via **Modifier le profil**. Le bouton **« Copier »** marche dans tous les cas.
   - **« Copier »** — copie l'URL dans votre presse-papier ; collez-la où vous voulez (email, autre messagerie).
6. Une entrée `gestion.login_link.reissued` est ajoutée au journal d'audit.

### Procédure de secours — ligne de commande (Super Admin uniquement)

Utile si la console est en panne ou si vous traitez plusieurs réémissions en série :

```bash
railway run --service lesretrouvailles python manage.py reissue_login_link 22790000001
```

Copiez l'URL imprimée et envoyez-la au membre via WhatsApp DM avec le message du Template 3 (`docs/runbooks/onboarding.md`).

### Cas particuliers

- **Le membre dit que le lien ne s'ouvre pas** → demandez-lui de le copier-coller dans son navigateur (Chrome / Safari) au lieu d'ouvrir directement depuis WhatsApp ; ça contourne d'éventuels problèmes de prévisualisation.
- **Le numéro WhatsApp donné ne trouve pas de compte** → vérifiez le format : `/gestion/membres/` accepte la recherche partielle ; côté CLI, la commande attend les chiffres seulement, sans `+` ni espace ni tiret.
- **Le membre a un nouveau numéro WhatsApp** → utilisez `/gestion/membres/<slug>/identifiant/` pour changer son identifiant (avec confirmation du numéro actuel), puis mettez à jour le champ `Numéro WhatsApp` sur sa fiche via **Modifier le profil**. Régénérez ensuite un lien si besoin.

### Format du numéro WhatsApp (champ `Numéro WhatsApp` sur la fiche)

Stocké en chiffres seulement, code pays inclus, **sans `+`**, sans espace, sans tiret. Le formulaire **supprime automatiquement** ces caractères au moment de la sauvegarde — vous pouvez coller depuis WhatsApp tel quel :

| Vous tapez ou collez | Sauvegardé comme |
|---|---|
| `+227 90 00 01 23` | `22790000123` (Niger) |
| `(555) 123-4567` ⚠️ | `5551234567` — accepté mais le partage WhatsApp 404era car il manque le code pays. Toujours inclure le code pays. |
| `+1 555-123-4567` | `15551234567` (USA) |
| `+33 6 12 34 56 78` | `33612345678` (France) |

L'affichage côté membre rajoute le `+` pour la lisibilité (`+22790000123`).

---

## 5. Supprimer un compte (demande RGPD)

Conformément au Règlement Général sur la Protection des Données (RGPD, article 17), tout membre a le droit de demander la suppression complète de ses données personnelles. Vous devez répondre dans un délai maximum de **30 jours**.

### Procédure (interface admin)

1. Allez à **Members → Members**.
2. Cherchez le membre par nom ou email.
3. Cochez la case à gauche de la ligne du membre.
4. Dans le menu déroulant des actions en haut, choisissez **« Purger RGPD (irréversible) »** → cliquez **Go**.
5. Une page de confirmation s'affiche avec :
   - Le résumé de ce qui sera supprimé (compte, profil, photos, requêtes de parrainage, etc.)
   - Un champ texte de confirmation. Saisissez **l'email exact** du membre — ou, pour les ~80 % de membres **sans email**, son **username exact** (le numéro WhatsApp en chiffres). La page vous indique lequel des deux elle attend.
6. Saisissez la valeur demandée puis cliquez **« Purger maintenant »**.
7. Vous êtes redirigé vers la liste avec un message de succès.
8. Une entrée `rgpd.member.purged` est ajoutée au journal d'audit (sans aucune donnée personnelle, juste un hash).

### Procédure (ligne de commande, alternative)

Pour traiter plusieurs demandes en lot ou via SSH :

La commande accepte **l'email OU le username** (numéro WhatsApp), donc elle
fonctionne aussi pour les membres sans email. `railway ssh` (et non `railway run`) :
la base n'est joignable que depuis le réseau interne de Railway.

```bash
# Aperçu sans changement
railway ssh --service lesretrouvailles -- python manage.py rgpd_purge_member alice@example.com --dry-run

# Membre sans email : passez son username (chiffres WhatsApp)
railway ssh --service lesretrouvailles -- python manage.py rgpd_purge_member 22790000001 --dry-run

# Exécution réelle
railway ssh --service lesretrouvailles -- python manage.py rgpd_purge_member alice@example.com
```

Le runbook détaillé : `docs/runbooks/rgpd-purge.md`.

### Cas particuliers

- **Le membre a créé des fiches In Memoriam** → la commande refuse poliment (les fiches concernent d'autres personnes, on ne peut pas les supprimer en cascade). Réassignez le `created_by` des fiches à un autre admin avant de réessayer.
- **Self-purge** → vous ne pouvez pas vous supprimer vous-même. Demandez à un autre admin.

### Notification au membre

Une fois la suppression effectuée, répondez au membre (par email ou WhatsApp selon le canal d'origine de la demande) avec un message du type :

> Bonjour,
> Conformément à votre demande au titre de l'article 17 du RGPD, nous avons procédé à la suppression définitive de votre compte et des données associées sur la plateforme Les Retrouvailles le {date}.
> Référence d'audit : {audit_log_id}.
> Cordialement.

---

## 6. Gérer le contenu du Mur des souvenirs

Le Mur des souvenirs est curé par les administrateurs (les membres ne peuvent pas uploader directement en Phase 1). Depuis 2026-05-10, **les co-administrateurs peuvent gérer les photos directement depuis `/gestion/souvenirs/`** — plus besoin de passer par le Super Admin.

### Accéder à la console Souvenirs

- **Depuis le tableau de bord** : la tuile **« Souvenirs en brouillon »** (4ᵉ tuile) compte les photos téléversées en attente de publication ; cliquez dessus pour ouvrir la liste filtrée sur les brouillons.
- **Depuis le sous-menu Gestion** : cliquez sur **« Souvenirs »**.
- **Directement** : **https://villageretrouvailles.com/gestion/souvenirs/**.

### Ajouter une photo

1. Sur `/gestion/souvenirs/`, cliquez sur **« Ajouter une photo »**.
2. **Photo** : cliquez sur **« Choisir un fichier »**, sélectionnez une image (JPEG, PNG ou WebP, **8 Mo maximum**).
3. **Légende** : décrivez la photo en quelques phrases (qui, quand, où, le contexte).
4. **Date approximative** (optionnel) : la date à laquelle la photo a été prise. Laissez vide si vous ne savez pas.
5. **Lieu** (optionnel) : Birni, Niamey, Paris, etc.
6. **Statut** :
   - `Brouillon` — visible uniquement par les admins (pour préparer en avance ou batcher plusieurs photos avant publication)
   - `Publiée` — visible par tous les membres
7. Cliquez **« Créer »**. Vous êtes ramené à la liste avec un bandeau de confirmation.

> 🔒 **Protection vie privée automatique :** depuis 2026-05-10, les métadonnées EXIF (coordonnées GPS, modèle d'appareil, date de prise de vue) sont **retirées côté serveur** avant l'envoi à Cloudinary pour toutes les photos que **vous** téléversez : Mur des souvenirs, fiches In Memoriam, photos importées avec le roster, et photos de membres déposées depuis `/gestion/`.
>
> ⚠️ **Exception connue :** la photo qu'un membre téléverse lui-même depuis « Profil → Modifier » part directement de son navigateur vers Cloudinary et **ne passe pas** par ce nettoyage (tech-debt F-03). Tant que ce n'est pas corrigé, ne promettez pas aux membres que leur photo de profil est nettoyée — et si un membre s'en inquiète, re-téléversez sa photo à sa place depuis `/gestion/`.

### Modifier la légende, remplacer la photo, ou changer le statut

1. Sur la liste, cliquez sur la vignette de la photo à modifier.
2. La page d'édition affiche la photo en grand, suivie du formulaire :
   - **Remplacer la photo** (optionnel) — sélectionnez un nouveau fichier ; l'ancienne image est automatiquement supprimée de Cloudinary après sauvegarde.
   - **Légende, date, lieu, statut** — modifiez ce que vous voulez.
3. Cliquez **« Enregistrer »**.
4. Pour basculer entre Brouillon et Publiée sans rien d'autre toucher, utilisez le bouton **« Publier »** ou **« Dépublier »** en bas de la page d'édition.

> 💡 **Recherche + filtres** : la barre de recherche en haut de la liste filtre par légende ou lieu (accents tolérés). Les puces **Toutes / Publiées / Brouillons** filtrent par statut.

### Supprimer définitivement une photo

La console `/gestion/` ne permet **pas** la suppression définitive d'une photo (par sécurité — c'est irréversible et supprime aussi le fichier de Cloudinary). Pour ça :

1. Dépubliez d'abord la photo via `/gestion/souvenirs/<id>/modifier/` → bouton **« Dépublier »**. Elle disparaît du Mur des souvenirs pour les membres.
2. Si vous voulez vraiment effacer la photo de Cloudinary : Super Admin, allez sur `/admin/memoires/memory/`, cochez la ligne, action **« Delete selected memorys »**.

> 💡 **Quoi auditer** : toutes les actions sur les photos écrivent une ligne dans le journal d'audit (`memoires.memory.created`, `memoires.memory.edited`, `memoires.memory.published`, `memoires.memory.unpublished`). Le Super Admin peut consulter le journal complet dans `/admin/members/auditlog/`.

> 💡 Visez 10-20 photos seed à l'ouverture (objectif master spec). Pas besoin d'avoir un titre énorme — quelques photos bien légendées valent mieux qu'une grande galerie sans contexte.

---

## 7. Gérer les fiches In Memoriam

Les fiches In Memoriam honorent des camarades décédés. La procédure est **plus stricte** que pour le Mur des souvenirs : il faut un **accord explicite de la famille** avant publication (Annexe D du master spec, §D.5).

### Procédure complète

1. **Examiner les nominations** : allez à **Memoriam → In memoriam nominations**. Vous voyez les propositions soumises par les membres via le formulaire `/in-memoriam/nominer/`.
2. **Contacter la famille** (par téléphone, WhatsApp ou en personne — pas par email impersonnel) en utilisant l'indication de contact donnée par le membre proposant. Expliquez le projet, écoutez leurs souhaits, demandez leur accord pour la publication.
3. **Documenter l'accord** : nom de la personne qui a donné l'accord, date, canal (email / WhatsApp / téléphone / en personne).
4. **Créer la fiche** : allez à **Memoriam → In memoriam entries → Add**.
   - **Nom complet**, **surnom** (optionnel), **années au CEG**, **classes** (optionnel)
   - **Année de naissance** et **année de décès** (optionnelles mais recommandées)
   - **Photo** (optionnelle)
   - **Hommage** (markdown supporté — quelques paragraphes, ton respectueux et personnel)
   - **Famille — donneur d'accord**, **date de l'accord**, **canal**
   - **Statut** : `draft` pour relire avant publication, puis `published` quand prêt
5. Sauvegardez. Quand le statut passe à `published`, un email est envoyé aux membres opted-in.

### Modifier ou archiver

- **Mettre à jour le contenu** d'une fiche publiée : modifiez librement, mais incrémentez `approved_content_version` à chaque changement substantiel pour traçabilité.
- **Archiver** (à la demande de la famille) : changez statut à `archived`. La fiche disparaît de la liste publique mais est conservée dans la base (pour auditabilité).

### Nominations refusées

Si une nomination ne donne pas lieu à création (par exemple : la famille refuse, ou un doublon avec une fiche existante), changez le statut de la nomination à `declined` ou `duplicate` et ajoutez une note admin.

> ⚠️ **Aucune fiche** ne doit jamais être publiée sans accord familial documenté. C'est la règle non négociable de la communauté.

---

## 8. Gérer la liste publique « Nous recherchons aussi »

Cette liste apparaît sur la page d'accueil publique pour aider à retrouver des camarades non encore inscrits.

### Ajouter un nom

1. Allez à **Members → Public search entries → Add**.
2. **Prénom**.
3. **Initiale du nom (1 à 2 caractères)** — saisissez **uniquement la première lettre** du nom de famille (ex. `M` pour Moussa). Le champ est limité à 2 caractères pour les préfixes type `Mc` ou `Da`. **N'écrivez pas le nom complet** — la liste publique est volontairement minimale en PII (master spec §6.5).
4. **Années au CEG** (1980-1985, plusieurs années possibles).
5. **Note** (optionnelle) : une courte ligne d'introduction publique (ex. « Cherché par sa promotion 1983 »).
6. Sauvegardez. Vous êtes automatiquement enregistré comme cosignataire (un seul admin suffit pour publier en mode P4d).

> 💡 Le formulaire bloquera automatiquement la saisie au-delà de 2 caractères dans le champ « Initiale du nom » et affichera un message d'aide clair en cas d'erreur.

Un email FYI est envoyé aux autres admins pour transparence.

### Demande de retrait

Quand quelqu'un voit son nom sur la liste publique et veut le retirer, il clique sur **« Retirer mon nom »** sur la page d'accueil. Cela crée une `Removal Request`.

1. Allez à **Members → Removal requests** pour voir les demandes en attente.
2. La demande est en `pending_confirmation` jusqu'à ce que le demandeur confirme par email ou expire (30 jours).
3. Une fois confirmée, le retrait s'exécute automatiquement et le nom disparaît.
4. Vous n'avez généralement rien à faire — c'est entièrement automatique. Surveillez juste qu'il n'y a pas de demandes coincées en `pending_confirmation` depuis plus de 30 jours (utiliser le filtre par statut).

### Revue trimestrielle

Une fois par trimestre (Janvier, Avril, Juillet, Octobre), vous recevez un email résumant les noms qui ont été ajoutés depuis la dernière revue. C'est l'occasion de :

- Vérifier qu'il n'y a pas de doublons
- Considérer s'il faut retirer des noms qui n'ont jamais été retrouvés en 12+ mois (un cron automatique le fait pour vous, mais vérifiez le résultat)

---

## 8bis. Gérer les listes de classe (« Promotions »)

Les listes de classe d'origine (6ème 1980-81 et 1981-82, 352 fiches) alimentent la page
**Promotions**, visible **uniquement par les membres connectés**. Contrairement à la liste
publique « Nous recherchons aussi » (§8), ces fiches portent le **nom complet** — d'où le
verrouillage derrière la connexion.

### Importer / ré-importer

Les fichiers sources et le CSV dérivé ne sont **jamais** versionnés (le dépôt GitHub est
public) : gardez-les dans `private-data/`, qui est ignoré par git.

```bash
# 1. (une seule fois) convertir les classeurs Excel en CSV
python scripts/convert_class_rosters.py

# 2. vérifier, puis importer
python manage.py import_class_roster private-data/class_rosters.csv --dry-run
python manage.py import_class_roster private-data/class_rosters.csv
```

La commande est **idempotente** : la relancer met à jour les fiches existantes sans jamais
créer de doublon. Pour l'exécuter sur la production, suivez la procédure de ciblage prod
décrite dans [`launch.md`](../runbooks/launch.md) (settings de prod + `DATABASE_PUBLIC_URL`).

### Corriger une fiche

`/admin/members/classrosterentry/` → filtre **« À vérifier »**. Ce filtre isole les
**36 fiches douteuses** : nom incomplet (un seul mot) ou personne listée deux fois dans les
classeurs d'origine. Corrigez le prénom / nom / surnom directement dans la fiche.

### Retirer quelqu'un (demande RGPD)

Une personne **non inscrite** qui demande à ne plus figurer sur ces listes :
supprimez simplement sa fiche dans `/admin/members/classrosterentry/`. C'est la voie RGPD
pour cette surface.

Une personne **inscrite** : la purge RGPD (§5) supprime automatiquement ses fiches de classe
en même temps que son compte — le résumé de purge les compte sous `roster_entries`.

### Lier une fiche à un membre à sa place

Un membre peut revendiquer sa propre fiche (bouton **« C'est moi »**), mais seulement si son
nom **correspond** à celui de la fiche. Une camarade dont le nom d'usage a changé (mariage)
sera donc bloquée : faites le lien vous-même depuis `/admin/members/classrosterentry/` en
renseignant le champ **Member**.

---

## 9. Surveillance et maintenance

Tâches récurrentes (cadence trimestrielle pour la plupart). Posez-vous des rappels calendrier.

### Sauvegardes médias

- Vérifiez régulièrement que la sauvegarde Cloudinary→Tigris fonctionne :
  ```bash
  railway bucket info --bucket media-backup --json
  ```
  La taille (`storageBytes`) doit augmenter doucement à mesure que de nouvelles photos sont ajoutées.
- Tableau de bord Railway → service `media-backup-cron` → onglet `Deploys` : la dernière exécution doit être un dimanche de moins de 8 jours, statut `SUCCESS`.

### Test de restauration (drill)

Tous les 90 jours, choisissez **une photo au hasard** et restaurez-la pour vérifier que la sauvegarde est utilisable. Procédure complète : `docs/runbooks/restore.md` §4.

### DMARC

Tous les 90 jours, consultez le tableau de bord du fournisseur DMARC (dmarcian ou similaire) pour vérifier que les emails partent correctement. Si le taux d'alignement légitime tombe sous 95 %, investiguez. Procédure complète : `docs/runbooks/dmarc.md` §2.

### Logs Railway

Pour examiner les logs en cas de comportement inattendu :

```bash
railway logs --service lesretrouvailles --lines 200
```

Filtrez sur erreurs : ajoutez `| grep -iE "error|traceback"`.

### Audit de readiness

À tout moment, pour avoir une vue synthétique des compteurs vs les minimums :

```bash
railway run --service lesretrouvailles python manage.py audit_launch_readiness
```

### Recherches sans résultat (signal pour le futur)

Depuis P8, deux actions `AuditLog` capturent les recherches qui n'ont rien trouvé :

- **`directory.query.no_results`** — un membre a fait une recherche dans `/annuaire/` qui n'a rien retourné, même après le repli par similarité (pg_trgm). Métadonnées : `q`, `year`, `city`, `profession`, `actor_username`.
- **`aide.query.no_results`** — un visiteur (anonyme ou connecté) a fait une recherche `?q=` dans `/aide/` qui n'a matché aucune entrée. Métadonnées : `q` tronqué à 80 caractères, `actor_username` (ou `"anonymous"`).

Filtrer ces actions dans `/admin/auditlog/` toutes les 4-6 semaines permet de voir ce que les membres cherchent sans le trouver. Si un même thème revient, c'est le signal pour ajouter une entrée FAQ (édition de `aide/faq.py` + PR — voir §12) ou pour enrichir les données de l'annuaire.

C'est aussi le journal qui informera la décision « faut-il un chatbot ? » plus tard. Décision déférée explicitement à `STATUS.md` § Phase 2 backlog : si après 60 jours d'usage les recherches sans résultat se concentrent sur des questions qu'une FAQ statique ne peut pas résoudre, on rouvre la spec d'un assistant IA. Sinon, le statu quo est suffisant.

---

## 10. Dépannage courant

### Un membre ne reçoit pas son email

1. Vérifiez l'orthographe de l'email saisi dans le `User`.
2. Demandez au membre de vérifier son dossier **spam**.
3. Si toujours rien : utilisez `reissue_login_link` pour générer un lien à partager via WhatsApp à la place.
4. Investigation plus poussée : consultez le tableau de bord Resend pour voir l'historique d'envoi (rejet, bounce, etc.).

### Un membre ne peut pas se connecter

> 💡 **Avant tout, pointez le membre vers [`/aide/`](https://villageretrouvailles.com/aide/)** — la FAQ couvre l'activation, le mot de passe oublié, et le format de l'identifiant. Beaucoup de cas se résolvent là sans intervention admin.

Si le membre persiste :

1. Vérifiez le **format de l'identifiant**. Le champ *Identifiant* sur la page de connexion accepte **trois** formes :
   - **Email** (membres ayant fourni un email à l'inscription) ;
   - **Numéro WhatsApp** en chiffres seulement, sans `+` ni espaces (ex. `22790000001`) ;
   - **Identifiant fourni par l'administrateur** (super-admin `bominomla`, comptes créés manuellement).
2. Vérifiez que le compte est actif : **Members → Members** → la ligne du membre → champ `Status` doit être `active`. Suspendre un membre depuis `/gestion/` désactive aussi son compte de connexion (`User.is_active=False`) et ferme ses sessions ouvertes : un statut `suspended` bloque donc réellement la connexion, et « Réactiver le compte » la rétablit.
3. Vérifiez l'`username` exact dans la fiche — un membre peut avoir oublié qu'il utilise son email plutôt que son numéro, ou vice versa.
4. Si vraiment oublié, générez un nouveau lien magique depuis `/gestion/` (voir §4) ou `reissue_login_link` en CLI.

### Erreur 500 sur une page admin

1. Notez **l'URL exacte** où l'erreur s'est produite.
2. Notez **l'heure** (utile pour grep les logs).
3. Récupérez les logs Railway autour de cette heure.
4. Si vous ne pouvez pas diagnostiquer, escaladez (contact technique ou Issue sur le repo Git).

### Une candidature de cooptation est bloquée

Une `AdminApplication` peut rester coincée en `cooptation_pending` si les deux parrains n'ont jamais répondu. Vérifiez :

1. **Cooptation → Admin Applications** filtrée par `status = cooptation_pending`.
2. **Cooptation → Cooptation requests** filtrée par cette application : voyez l'état des deux requêtes (pending / accepted / refused / expired).
3. Si les deux ont expiré sans réponse, le système envoie automatiquement un email de questionnaire au candidat (méthode 2 du master spec). Le statut devrait évoluer dans les 24 h après le passage du cron.
4. Si rien ne bouge, intervenez manuellement depuis `/admin/cooptation/adminapplication/` :
   - pour la faire remonter dans la file de revue, ouvrez la fiche et passez son champ **`Status`** à `awaiting_admin`, puis enregistrez ;
   - pour la refuser, sélectionnez-la dans la liste et lancez l'action **« Rejeter les candidatures sélectionnées »**.
   (Il n'existe pas d'action « Push to awaiting_admin » — les trois actions disponibles sont « Approuver… », « Rejeter… » et « Renvoyer le lien de mot de passe… ».)

---

## 11. En cas de problème majeur

### Restauration de la base de données

Railway prend des snapshots Postgres quotidiens (rétention 7 jours). En cas de corruption ou perte :

1. Tableau de bord Railway → service `Postgres` → onglet `Backups`.
2. Choisissez le snapshot avant l'incident.
3. Cliquez **Restore** → confirmez.
4. Railway provisionne une nouvelle base à partir du snapshot et met à jour `DATABASE_URL` automatiquement.

Procédure complète : `docs/runbooks/restore.md` §6.

### Restauration de médias

Si une photo a été supprimée par erreur de Cloudinary mais existe encore dans le bucket Tigris : utilisez la procédure de `docs/runbooks/restore.md` §3.

Pour récupérer une photo individuelle :

```bash
aws s3 cp "s3://media-backup-fissla9lsuj0/<public_id>" /tmp/photo.jpg \
    --endpoint-url https://t3.storageapi.dev
# Puis ré-uploadez vers Cloudinary avec cld uploader upload
```

### Service indisponible

Si la plateforme ne répond plus :

1. Tableau de bord Railway → service `lesretrouvailles` → vérifiez le statut de la dernière déploiement.
2. Si `FAILED` ou `CRASHED` : consultez les logs (build + runtime) pour la cause.
3. Solution rapide : **revert à la dernière déploiement réussie** depuis le tableau Deployments → `Redeploy` sur la précédente verte.

---

## 12. Pour aller plus loin

- **Runbooks opérationnels** : `docs/runbooks/` — détails techniques pour chaque domaine
  - `launch.md` — procédure complète de soft launch
  - `onboarding.md` — détails d'import des membres
  - `dmarc.md` — surveillance email
  - `restore.md` — sauvegardes médias + restauration BDD
  - `rgpd-purge.md` — suppression de comptes (RGPD)
  - `staging-deploy.md` — déploiement
- **Spécification produit** : `docs/superpowers/specs/2026-05-01-alumni-platform-design.md` — la vision et les contraintes du projet
- **STATUS.md** : `docs/superpowers/STATUS.md` — état actuel du projet, phases livrées

### Modifier la FAQ publique (`/aide/`)

La page `/aide/` est alimentée par une liste Python typée, **`aide/faq.py`**. Pour ajouter, retirer, ou modifier une question :

1. Ouvrez `aide/faq.py` dans une branche dédiée (ex. `docs/aide-update`).
2. Modifiez la liste `FAQ_ENTRIES`. Chaque entrée a `slug` (unique), `category` (parmi `CATEGORIES`), `question`, `answer_md` (markdown court), et `related_links` (liste de tuples `(label, url)`).
3. Lancez `pytest aide/` — les tests structurels (`test_faq_content.py`) attrapent une catégorie inconnue, un slug en double, ou un champ vide. Il y a aussi un test qui vérifie que toutes les URL internes des `related_links` se résolvent côté Django — un typo comme `/profil/edit/` (au lieu de `/profil/`) fait échouer la suite.
4. Soumettez une pull request. Pas d'interface admin pour cette page : c'est volontaire (zéro surface d'attaque, contrôle de version par git).

### Modifier le guide membre publique (`/guide/`)

La page `/guide/` rend le markdown canonique **`docs/guides/guide_membre.md`** (le même fichier que vous lisez ici, version membre). Pour mettre à jour :

1. Ouvrez `docs/guides/guide_membre.md` dans une branche dédiée.
2. Modifiez le contenu en markdown standard. La syntaxe acceptée : titres `##`/`###`, listes, gras/italique, blockquotes (`>`), code inline backtick, liens. Les balises `<script>` ou attributs `onclick=` sont strippés par bleach au rendu — défense-en-profondeur.
3. Lancez `pytest aide/tests/test_guide.py` — les tests structurels vérifient que le fichier est trouvé, qu'il a au moins 8 sections h2, et que les ancres du sommaire correspondent aux IDs du corps.
4. Soumettez une pull request. Le déploiement régénère le HTML rendu au prochain redémarrage Railway. Pas de cache à invalider.

> 💡 La page utilise l'extension `toc` du module markdown — chaque titre `##` ou `###` reçoit automatiquement un ID slug-ifié (ex. `## 5. Trouver vos camarades` → `id="5-trouver-vos-camarades"`). Vous pouvez partager des liens directs vers une section : `https://villageretrouvailles.com/guide/#5-trouver-vos-camarades`.

---

## Une dernière note

Cette plateforme est un **bien commun** de la communauté CEG 1 Birni. Votre rôle d'administrateur est avant tout un service rendu aux camarades. Restez patient, respectueux, et n'hésitez pas à demander conseil aux autres admins quand une situation est délicate (RGPD, In Memoriam, conflit entre membres).

Bonne administration, et longues retrouvailles à tous.
