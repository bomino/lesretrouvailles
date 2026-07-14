# Les Retrouvailles

> Plateforme privée des anciens du **CEG 1 Birni — Zinder, Niger** (promotions 1980-1985).
>
> Un espace pour reconstituer ce que la vie a dispersé : un annuaire, une mémoire collective, un In Memoriam, et un pont vers le groupe WhatsApp existant.

[![v1.2.1-member-guide](https://img.shields.io/badge/release-v1.2.1--member--guide-blue)](https://github.com/Bomino/lesretrouvailles/releases/tag/v1.2.1-member-guide)

---

## Statut

**v1.2.1-member-guide** — feature-complete, en production sur https://villageretrouvailles.com/. Au programme depuis le soft launch : console de gestion mobile-first pour les co-administrateurs (Gestion v1, `v1.1.0-gestion-console`), page d'aide publique avec recherche d'annuaire améliorée (P8, `v1.2.0-self-service-help`), page guide membre publique rendue en HTML stylisé depuis le markdown canonique (P8.1, `v1.2.1-member-guide`), et l'archive **Promotions** — les listes de classe 1980-82 (352 noms, 11 classes), réservées aux membres connectés, avec revendication de sa propre ligne. Une passe de durcissement pré-lancement a suivi : Django 5.2 LTS, coordonnées masquées par défaut, métadonnées EXIF supprimées à l'upload. Suite de tests : 954.

| Phase | Description | Statut |
|---|---|---|
| **P1** | Foundation (Django, Postgres, Tailwind, allauth) | ✅ |
| **P2** | Membership (modèle Member, profils, annuaire, Cloudinary) | ✅ |
| **P3** | Cooptation (signup public, parrainage, deadlines) | ✅ |
| **P4a-d** | Public surface (landing, ghost list, removal flow) | ✅ |
| **P5a** | Mur des souvenirs (galerie photos curée par admin) | ✅ |
| **P5b** | In Memoriam (fiches + nominations) | ✅ |
| **P6a** | Ops — sauvegarde médias (Cloudinary → bucket Railway) | ✅ |
| **P6b** | Ops — purge RGPD admin | ✅ |
| **P6c** | Ops — DMARC + rétention AuditLog | ✅ |
| **P7** | Soft launch (auth téléphone-ou-email, import en masse) | ✅ |
| **Gestion v1** | Console `/gestion/` pour co-administrateurs (annuaire, magic-links, cooptation) | ✅ |
| **P8** | Self-service help (page `/aide/` publique + annuaire multi-mots et tolérance aux fautes) | ✅ |
| **P8.1** | Guide membre en HTML (page `/guide/` publique avec sommaire interactif, rendu depuis `docs/guides/guide_membre.md`) | ✅ |

Suite (Phase 2 — backlog dans [`docs/superpowers/STATUS.md`](docs/superpowers/STATUS.md)) : mode sombre, galerie ouverte aux membres, carte géographique, In Memoriam ouvert, traduction Hausa, flow RGPD self-service.

---

## Stack technique

- **Backend** : Django 5.2 LTS, PostgreSQL, [django-allauth](https://django-allauth.readthedocs.io/) (auth + magic links)
- **Frontend** : Tailwind CSS + DaisyUI, [HTMX](https://htmx.org/), Playfair Display + Inter (Google Fonts), Vanilla JS (~10 lignes pour le hamburger mobile)
- **Médias** : Cloudinary (upload signé direct + transforms), bucket Railway/Tigris S3-compatible (sauvegarde hebdomadaire)
- **Email** : [Resend](https://resend.com/) avec SPF/DKIM/DMARC sur villageretrouvailles.com
- **Hébergement** : Railway (app, Postgres, cron services, bucket)
- **Tests** : pytest + pytest-django (suite complète verte ; `make test`)
- **Lint/format** : ruff (Python), djLint (templates Django), pre-commit hooks

---

## Démarrage rapide (développement local)

### Prérequis

- Python 3.12+
- Docker (pour Postgres en local)
- Node.js 20+ — **requis** pour builder le CSS. `static/css/output.css` est *généré*, pas versionné (`.gitignore`) : lancez `make css` après un clone, sinon le site s'affiche sans styles. Le Dockerfile et la CI le buildent automatiquement.

### Installation

```bash
# 1. Clone
git clone https://github.com/Bomino/lesretrouvailles.git
cd lesretrouvailles

# 2. Postgres en Docker
docker compose up -d db

# 3. Environnement Python
python -m venv .venv
.venv/Scripts/activate          # Windows : .venv\Scripts\activate
pip install -e ".[dev]"

# 4. Variables d'environnement
cp .env.example .env
# Éditer .env si besoin (les défauts marchent pour le dev local)

# 5. Migrations + super admin local
python manage.py migrate
python manage.py createsuperuser

# 6. Lancer le serveur
python manage.py runserver
# → http://localhost:8000/
```

### Tests

```bash
# Suite complète (~3 min)
pytest

# Un fichier spécifique
pytest members/tests/test_models_member.py -v

# Vérifier qu'aucune régression n'est introduite avant un PR
pytest && echo "OK"
```

### Build CSS (uniquement si on modifie les classes Tailwind)

```bash
npm install
npm run build        # one-shot
npm run watch        # mode dev avec recompilation auto
```

---

## Documentation

```
docs/
├── superpowers/
│   ├── STATUS.md                  ← état actuel du projet, phases livrées
│   ├── specs/                     ← intentions de design (WHAT)
│   └── plans/                     ← plans d'implémentation (HOW)
├── runbooks/                      ← procédures opérateur
│   ├── launch.md                  ← procédure complète de soft launch
│   ├── onboarding.md              ← format CSV + templates WhatsApp
│   ├── dmarc.md                   ← surveillance email
│   ├── restore.md                 ← sauvegardes médias + restauration BDD
│   ├── rgpd-purge.md              ← suppression de comptes (RGPD)
│   ├── staging-deploy.md          ← déploiement Railway
│   └── roster_template.csv        ← template CSV vide
├── guides/                        ← documentation utilisateur (français)
│   ├── guide_membre.md            ← pour les ~200 alumni
│   └── guide_admin.md             ← pour les Super Admins
└── archives/
    └── PRD_Alumni_CEG1_Birni_v1_2.md  ← cahier des charges initial
```

**Pour l'équipe technique :** commencer par `docs/superpowers/STATUS.md` (état actuel + index des phases) puis `CLAUDE.md` (conventions du projet).

**Pour les opérateurs (super admins) :** commencer par `docs/guides/guide_admin.md` puis les runbooks au besoin.

**Pour les membres :** `docs/guides/guide_membre.md`.

---

## Architecture des données

Modèles principaux (Postgres) :

- **`Member`** (members) — profil d'un ancien : prénom, nom, surnom, années au CEG (1980-1985), classes (6e, 6eA, 6a… ou aucune), ville, profession, photo Cloudinary, **numéro WhatsApp** (digits-only avec code pays, distinct du `User.username` qui sert d'identifiant de connexion ; voir `Member.whatsapp` ajouté en migration 0017/0018 — décorrelé du username pour que le partage wa.me fonctionne aussi pour les membres coopté·e·s ou les admins manuels).
- **`User`** (auth Django) — compte de connexion. Username = numéro WhatsApp digits-only ; email optionnel.
- **`AdminApplication`** (cooptation) — candidature soumise via `/inscription/`, en attente de cooptation par 2 parrains.
- **`CooptationRequest`** (cooptation) — une instance de parrainage demandé.
- **`Memory`** (memoires) — photo curée du Mur des souvenirs.
- **`InMemoriamEntry`** (memoriam) — fiche d'hommage à un·e ancien·ne décédé·e.
- **`InMemoriamNomination`** (memoriam) — proposition de nomination soumise par un membre.
- **`PublicSearchEntry`** (members) — entrée de la liste publique « Nous recherchons aussi… » (PII strict minimum).
- **`AuditLog`** (members) — journal d'audit append-only (rétention 12 mois).

Détails : voir `docs/superpowers/specs/2026-05-01-alumni-platform-design.md`.

---

## Conventions de contribution

- **Workflow** : spec (`docs/superpowers/specs/`) → plan (`docs/superpowers/plans/`) → branche `feat/X` ou `fix/X` → TDD → PR / merge `--no-ff`.
- **Tests** : tout nouveau code a au moins un test. La suite doit rester verte.
- **Langue** : tout le contenu utilisateur en français ; commentaires et identifiants en anglais.
- **Commits** : message à l'impératif, footer `Co-Authored-By:` pour Claude le cas échéant.
- **Hooks** : `ruff`, `ruff-format`, `djLint` — auto-fix au commit ; il faut juste re-stager si reformatages.

Voir `CLAUDE.md` pour les conventions détaillées (gotchas Cloudinary, Tigris, Windows shell, etc.).

---

## Production

- **URL** : https://villageretrouvailles.com/
- **Hébergement** : Railway (projet `Retrouvailles`)
  - Service `lesretrouvailles` : application Django + gunicorn
  - Service `Postgres` : base de données (snapshots quotidiens, rétention 7 jours)
  - Service `cooptation-cron` : daily cron (deadlines + retention)
  - Service `media-backup-cron` : weekly cron (Cloudinary → Tigris)
  - Bucket `media-backup` : sauvegarde médias (Tigris S3-compatible)
- **CDN médias** : Cloudinary (cloud `daa3utt2i`)
- **Email** : Resend, domaine `villageretrouvailles.com`
- **Domaine** : `villageretrouvailles.com` + `staging.villageretrouvailles.com`

Procédures opérationnelles dans `docs/runbooks/`.

---

## Crédits

- **Conception et chef de projet** : Bomino (B. Mahamadou Lawali)
- **Communauté** : alumni du CEG 1 Birni — Zinder, promotions 1980-1985
- **Développement** : itératif, en pair avec [Claude Code](https://claude.ai/code) (Anthropic Opus 4.7)
- **Infrastructure** : Railway, Cloudinary, Resend, Tigris

> Cette plateforme est un bien commun de la communauté CEG 1 Birni. Construite **pour** elle, **avec** elle.
