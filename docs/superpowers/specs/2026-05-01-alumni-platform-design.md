# PLATEFORME ALUMNI

## CEG 1 BIRNI — ZINDER

*Promotions 1980 – 1985*

**Product Requirements Document (PRD)**

Version 1.3 — Mai 2026

*CONFIDENTIEL — Usage interne*

Statut : **Validé v1.3** | Langue : **Français**

---

## Historique des versions

| Version | Date | Auteur | Changements |
|---------|------|--------|-------------|
| 1.0 | Mai 2026 | BMLa | Version initiale |
| 1.1 | Mai 2026 | BMLa | Révisions mineures |
| 1.2 | Mai 2026 | BMLa + Claude | Correction toponyme (Birni = quartier historique de Zinder ; retrait des références à "N'Konni"). Réécriture §2.3 (éligibilité). MVP recentré : ajout Mur des souvenirs admin et page In Memoriam ; carte géographique repoussée en Phase 2. Nouveau §6.5 (flow Fantôme + landing publique). §8 enrichi (NFR data Niger, accessibilité 55-65 ans, RPO/RTO, sauvegarde médias). Nouveau §9.4 (politique de suppression RGPD). §10 ajusté (timeline 12-16 semaines). Stack mise à jour (DRF retiré du MVP, Railway plan gratuit retiré, ajout Backblaze B2 + GitHub Actions). Nouvelle Annexe D (procédure In Memoriam). Nouvelle Annexe E (liste des notifications). |
| 1.3 | 2026-05-01 | BMLa + Claude | **P1 résolus.** Liste publique "Nous recherchons aussi…" : validation collégiale obligatoire, opt-out sans authentification, défunts exclus. Cooptation : deadline parrains (J+7 relance, J+14 expiration) avec fallback automatique vers admin direct ou questionnaire. Alignement §8.2/§9.4 : purge RGPD effective dans la fenêtre de rétention 30j, procédure ciblée pour purger les sauvegardes B2 versionnées. **P2 résolus.** Rétention `AdminApplication` : 6 mois après rejet, puis purge. Email deliverability : SPF/DKIM/DMARC obligatoires sur le domaine. §7.3 HTTPS : formulation agnostique du fournisseur. §8.4 compatibilité : Android 7+ (élargi pour la cohorte). **P3 légers.** §8.4 i18n : architecture Django gettext prête à activer Hausa en Phase 4. §10 staging : URL d'avant-prod pour validation admin avant ouverture WhatsApp. KPI baseline calibrée à confirmer avec taille réelle du groupe WA. |

---

## Table des Matières

1. Résumé Exécutif
2. Contexte & Problématique
3. Vision & Objectifs
4. Utilisateurs & Personas
5. Périmètre — User Stories
6. Spécifications Fonctionnelles
7. Architecture Technique
8. Exigences Non Fonctionnelles
9. Gouvernance & Modération
10. Roadmap & Phases
11. Métriques de Succès
12. Risques & Atténuations
13. Annexes

---

# 1. Résumé Exécutif

La plateforme Alumni CEG 1 Birni est un espace numérique permanent destiné aux anciens élèves du Collège d'Enseignement Général N°1 du quartier historique **Birni** de la ville de **Zinder**, ayant fréquenté l'établissement entre 1980 et 1985. Elle constitue une extension structurée et durable du groupe WhatsApp existant, créé le 1er Septembre 2020, qui réunit déjà cette communauté.

**Problème :** WhatsApp ne permet pas la structuration des membres, ni la préservation de la mémoire collective de la promotion.

**Solution :** Une plateforme web à visibilité **mixte** — vitrine publique indexée pour retrouver les "Fantômes" + espace membre privé non indexé contenant l'annuaire, les profils, le mur des souvenirs et les pages In Memoriam.

**Public cible :** Exclusivement les anciens élèves du CEG 1 Birni (Zinder), promotions 1980–1985 (monde entier).

**MVP prioritaire :** Annuaire structuré et profils, validation par cooptation avec deadlines, Mur des souvenirs admin (10-20 photos seed), page In Memoriam (1-3 fiches préparées), et landing publique pour retrouver les Fantômes. La carte géographique est repoussée en Phase 2 pour prioriser le contenu émotionnel au lancement.

**Stack technique :** Django 5.x · PostgreSQL · HTMX · Tailwind CSS · DaisyUI · Cloudinary · Backblaze B2 (sauvegarde médias) · GitHub Actions (cron sauvegarde) · Hetzner ou Railway · Resend (avec SPF/DKIM/DMARC sur le domaine).

---

# 2. Contexte & Problématique

## 2.1 Contexte

Le groupe WhatsApp "Alumni CEG 1 Birni" a été créé le 1er Septembre 2020 et rassemble des anciens élèves dispersés à travers le Niger et le monde. En quatre ans d'existence, le groupe a permis de renouer des liens perdus et de maintenir une cohésion communautaire précieuse. Cependant, les limites structurelles de WhatsApp comme outil de gestion communautaire deviennent de plus en plus apparentes.

## 2.2 Problèmes Identifiés

| Priorité | Problème | Impact |
|----------|----------|--------|
| **P1 — Critique** | Pas d'annuaire structuré | Impossible de trouver un camarade par ville, profession, ou promotion. Le groupe WhatsApp est une liste opaque de numéros. |
| **P1 — Critique** | Absence de mémoire collective | Les photos partagées disparaissent des téléphones. Les histoires, anecdotes et événements ne sont archivés nulle part. La mémoire de la promotion est fragile. |
| **P2 — Important** | Bruit et perte d'information | Les messages importants (annonces, coordonnées) sont noyés dans le flux quotidien du groupe WhatsApp. |
| **P2 — Important** | Difficultés d'organisation | Organiser des événements ou des cotisations via WhatsApp est laborieux, sans suivi ni transparence. |

## 2.3 Périmètre d'Éligibilité

Pour être membre de la plateforme, une personne doit avoir été inscrite au CEG 1 Birni (Zinder) pendant au moins une année scolaire entre 1980 et 1985 (inclus), que cette période ait été ou non sanctionnée par un BEPC.

*La vérification de l'éligibilité est assurée par un processus de validation décrit en section 9.*

---

# 3. Vision & Objectifs

## 3.1 Vision

> *"Créer une maison digitale permanente pour une génération qui a partagé des années décisives — afin que leur histoire soit préservée, que leurs liens perdurent, et que leur réseau soit une force collective."*

## 3.2 Objectifs Stratégiques

| # | Objectif | Indicateur clé | Cible à 12 mois |
|---|----------|----------------|------------------|
| **O1** | Constituer un annuaire numérique de tous les membres éligibles | % des membres WhatsApp inscrits sur la plateforme | ≥ 70 % |
| **O2** | Préserver la mémoire collective de la promotion | Nombre de photos et témoignages archivés | ≥ 500 photos |
| **O3** | Retrouver les membres "fantômes" absents de WhatsApp | Nombre de nouveaux membres identifiés via la plateforme | ≥ 30 membres |
| **O4** | Assurer la pérennité numérique de la communauté | Disponibilité de la plateforme | ≥ 99 % |

---

# 4. Utilisateurs & Personas

La plateforme est exclusivement destinée aux anciens du CEG 1 Birni (1980–1985). Trois personas représentatifs ont été identifiés.

### Persona 1 — L'Actif (Idrissa, 56 ans, Niamey)

Participe activement au groupe WhatsApp depuis 2020. À l'aise avec la technologie, il utilise un smartphone Android. Il veut un endroit structuré pour retrouver ses camarades par ville ou profession, et contribuer à l'archivage des photos.

- **Besoin principal :** Trouver un camarade par ville ou spécialité professionnelle
- **Frustration :** *"Je cherche un collègue médecin parmi nous — impossible dans WhatsApp"*
- **Contexte :** Connexion 4G mobile, utilise son téléphone pour tout

### Persona 2 — Le Fantôme (Hamidou, 58 ans, Paris)

Connu de plusieurs membres du groupe mais jamais retrouvé. N'a pas de numéro nigérien actif. A entendu parler du groupe WhatsApp mais ne peut pas le rejoindre directement. La plateforme web lui permet d'exister et d'être retrouvé.

- **Besoin principal :** Être retrouvable et rejoindre la communauté à son rythme
- **Frustration :** *"J'ai perdu contact depuis les années 90 — je ne sais pas comment vous rejoindre"*
- **Contexte :** Accès internet haut débit, PC et mobile

### Persona 3 — L'Administrateur (Moussa, 57 ans, Zinder)

Co-fondateur du groupe WhatsApp. Connaît la majorité des membres. Valide les inscriptions, modère le groupe, et coordonne les événements. Il a besoin d'outils de gestion des membres et d'une vision d'ensemble de la communauté.

- **Besoin principal :** Gérer les inscriptions et avoir une vue d'ensemble des membres
- **Frustration :** *"Gérer 80+ membres sur WhatsApp sans liste, sans profils, c'est ingérable"*
- **Contexte :** Mixte mobile/desktop, technicité intermédiaire

---

# 5. Périmètre & User Stories

## 5.1 MVP — Phase 1 : Annuaire, Profils & Teaser Mémoire

| ID | En tant que… | Je veux… | Critère d'acceptation |
|----|--------------|----------|------------------------|
| **US-01** | Visiteur éligible | Soumettre une demande d'inscription avec mes informations (nom, années CEG 1, ville actuelle, profession) et nommer 2 parrains | Formulaire soumis, message de confirmation reçu, admin notifié, parrains contactés sous 1h |
| **US-02** | Administrateur | Valider ou rejeter une demande d'inscription avec commentaire | Statut mis à jour, candidat notifié par email |
| **US-03** | Membre authentifié | Consulter l'annuaire des membres avec filtres (nom, ville, promotion, profession) | Résultats pertinents affichés en < 2 secondes |
| **US-04** | Membre authentifié | Voir le profil complet d'un camarade (photo, coordonnées visibles, parcours) | Profil affiché, contacts visibles uniquement aux membres connectés |
| **US-05** | Membre authentifié | Modifier mon propre profil (photo, ville, profession, contact) | Modifications sauvegardées et visibles immédiatement |
| **US-06** | Visiteur public | Découvrir la plateforme via une page d'accueil indexable et signaler que je suis un ancien | Landing publique SEO, CTA fonctionnel, formulaire d'inscription accessible |
| **US-07** | Membre authentifié | Accéder en un clic au groupe WhatsApp depuis la plateforme | Lien WhatsApp fonctionnel, visible sur la page d'accueil |
| **US-08** | Membre authentifié | Consulter un Mur des souvenirs avec photos historiques curées par les admins | Galerie 10-20 photos seed, vue détaillée, légendes |
| **US-09** | Membre authentifié | Consulter une page In Memoriam avec 1-3 fiches préparées | Page accessible, fiches affichées avec photo + texte hommage |
| **US-09b** | Personne listée publiquement comme "recherchée" | Demander mon retrait sans créer de compte | Lien sur la page publique, formulaire 1-clic, retrait admin sous 48h |

> *Note : la carte géographique a été repoussée en Phase 2 (US-15) pour prioriser le contenu émotionnel au lancement. Le filtre "ville" de l'annuaire (US-03) couvre 80 % du besoin de proximité géographique.*

## 5.2 Phase 2 : Mémoire Collective Étendue

| ID | En tant que… | Je veux… |
|----|--------------|----------|
| **US-10** | Membre authentifié | Uploader des photos de l'époque avec tags (personnes, année, lieu) |
| **US-11** | Membre authentifié | Publier un souvenir écrit ("Je me souviens de…") avec réactions des autres membres |
| **US-12** | Administrateur | Créer une fiche In Memoriam pour honorer un camarade décédé (selon procédure Annexe D) |
| **US-13** | Membre authentifié | Consulter les profils des anciens professeurs du CEG 1 |
| **US-14** | Membre authentifié | Demander le retrait d'un tag photo me concernant |
| **US-15** | Membre authentifié | Voir une carte géographique montrant où sont dispersés les camarades |

## 5.3 Phase 3 : Vie Communautaire

| ID | En tant que… | Je veux… |
|----|--------------|----------|
| **US-16** | Administrateur | Créer et publier un événement (réunion, retrouvailles) avec formulaire d'inscription |
| **US-17** | Administrateur | Gérer une caisse commune : enregistrer les cotisations et afficher un bilan transparent |
| **US-18** | Membre authentifié | Publier une actualité personnelle (promotion, distinction, publication) sur un fil commun |

---

# 6. Spécifications Fonctionnelles — MVP

## 6.1 Système d'Inscription & Validation

Le processus d'inscription est le point de contrôle le plus critique de la plateforme. Il garantit l'authenticité de la communauté.

### Formulaire d'Inscription

**Champs obligatoires :**

- Nom complet (nom de famille + prénom)
- Surnom ou sobriquet (facultatif mais fortement encouragé)
- Années passées au CEG 1 Birni (ex : 1981–1984)
- Classe(s) fréquentée(s) (ex : 6ème B, 5ème A, 4ème C)
- Ville et pays de résidence actuelle
- Profession / secteur d'activité
- Adresse email (pour la connexion et les notifications)
- Numéro WhatsApp (optionnel — pour lien direct)
- Photo de profil (optionnelle — photo actuelle ou d'époque)
- **Nom et email de 2 parrains** parmi les membres existants

### Processus de Validation

**Méthode retenue : Validation manuelle par cooptation, avec deadlines.**

1. Le candidat soumet le formulaire et nomme jusqu'à 2 parrains parmi les membres existants (par nom et email).
2. L'administrateur reçoit une notification.
3. Les parrains nommés reçoivent une demande de cooptation par email avec un lien sécurisé à expiration.
4. Chaque parrain accorde ou refuse, avec un commentaire optionnel.
5. **Deadlines :**
   - **J+7** : relance automatique aux parrains qui n'ont pas répondu.
   - **J+14** : la cooptation expire. Le candidat est notifié et bascule automatiquement sur **méthode 2 (vérification admin directe)** si l'admin connaît le candidat, sinon **méthode 3 (questionnaire de connaissance)**.
6. L'administrateur prend la décision finale après cooptation (2 accords requis, sauf vérification admin directe ou questionnaire validé).
7. Le candidat reçoit un email de confirmation avec ses identifiants.

> *Pas de blocage indéfini : aucune candidature ne peut rester en attente plus de 21 jours sans décision finale (validation, rejet, ou demande de complément).*

## 6.2 Profil Membre

Chaque membre dispose d'un profil structuré, visible uniquement aux membres authentifiés.

| Section | Champs | Visibilité |
|---------|--------|------------|
| **Identité** | Nom, surnom, photo | Membres connectés uniquement |
| **Parcours scolaire** | Années CEG 1, classes, profs mémorables | Membres connectés uniquement |
| **Localisation** | Ville, pays | Membres connectés uniquement |
| **Profession** | Métier, secteur, employeur (optionnel) | Membres connectés uniquement |
| **Contact** | Email, WhatsApp, LinkedIn (optionnel) | Contrôlé par le membre (peut masquer) |

## 6.3 Annuaire & Recherche

- Recherche textuelle : nom, prénom, surnom
- Filtres combinables : année de scolarité, ville/pays, profession/secteur
- Tri : alphabétique, par date d'inscription, par proximité géographique (quand applicable)
- Vue liste et vue grille (cartes de profil)
- **Pagination 20 profils par page (pas de scroll infini — économie de data)**

## 6.4 Mur des Souvenirs (admin-only en Phase 1)

Galerie statique de 10 à 20 photos historiques curées par les administrateurs, prête au lancement. **Aucun upload utilisateur en Phase 1** : les admins postent eux-mêmes les photos seed.

- Vue grille avec lazy loading et thumbnails ≤ 50 KB
- Vue détaillée avec légende (date, lieu, personnes identifiées si accord)
- Composant technique réutilisé tel quel pour la galerie ouverte de Phase 2 (mais sans upload, modération, ni gestion de tags)

Sert de teaser émotionnel pour le lancement et de proof-of-concept visuel pour la galerie complète.

## 6.5 Flow de Découverte des Fantômes & Landing Publique

La plateforme expose une **unique surface publique** indexée par les moteurs de recherche : la page d'accueil. Toutes les autres pages (annuaire, profils, mur des souvenirs, In Memoriam) restent strictement réservées aux membres authentifiés et marquées `noindex` au niveau du template.

### Page d'accueil publique — composants

- **Récit court** (200-300 mots) présentant l'histoire de la promotion 1980-1985 et de la communauté.
- **Section "Nous recherchons aussi…"** listant les noms / surnoms / années des anciens élèves activement recherchés par la communauté (mais pas encore inscrits). Voir gouvernance ci-dessous.
- **CTA principal** "Je suis un ancien" → formulaire d'inscription.
- **Lien d'invitation partageable** WhatsApp avec tracking UTM (`utm_source=whatsapp&utm_campaign=invitation`) pour mesurer quel canal ramène le plus de Fantômes.
- **Mots-clés SEO ciblés :** "CEG 1 Birni Zinder", "promotion 1980 1985 Zinder", "anciens CEG Birni".

### Gouvernance de la liste publique "Nous recherchons aussi…"

Exposer publiquement le nom + année d'absents non-consentants est éthiquement et juridiquement sensible (RGPD pour la diaspora EU, réputation pour les concernés). Donc :

- **Validation collégiale obligatoire** : aucun nom n'est ajouté sans accord explicite de **2 Super Admins minimum**, documenté dans `AuditLog`.
- **Données exposées strictement minimales** : prénom + initiale du nom de famille + année(s) CEG. Pas de profession, pas de ville, pas de photo.
- **Lien "Retirer mon nom" visible sur la page publique**, **sans authentification requise**. Formulaire avec confirmation par email à l'adresse fournie. Retrait admin sous 48h, sans débat.
- **Aucun défunt** dans cette liste : la mémoire des défunts relève exclusivement de l'Annexe D (procédure In Memoriam).
- **Revue trimestrielle** par les Super Admins : toute personne listée depuis plus de 12 mois sans contact entrant est retirée par défaut (la liste n'est pas un cimetière numérique).

### Mécanisme de retrouvailles

Un proche d'un Fantôme (enfant, conjoint, collègue) cherche son nom sur Google et tombe sur la liste publique des recherchés. Il transmet le lien. Le Fantôme s'inscrit.

### Tension à résoudre dans le code

§7.3 prescrit que l'annuaire et les profils ne soient **jamais indexés**. La page d'accueil et la liste des recherchés **doivent** l'être. Différenciation explicite par middleware Django ou par template, **pas par un `robots.txt` global** qui bloquerait tout.

---

# 7. Architecture Technique

## 7.1 Stack Recommandé

| Couche | Technologie | Justification |
|--------|-------------|---------------|
| **Backend** | Django 5.x | Expertise existante, robuste, sécurisé par défaut, excellent admin. *DRF retiré de la stack MVP — non nécessaire avec frontend HTMX. Réintroduit en Phase 4 si app mobile/PWA.* |
| **Frontend** | HTMX + Tailwind CSS + DaisyUI | Léger, pas de JS complexe, idéal pour connexions 3G mobiles. DaisyUI fournit des composants UI (cards, badges, avatars, tables) sans framework React. |
| **Base de données** | PostgreSQL | Fiable, performant pour les recherches et les requêtes complexes |
| **Stockage médias** | Cloudinary | CDN global, optimisation automatique des images (`f_auto,q_auto:eco`), plan gratuit 25 GB |
| **Sauvegarde médias** | Backblaze B2 | Stockage froid versionné, ~$0,005/GB/mois, indépendant de Cloudinary |
| **Cron sauvegarde** | GitHub Actions (`schedule`) | Zéro infra, gratuit pour repos publics ou 2000 min/mois en privé. Aucun Celery ou worker à maintenir. |
| **Hébergement** | Hetzner CX22 (~€4,50/mois) ou Railway Hobby (~$5/mois) | Hetzner pour contrôle total, Railway pour simplicité. *Plan gratuit Railway supprimé.* |
| **Emails** | Resend + DNS records SPF/DKIM/DMARC sur le domaine | API simple, plan gratuit 3 000 emails/mois, intégration Django en 5 lignes. **DNS records obligatoires pour la deliverability** (sans SPF/DKIM, les cooptations finissent en spam). |
| **Carte (Phase 2)** | Leaflet.js + OpenStreetMap | Open source, gratuit, léger, fonctionne bien sur mobile |

## 7.2 Modèle de Données Principal

**Entités MVP (Phase 1) :**

- `Member` : id, user (FK), full_name, nickname, years_attended, classes, city, country, profession, photo_url, contact_prefs, status, created_at
- `AdminApplication` : id, full_name, nickname, years_attended, classes, city, country, profession, email, whatsapp, status, reviewed_by, review_note, submitted_at, **rejected_at, retention_until** *(champs explicites, pas de blob JSON ; rétention de 6 mois après rejet, puis purge)*
- `CooptationRequest` : id, application (FK), parrain (FK Member), response, responded_at, **expires_at** *(J+14 par défaut)*
- `PublicSearchEntry` : id, first_name, last_name_initial, years_at_ceg, added_by_admins (M2M), added_at, removal_token, removed_at
- `AuditLog` : id, actor (FK), action, target_type, target_id, metadata (JSON), created_at
- `NotificationPreference` : id, member (FK), digest_weekly, in_memoriam_alerts, event_alerts, tag_alerts
- `ConsentRecord` : id, member (FK), charter_version, accepted_at, ip_address
- `Memory` *(seed photos admin Phase 1, étendu Phase 2)* : id, author (FK), type, content, tags, status, created_at
- `InMemoriamEntry` *(seed Phase 1, ouvert Phase 2)* : id, deceased_data, tribute, family_consent_record, family_contact_canal, created_by, status, created_at

**Entités Phase 2 :**

- `PhotoTag` : id, memory (FK), tagged_member (FK), accepted [pending/accepted/removed]
- `Teacher` : id, name, subject, years, tribute_text, photo_url

## 7.3 Sécurité & Accès

- **Authentification :** Django Allauth (email + mot de passe)
- **Autorisation :** 3 rôles — Admin, Modérateur, Membre
- **Indexation différenciée :** la page d'accueil et la liste publique des recherchés sont indexables ; toutes les autres pages (annuaire, profils, mémoire, In Memoriam) sont marquées `noindex` au niveau du template, **pas via `robots.txt` global**
- Toutes les routes de l'annuaire requièrent une session authentifiée (middleware Django)
- **HTTPS obligatoire** via Let's Encrypt ou certificat managé du fournisseur (Hetzner avec Caddy/Nginx, Railway avec certificat auto-managé)
- **Deliverability email :** SPF, DKIM et DMARC configurés sur le domaine d'envoi avant le premier email transactionnel. DMARC en `p=quarantine` minimum. Surveillance DMARC reports trimestrielle.
- Rate limiting sur le formulaire d'inscription et sur le formulaire public "Retirer mon nom" (protection anti-spam et anti-énumération)

---

# 8. Exigences Non Fonctionnelles

## 8.1 Performance & Coût Data Mobile

Conçue pour des connexions 3G nigériennes et des forfaits data limités.

| Exigence | Cible |
|----------|-------|
| Temps de chargement page initiale | < 3 s sur 3G mobile |
| Poids hors images, par page | ≤ 200 KB |
| Thumbnails par défaut | ≤ 50 KB, format WebP/AVIF via `f_auto,q_auto:eco` Cloudinary |
| Chargement de l'image originale | Sur clic uniquement, jamais en preload |
| Lazy loading | `loading="lazy"` sur toute image hors viewport initial |
| Mode "Économie de données" | Toggle dans les préférences profil. Désactive les images, remplace les avatars par placeholders colorés avec initiales. |
| Cache navigateur sur assets statiques | 1 an, avec hash dans le nom de fichier |
| Pagination annuaire | 20 profils par page. **Pas de scroll infini** (consomme la data inutilement quand on cherche un nom précis) |

## 8.2 Disponibilité & Sauvegardes

| Catégorie | Cible |
|-----------|-------|
| Uptime | ≥ 99 % (~7 h downtime/mois acceptables, hors panne fournisseur amont) |
| Sauvegarde base de données | Quotidienne, rétention 30 jours, RPO ≤ 24 h, RTO ≤ 24 h |
| Sauvegarde médias (séparée) | **Hebdomadaire vers Backblaze B2, déclenchée par GitHub Actions `schedule`.** Volume cible : 1,5-3 GB. Coût ~$0,10/mois. Rétention 30 jours alignée avec la fenêtre RGPD. |
| Test de restauration | Trimestriel : 1 photo aléatoire restaurée et comparée par hash. Documenté dans `runbooks/restore.md`. |
| Plan de bascule médias | Si Cloudinary inaccessible, DNS bascule vers une instance Django + WhiteNoise servant la copie B2. Mode dégradé acceptable. |
| **Purge ciblée RGPD** | Une demande de suppression utilisateur (§9.4) déclenche une purge ciblée des sauvegardes B2 versionnées dans la fenêtre des 30 jours. Procédure scriptée (`scripts/purge_user_from_backups.py`) appelée par l'admin avec confirmation. |

### Workflow GitHub Actions — sauvegarde médias

```yaml
name: backup-cloudinary-to-b2
on:
  schedule:
    - cron: '0 3 * * 0'  # dimanche 03:00 UTC
  workflow_dispatch:      # déclenchement manuel possible
jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install cloudinary b2sdk
      - name: Backup Cloudinary → B2
        env:
          CLOUDINARY_URL: ${{ secrets.CLOUDINARY_URL }}
          B2_KEY_ID: ${{ secrets.B2_KEY_ID }}
          B2_APP_KEY: ${{ secrets.B2_APP_KEY }}
          B2_BUCKET: ${{ secrets.B2_BUCKET }}
        run: python scripts/backup_media.py
```

Le script `backup_media.py` parcourt les `public_id` Cloudinary connus de la base de données (export Django commandé en amont), télécharge chaque original, et le push vers le bucket B2 versionné. Détection de duplication par hash pour éviter de re-uploader les fichiers inchangés.

## 8.3 Accessibilité (membres 55-65 ans)

| Exigence | Cible |
|----------|-------|
| Police de base | ≥ 16 px |
| Contraste | WCAG 2.1 AA minimum |
| Cibles tactiles | ≥ 44 × 44 px, espacement ≥ 8 px entre cibles |
| Boutons | Libellé texte ET icône (jamais icône seule) |
| Wizards multi-étapes | Aucun. Tout sur une seule page, ou avec sauvegarde brouillon. |
| Hover-only interactions | Interdit. Toute action doit être tap/clic. |
| Toasts auto-disparaissants | Interdits pour confirmations importantes. Rester jusqu'à clic explicite. |
| Préservation de saisie | Le contenu d'un formulaire est toujours préservé en cas d'erreur. |
| Navigation principale | Visible sur desktop. Hamburger autorisé sur mobile uniquement. |
| Zoom navigateur | Fonctionnel jusqu'à 200 % sans casse de mise en page. |
| ARIA | Étiquettes sur la carte (Phase 2), composants interactifs, et formulaires. |

## 8.4 Autres Exigences

| Catégorie | Exigence |
|-----------|----------|
| **Langue** | Français principal. UTF-8 partout pour tolérer Hausa et Zarma dans les contenus utilisateur. |
| **i18n extensibilité** | Architecture Django `gettext` activée dès le MVP (toutes les chaînes UI dans des fichiers `.po`). Pas de Hausa en V1, mais ajout en Phase 4 sans réfacto. |
| **Vie privée** | Données personnelles jamais exposées publiquement, jamais vendues, accès limité aux membres. |
| **Scalabilité** | Architecture prévue pour 500+ membres sans dégradation. |
| **Compatibilité navigateurs** | **Android 7+** (cohorte 55-65 ans, certains téléphones plus anciens), iOS 13+, Chrome/Firefox/Safari (versions des 2 dernières années). |

---

# 9. Gouvernance & Modération

## 9.1 Rôles & Responsabilités

| Rôle | Qui | Permissions |
|------|-----|-------------|
| **Super Admin** | Fondateurs du groupe WhatsApp (2–3 personnes) | Accès complet : validation des inscriptions, gestion des rôles, suppression de compte, configuration de la plateforme, création des fiches In Memoriam (selon Annexe D), validation collégiale de la liste publique "Nous recherchons aussi…" |
| **Modérateur** | Membres de confiance désignés par les Admins | Valider les inscriptions, modérer les contenus (Phase 2), signaler les abus |
| **Membre** | Tout ancien validé du CEG 1 Birni (1980–1985) | Consulter l'annuaire, modifier son profil, accéder aux fonctionnalités de sa phase |

## 9.2 Politique de Modération

- Toute inscription doit être approuvée manuellement avant activation.
- Un membre peut signaler un profil incorrect à l'administrateur.
- Un membre peut demander la suppression de son profil à tout moment (voir §9.4).
- Les administrateurs peuvent désactiver un compte en cas d'abus, avec notification.
- Les décisions d'exclusion sont prises collégialement par les Super Admins.

## 9.3 Authentification des Membres — Méthodes

**Méthode 1 — Cooptation :** Deux membres existants confirment l'identité du candidat via un lien de validation envoyé par email. Le candidat nomme ses parrains au moment du formulaire. Deadlines : relance J+7, expiration J+14.

**Méthode 2 — Vérification admin directe :** L'administrateur connaît personnellement le candidat ou peut le vérifier via le groupe WhatsApp. Court-circuite la cooptation. Utilisée également en fallback automatique quand la méthode 1 expire.

**Méthode 3 — Questionnaire de connaissance :** Le candidat répond à des questions sur le CEG 1 Birni que seuls les anciens peuvent connaître (noms de professeurs, salles de classe, événements). Utilisée en complément si la cooptation est ambigüe ou en fallback automatique quand la méthode 1 expire et que l'admin ne connaît pas personnellement le candidat.

**Aucun candidat ne reste en attente plus de 21 jours** : à J+21, l'admin doit avoir tranché (validation, rejet, ou demande de complément).

## 9.4 Politique de Suppression de Compte (RGPD-compliant)

Tout membre peut demander la suppression de son compte à tout moment. La suppression est effectuée sous **30 jours** (délai RGPD). Le membre choisit, au moment de la demande, le traitement appliqué à ses contributions :

| Donnée | Action à la suppression |
|--------|-------------------------|
| Compte (login, email, mot de passe) | Suppression dure |
| Profil (nom, ville, profession, contacts) | Suppression dure |
| Photo de profil | Suppression dure (Cloudinary + sauvegarde B2 via purge ciblée §8.2) |
| Photos uploadées en galerie | Choix : (a) suppression dure, ou (b) conservation avec auteur anonymisé "Ancien membre" |
| Tags photo posés sur le membre par d'autres | Tags retirés, photos elles-mêmes conservées |
| Témoignages écrits | Choix : suppression ou anonymisation |
| Commentaires & réactions | Anonymisés (pour préserver l'intégrité des fils) |
| Mention dans un In Memoriam d'autrui | Conservée si publique, retirée si privée |
| Logs d'audit | Conservés 12 mois pour sécurité/légal puis purgés |
| Sauvegardes (BD + médias) | Purge effective dans la fenêtre de rétention 30 jours. Pour les sauvegardes B2 versionnées, lancer `scripts/purge_user_from_backups.py` pour purge ciblée immédiate. |
| Candidature `AdminApplication` (si rejetée) | 6 mois de rétention puis purge automatique. Le candidat peut redéposer après ce délai. |

Confirmation par email avec récapitulatif détaillé de ce qui a été supprimé / anonymisé / conservé. Le choix du membre sur les photos collectives est **important** : forcer la suppression dure peut détruire des photos où d'autres apparaissent.

---

# 10. Roadmap & Phases

**Hypothèse de charge :** développement principal solo en temps partiel (~10-15 h/semaine). Les durées indiquées sont des fourchettes réalistes incluant les imprévus. Les estimations initiales (6-8 semaines pour le MVP) ont été ajustées à la hausse après revue v1.2 — un MVP solo en temps partiel s'allonge typiquement de 50 à 100 % par rapport à une estimation optimiste.

| Phase | Durée | Fonctionnalités | Critère de passage |
|-------|-------|-----------------|--------------------|
| **Phase 1 — MVP** | **12-16 semaines** | Inscription / cooptation avec deadlines / validation, profils membres, annuaire + filtres, lien WhatsApp, **Mur des souvenirs admin (10-20 photos seed), Page In Memoriam (1-3 fiches), Landing publique Fantômes (SEO) avec liste recherchés gouvernée, formulaire public de retrait** | ≥ 50 membres inscrits, ≥ 70 % profils complets, ≥ 5 Fantômes retrouvés |
| **Phase 2 — Mémoire étendue** | 6-8 semaines | Galerie photos avec tags + droit à l'image, Mur des mémoires écrites, profils des professeurs, In Memoriam ouvert (procédure Annexe D), **carte géographique** | ≥ 100 photos uploadées par les membres |
| **Phase 3 — Communauté** | 6-8 semaines | Gestion d'événements, caisse commune & cotisations, fil d'actualités | Premier événement organisé via la plateforme |
| **Phase 4 — Évolutions** | À définir | Application mobile (PWA), notifications push, messagerie directe, module mentoring, **activation Hausa via gettext** | Défini en fonction des retours après Phase 3 |

### Environnements

- **Production** : `alumni-ceg1-birni.org` (ou nom à arbitrer). Visible par la communauté.
- **Staging** : `staging.alumni-ceg1-birni.org`, accès basic-auth restreint aux Super Admins. Toute nouvelle release passe d'abord par staging pour validation des 2-3 admins, puis migration vers prod **avant** annonce dans le groupe WhatsApp.
- **Développement** : local Docker Compose (Postgres + Django + asset watcher).

### Jalons Phase 1

- **S1-S4 :** modèle de données + auth + admin Django + DNS records SPF/DKIM/DMARC + setup staging
- **S5-S8 :** annuaire + profils + recherche
- **S9-S12 :** cooptation avec deadlines + landing publique + SEO + formulaire de retrait public
- **S13-S14 :** Mur des souvenirs admin + page In Memoriam (contenu seed préparé en parallèle hors code)
- **S15-S16 :** tests, contenu seed, soft launch staging avec 5-10 membres pilotes avant ouverture WhatsApp

---

# 11. Métriques de Succès

## 11.1 KPIs Phase 1 (MVP)

> *Note de calibration : les cibles 12 mois supposent un groupe WhatsApp de ~80 membres actifs. À recalibrer dès la connaissance du chiffre exact (groupe estimé à 80-200 membres au moment du PRD).*

| Métrique | Baseline | Cible 3 mois | Cible 12 mois |
|----------|----------|--------------|----------------|
| Membres inscrits et validés | 0 | 30 | ~64 (≈ 80 % du groupe WA estimé à 80 membres) |
| Taux de complétion des profils | — | 60 % | 80 % |
| Membres "fantômes" retrouvés | 0 | 10 | 30 |
| Visites mensuelles de la landing publique | 0 | 200 | 500 |
| Visites mensuelles de l'annuaire (membres connectés) | 0 | 100 | 400 |
| Demandes de retrait via le formulaire public | — | ≤ 2 | ≤ 5 |

---

# 12. Risques & Atténuations

| Risque | Probabilité | Atténuation |
|--------|-------------|-------------|
| Faible adoption initiale (résistance au changement) | Moyen | Impliquer les fondateurs WA dès le début. Lancement officiel lors d'un événement. Démonstration guidée. **Le Mur des souvenirs et l'In Memoriam au lancement compensent l'aspect "annuaire sec".** |
| Difficulté à vérifier l'éligibilité des membres | Moyen | Cooptation à 2 parrains avec deadlines. Questionnaire de connaissance interne. Validation admin en dernier recours. |
| Faux profils / usurpation d'identité | Faible | Validation manuelle obligatoire. Signalement libre. Procédure de suspension rapide. |
| Coût d'hébergement non maîtrisé | Faible | Démarrage Hetzner CX22 (~€4,50/mois) ou Railway Hobby (~$5/mois) — **plan gratuit Railway n'existe plus**. Budget prévisionnel ~75-90 $/an la première année. Caisse commune Phase 3 prend le relais. |
| Pérennité du projet si l'Admin principal se retire | Moyen | Succession à 3 Super Admins minimum. Documentation technique. Code source sur dépôt partagé. |
| Accès limité (connexion lente au Niger) | Élevé | Architecture HTMX + DaisyUI légère, mode économie de données, thumbnails 50 KB, lazy loading agressif. Voir §8.1. |
| Disparition de Cloudinary / changement de pricing | Faible-Moyen | **Sauvegarde hebdomadaire des médias vers Backblaze B2 via GitHub Actions. Test de restauration trimestriel. Plan de bascule documenté.** |
| Conflit éthique sur fiche In Memoriam | Moyen | **Procédure Annexe D : pas de publication sans accord famille. Retrait sous 48 h sur demande, sans débat.** |
| Plainte RGPD d'un membre EU | Faible | **Politique de suppression §9.4. Consent records. DPO désigné parmi Super Admins. Charte explicite. Purge ciblée des sauvegardes.** |
| Plainte d'une personne listée dans "Nous recherchons aussi…" | Faible-Moyen | **§6.5 gouvernance : validation collégiale, données minimales, lien retrait sans authentification, retrait sous 48h, revue trimestrielle. Aucun défunt sur cette liste.** |
| Cooptation bloquée (parrains non-réactifs) | Moyen | **Deadlines J+7 / J+14 avec fallback automatique vers méthode 2 ou 3. Aucune candidature en attente > 21 jours.** |
| Emails transactionnels en spam | Moyen-Élevé | **SPF/DKIM/DMARC obligatoires sur le domaine avant le premier envoi. Surveillance trimestrielle des rapports DMARC.** |

---

# 13. Annexes

## Annexe A — Charte de la Communauté (Proposition)

La plateforme Alumni CEG 1 Birni est régie par les principes suivants :

- Respect mutuel et bienveillance entre tous les membres
- Confidentialité des informations partagées sur la plateforme
- Authenticité : tout membre s'engage sur l'honneur à être bien un ancien du CEG 1 Birni
- La plateforme est un espace apolitique et non commercial
- Toute utilisation des données des membres à des fins personnelles ou commerciales est strictement interdite

## Annexe B — Glossaire

| Terme | Définition |
|-------|------------|
| **CEG 1 Birni** | Collège d'Enseignement Général N°1 situé dans le quartier historique **Birni** de la ville de **Zinder**, Niger. Le quartier Birni est le cœur ancien de Zinder, autour du palais du Sultan et de la Grande Mosquée. **À ne pas confondre avec la ville de Birni N'Konni** (région de Tahoua), géographiquement distincte. |
| **Birni** | Quartier historique de Zinder, Niger. Centre traditionnel et culturel de la ville. |
| **MVP** | Minimum Viable Product — version minimale fonctionnelle pour le lancement |
| **PRD** | Product Requirements Document — document de spécification produit |
| **Alumni** | Anciens élèves d'un établissement scolaire |
| **Membre "fantôme"** | Ancien élève connu de la communauté mais non présent sur le groupe WhatsApp |
| **Cooptation** | Processus par lequel deux membres existants confirment et valident l'identité d'un nouveau candidat |
| **RPO / RTO** | Recovery Point Objective (perte de données acceptable) / Recovery Time Objective (durée de restauration acceptable) |
| **RGPD** | Règlement Général sur la Protection des Données (applicable aux membres résidant dans l'UE) |
| **SPF / DKIM / DMARC** | Records DNS qui authentifient l'expéditeur d'un email pour éviter le filtrage en spam. |

## Annexe C — Références

- Groupe WhatsApp Alumni CEG 1 Birni — Créé le 1er Septembre 2020
- Session de brainstorming PRD — Mai 2026
- Django Documentation — https://docs.djangoproject.com
- Django i18n / gettext — https://docs.djangoproject.com/en/5.0/topics/i18n/
- HTMX — https://htmx.org
- Leaflet.js — https://leafletjs.com
- Cloudinary — https://cloudinary.com
- DaisyUI — https://daisyui.com
- Resend — https://resend.com
- Railway — https://railway.app
- Hetzner Cloud — https://www.hetzner.com/cloud
- Backblaze B2 — https://www.backblaze.com/cloud-storage
- GitHub Actions (`schedule` trigger) — https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
- DMARC.org — https://dmarc.org

## Annexe D — Procédure In Memoriam

La création d'une fiche In Memoriam est une démarche éthiquement sensible. Cette procédure est **obligatoire avant toute publication**.

### D.1 Initiation

Seul un Super Admin peut initier une fiche In Memoriam. **Aucun membre ordinaire ne peut créer une fiche.**

### D.2 Avant publication

1. Le Super Admin identifie un proche de la personne décédée (enfant, conjoint, frère/sœur, ami proche).
2. Contact écrit (email ou WhatsApp) au proche, présentant le contenu prévu : texte d'hommage, photos sélectionnées, témoignages collectés.
3. Demande d'accord explicite. Délai de réponse 14 jours.

### D.3 Validation

- **Pas de publication sans accord explicite et écrit** du proche identifié.
- Si aucun proche n'est identifiable ou joignable, la fiche reste en brouillon et n'est jamais publiée. La mémoire orale du groupe WhatsApp suffit dans ce cas.
- L'accord obtenu est documenté dans la fiche : qui a donné l'accord, quand, par quel canal. Visible uniquement en zone admin.

### D.4 Retrait après publication

Si la famille demande le retrait d'une fiche déjà publiée, le retrait est effectué **sous 48 heures, sans débat ni négociation**. Les témoignages individuels publiés par d'autres membres dans la fiche sont, au choix de la famille :

- archivés et retirés de la vue publique,
- ou anonymisés et conservés.

### D.5 Documentation administrative

Chaque fiche In Memoriam stocke en zone admin :

- l'identité du proche ayant donné l'accord,
- la date de l'accord,
- le canal de communication utilisé,
- la version du contenu approuvé,
- l'historique des modifications post-publication.

## Annexe E — Liste des Notifications

Liste exhaustive des notifications email à implémenter, par phase. **Recommandation :** digest hebdomadaire pour les notifications communautaires (pas un email par action — la fatigue notification mène à la désinscription, particulièrement chez les 55-65 ans).

### E.1 Phase 1 — Candidat

- Soumission de demande reçue
- Demande de cooptation envoyée à tes parrains
- Cooptation accordée par parrain
- Cooptation refusée par parrain
- **Cooptation expirée à J+14, bascule vers méthode admin/questionnaire** (nouveau v1.3)
- Profil approuvé + identifiants de connexion
- Profil rejeté + motif
- Réinitialisation de mot de passe

### E.2 Phase 1 — Admin

- Nouvelle demande d'inscription en attente
- **Cooptation à relancer (J+7) ou expirée (J+14)** (nouveau v1.3)
- **Demande de retrait de la liste publique "Nous recherchons aussi…"** (nouveau v1.3)
- Profil signalé par un membre

### E.3 Phase 1 — Communauté

- Cooptation demandée pour toi (parrain)
- **Relance cooptation à J+7** (nouveau v1.3)
- Digest hebdomadaire "nouveaux dans ta promotion" *(opt-in)*

### E.4 Phase 2

- In Memoriam publié *(digest hebdomadaire, opt-in)*
- Tu as été tagué·e dans une photo (avec lien retrait direct)
- Réaction sur ton souvenir écrit

### E.5 Phase 3

- Nouvel événement publié
- Rappel J-7 / J-1 pour événement auquel tu es inscrit·e
- Cotisation reçue (confirmation)
- Bilan caisse mensuel

**Total : ~20 templates** à versionner (`template_id`, version, `locale`). Le modèle `NotificationPreference` permet à chaque membre de désactiver les digests et les alertes non-essentielles.

---

*Plateforme Alumni CEG 1 Birni — PRD v1.3 — Confidentiel*
