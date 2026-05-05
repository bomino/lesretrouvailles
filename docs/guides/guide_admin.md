# Guide administrateur — Les Retrouvailles

Ce guide est destiné aux **Super Administrateurs** de la plateforme. Il complète les runbooks opérationnels (`docs/runbooks/`) en présentant le travail d'administration courante du point de vue d'un humain qui clique dans `/admin/`.

> 🔒 Ce guide contient des actions destructives (suppression de comptes, purge de données). Lisez chaque section avant d'agir, et préférez le **mode aperçu** ou **dry-run** quand il existe.

---

## 1. Votre rôle de Super Admin

Vous êtes responsable de :

- **Onboarder** les nouveaux membres (cooptation publique, import en masse, création manuelle)
- **Curer le contenu** : Mur des souvenirs, In Memoriam, liste publique « Nous recherchons aussi »
- **Modérer** : approuver les candidatures, gérer les demandes de retrait, traiter les demandes RGPD
- **Surveiller** : santé des sauvegardes, rapports DMARC, logs Railway
- **Soutenir** les membres : répondre aux questions par WhatsApp, renvoyer les liens magiques perdus, gérer les comptes oubliés

Tout passe par l'interface admin Django : **https://villageretrouvailles.com/admin/** (avec votre identifiant de super admin).

> 💡 Cette plateforme est conçue pour rester gérable par 2-3 administrateurs bénévoles. La plupart des opérations courantes prennent quelques minutes par semaine.

---

## 2. Accéder à l'interface admin

1. Allez à **https://villageretrouvailles.com/admin/**.
2. Connectez-vous avec votre nom d'utilisateur (par exemple `bominomla`) ou votre email + votre mot de passe.
3. Vous arrivez sur le tableau de bord Django Admin, organisé par sections :
   - **Members** — comptes des membres, candidatures de cooptation, journal d'audit, etc.
   - **Cooptation** — candidatures (`AdminApplication`), requêtes de parrainage, questions
   - **Memoires** — Mur des souvenirs (`Memory`)
   - **Memoriam** — fiches In Memoriam et nominations
   - **Authentication and Authorization** — utilisateurs Django, groupes, permissions

> 🔒 **Sécurité élémentaire :**
> - Ne partagez **jamais** votre mot de passe d'admin (ni par WhatsApp, ni par email).
> - Changez-le immédiatement si vous l'avez écrit dans une conversation.
> - Déconnectez-vous toujours après usage sur un appareil partagé.
> - Toute action destructive est tracée dans le journal d'audit (`Members → Audit log`).

---

## 3. Onboarder de nouveaux membres

Trois méthodes selon le contexte :

### 3a. Import en masse (recommandé pour le lancement)

C'est la méthode utilisée pour intégrer les ~200 membres du groupe WhatsApp existant. Tout est documenté dans :

- **Procédure complète** : `docs/runbooks/launch.md`, étapes 2 à 5
- **Format CSV + templates WhatsApp** : `docs/runbooks/onboarding.md`
- **Template CSV vide** : `docs/runbooks/roster_template.csv`

En résumé :

1. Préparez un fichier `roster.csv` avec une ligne par membre (colonnes : prénom, nom, surnom, WhatsApp, email optionnel, années, classes, ville, pays, profession, photo optionnelle).
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
4. Quand les deux parrains ont accepté (ou délais expirés), la candidature passe en **« Awaiting admin »**.
5. Vous voyez la candidature dans **Cooptation → Admin Applications** (filtre statut = `awaiting_admin`).

Pour approuver :

1. Cliquez sur la candidature.
2. Vérifiez les informations (nom, années, classes, ville, parrainages).
3. Dans la liste d'actions en haut : choisir **« Approve and create member »** → confirmer.
4. Le système crée automatiquement le `User` + `Member` + envoie l'email de définition de mot de passe.

Pour refuser :

1. Choisir l'action **« Reject application (with reason) »**.
2. Saisissez la raison (sera incluse dans l'email au candidat).
3. Confirmer.

> 💡 La candidature refusée est conservée 6 mois (rétention RGPD), puis purgée automatiquement.

### 3c. Création manuelle (cas exceptionnels)

Pour ajouter un membre directement sans passer par la cooptation (par exemple : un admin que vous voulez créer sans flux complet) :

1. Allez à **Authentication → Users → Add user**.
2. Saisissez **username** (en chiffres = numéro WhatsApp pour cohérence) et un mot de passe.
3. Sauvegardez. Vous arrivez sur le formulaire complet.
4. Cochez **« Active »**, **« Staff »** et/ou **« Superuser »** selon le besoin.
5. Renseignez l'email si applicable.
6. Sauvegardez.
7. Allez à **Members → Members → Add member**, lié à ce User.
8. Renseignez : nom, prénom, années, classes, ville, etc.
9. Sauvegardez.

> ⚠️ Cette méthode ne crée **pas** automatiquement la `EmailAddress` Allauth nécessaire pour la connexion par email. Préférez l'import en masse ou la cooptation publique chaque fois que possible.

---

## 4. Renvoyer un lien magique pour un membre sans email

C'est le cas le plus fréquent en régime de croisière (rappelez-vous : ~80 % de notre cohorte n'a pas d'email).

### Procédure

1. Le membre vous écrit sur WhatsApp : *« J'ai oublié mon mot de passe »* ou *« Le lien ne fonctionne plus »*.
2. Demandez-lui son **numéro WhatsApp** pour confirmer (en chiffres seulement, par exemple `22790000001`).
3. Depuis votre terminal connecté au projet Railway :
   ```bash
   railway run --service lesretrouvailles python manage.py reissue_login_link 22790000001
   ```
4. La commande imprime un nouveau lien magique.
5. **Copiez l'URL complète** et envoyez-la au membre via WhatsApp DM avec un message du type :
   ```
   Salut {Prénom},
   Voici ton nouveau lien (valable 7 jours) :
   {URL}
   Touche le lien depuis ton téléphone, choisis un mot de passe que tu retiendras.
   ```

### Cas particuliers

- **Le membre dit que le lien ne s'ouvre pas** → demandez-lui de le copier-coller dans son navigateur (Chrome / Safari) au lieu d'ouvrir directement depuis WhatsApp ; ça contourne d'éventuels problèmes de prévisualisation.
- **Le numéro WhatsApp donné ne trouve pas de compte** → vérifiez le format : la commande attend les chiffres seulement, sans `+` ni espace ni tiret. Listez les comptes existants depuis le shell admin si nécessaire.

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
   - Un champ texte où vous devez **saisir l'email exact** du membre pour confirmer.
6. Saisissez l'email puis cliquez **« Purger maintenant »**.
7. Vous êtes redirigé vers la liste avec un message de succès.
8. Une entrée `rgpd.member.purged` est ajoutée au journal d'audit (sans aucune donnée personnelle, juste un hash).

### Procédure (ligne de commande, alternative)

Pour traiter plusieurs demandes en lot ou via SSH :

```bash
# Aperçu sans changement
railway run --service lesretrouvailles python manage.py rgpd_purge_member alice@example.com --dry-run

# Exécution réelle
railway run --service lesretrouvailles python manage.py rgpd_purge_member alice@example.com
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

Le Mur des souvenirs est curé par les administrateurs (les membres ne peuvent pas uploader directement en Phase 1).

### Ajouter une photo

1. Allez à **Memoires → Memorys → Add memory**.
2. **Photo** : cliquez sur **Choisir un fichier**, sélectionnez une photo (JPG, PNG ou WebP).
3. **Légende** : décrivez la photo en quelques phrases (qui, quand, où, le contexte).
4. **Date approximative** (optionnel) : la date à laquelle la photo a été prise. Laissez vide si vous ne savez pas.
5. **Lieu** (optionnel) : Birni, Niamey, Paris, etc.
6. **Statut** :
   - `Brouillon` — visible uniquement par les admins (pour préparer en avance)
   - `Publiée` — visible par tous les membres
7. Cliquez **Save** (ou **Save and add another** si vous en avez plusieurs).

L'upload se fait directement vers Cloudinary ; la photo apparaît immédiatement dans la galerie.

### Modifier ou supprimer

- **Modifier** : cliquez sur la ligne, changez ce que vous voulez, sauvegardez.
- **Supprimer** : cochez, action **« Delete selected memorys »**. Cela supprime aussi la photo de Cloudinary (la prochaine sauvegarde médias ne re-créera pas la photo dans le bucket).

> 💡 Visez 10-20 photos seed à l'ouverture (objectif master spec). Pas besoin d'avoir un titre énorme — quelques photos bien légendées valent mieux qu'une grande galerie sans contexte.

---

## 7. Gérer les fiches In Memoriam

Les fiches In Memoriam honorent des camarades décédés. La procédure est **plus stricte** que pour le Mur des souvenirs : il faut un **accord explicite de la famille** avant publication (Annexe D du master spec, §D.5).

### Procédure complète

1. **Examiner les nominations** : allez à **Memoriam → In memoriam nominations**. Vous voyez les propositions soumises par les membres via le formulaire `/in-memoriam/nominer/`.
2. **Contacter la famille** (par téléphone, WhatsApp ou en personne — pas par email impersonnel) en utilisant l'indication de contact donnée par le membre proposant. Expliquez le projet, écoutez leurs souhaits, demandez leur accord pour la publication.
3. **Documenter l'accord** : nom de la personne qui a donné l'accord, date, canal (email / WhatsApp / téléphone / en personne).
4. **Créer la fiche** : allez à **Memoriam → In memoriam entries → Add**.
   - **Nom complet**, **surnom** (optionnel), **années au CEG**, **classes**
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
2. **Prénom** et **initiale du nom** (ex. « Mahamadou L. ») — données minimales pour ne pas exposer publiquement de PII.
3. **Années au CEG** (1980-1985, plusieurs années possibles).
4. **Note** (optionnelle) : une courte ligne d'introduction publique (ex. « Cherché par sa promotion 1983 »).
5. Sauvegardez. Vous êtes automatiquement enregistré comme cosignataire (un seul admin suffit pour publier en mode P4d).

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

---

## 10. Dépannage courant

### Un membre ne reçoit pas son email

1. Vérifiez l'orthographe de l'email saisi dans le `User`.
2. Demandez au membre de vérifier son dossier **spam**.
3. Si toujours rien : utilisez `reissue_login_link` pour générer un lien à partager via WhatsApp à la place.
4. Investigation plus poussée : consultez le tableau de bord Resend pour voir l'historique d'envoi (rejet, bounce, etc.).

### Un membre ne peut pas se connecter

1. Vérifiez le **format de l'identifiant** : email **OU** numéro WhatsApp en chiffres seulement (sans `+`, sans espace).
2. Vérifiez que le compte est actif : **Members → Members** → la ligne du membre → champ `Status` doit être `active`.
3. Si vraiment oublié : générez un nouveau lien magique avec `reissue_login_link`.

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
4. Si rien ne bouge, intervenez manuellement : action **« Push to awaiting_admin »** ou **« Reject application »**.

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

---

## Une dernière note

Cette plateforme est un **bien commun** de la communauté CEG 1 Birni. Votre rôle d'administrateur est avant tout un service rendu aux camarades. Restez patient, respectueux, et n'hésitez pas à demander conseil aux autres admins quand une situation est délicate (RGPD, In Memoriam, conflit entre membres).

Bonne administration, et longues retrouvailles à tous.
