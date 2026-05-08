"""Curated FAQ for the public `/aide/` page.

Source-of-truth Python list — version-controlled, type-safe, no admin UI.
When the platform behavior or `docs/guides/guide_membre.md` changes,
update entries here in the same PR.

Each entry's `answer_md` is rendered through the existing markdown +
bleach pipeline already used elsewhere in the project. Keep answers
short (2-4 paragraphs) and link out to the relevant feature URL via
`related_links`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CATEGORIES = (
    "Compte",
    "Profil",
    "Confidentialité",
    "Annuaire",
    "Souvenirs",
    "In Memoriam",
    "Cooptation",
    "Dépannage",
)


@dataclass(frozen=True)
class FAQEntry:
    slug: str
    category: str
    question: str
    answer_md: str
    related_links: list[tuple[str, str]] = field(default_factory=list)


FAQ_ENTRIES: list[FAQEntry] = [
    # --- Compte ---
    FAQEntry(
        slug="activer-compte",
        category="Compte",
        question="Comment activer mon compte la première fois ?",
        answer_md=(
            "Vous avez reçu de l'administrateur **un lien d'activation**, soit par email "
            "(expéditeur *Les Retrouvailles*), soit par message WhatsApp privé. Touchez ou "
            "cliquez ce lien pour ouvrir la page de création de mot de passe, choisissez un "
            "mot de passe (au moins 8 caractères, avec des chiffres), confirmez — et vous êtes "
            "connecté·e.\n\n"
            "Le lien est valable **7 jours**. Passé ce délai, contactez l'administrateur via "
            "WhatsApp pour en recevoir un nouveau. Pensez à vérifier votre dossier spam si "
            "vous attendez un email."
        ),
        related_links=[
            ("Page de connexion", "/accounts/login/"),
            ("Guide complet — Activation", "/static/docs/guide_membre.md"),
        ],
    ),
    FAQEntry(
        slug="se-connecter",
        category="Compte",
        question="Comment me connecter au quotidien ?",
        answer_md=(
            "Allez sur la **page de connexion**. Le champ d'identification accepte deux "
            "formes :\n\n"
            "- 📧 **Votre email** (si vous en avez un) ;\n"
            "- 📱 **Votre numéro WhatsApp** en chiffres uniquement, sans le `+` et sans "
            "espaces (ex. `22790000001`).\n\n"
            "Le mot de passe est celui que vous avez choisi à l'activation."
        ),
        related_links=[("Se connecter", "/accounts/login/")],
    ),
    FAQEntry(
        slug="mot-de-passe-oublie",
        category="Compte",
        question="J'ai oublié mon mot de passe — que faire ?",
        answer_md=(
            "**Si vous avez un email** : sur la page de connexion, cliquez sur *« Mot de passe "
            "oublié ? »*. Vous recevrez un email pour le réinitialiser.\n\n"
            "**Si vous n'avez pas d'email** : envoyez un message WhatsApp à l'administrateur en "
            "demandant un nouveau lien. Il vous répondra avec un nouveau lien magique en "
            "quelques minutes."
        ),
        related_links=[("Mot de passe oublié", "/accounts/password/reset/")],
    ),
    FAQEntry(
        slug="changer-mot-de-passe",
        category="Compte",
        question="Comment changer mon mot de passe ?",
        answer_md=(
            "Connectez-vous, puis allez à **Mon profil → Changer mon mot de passe** (ou "
            "directement à `/accounts/password/change/`). Saisissez votre ancien mot de passe "
            "puis le nouveau (deux fois pour confirmer).\n\n"
            "Choisissez un mot de passe difficile à deviner — au moins 8 caractères avec des "
            "chiffres — et ne le partagez avec personne."
        ),
        related_links=[("Changer mon mot de passe", "/accounts/password/change/")],
    ),
    FAQEntry(
        slug="supprimer-compte",
        category="Compte",
        question="Comment supprimer mon compte (RGPD) ?",
        answer_md=(
            "Vous pouvez à tout moment demander la **suppression complète** de votre compte. "
            "C'est votre droit au titre du RGPD (article 17).\n\n"
            "**Procédure** : envoyez un email ou un message WhatsApp à l'administrateur en "
            "demandant explicitement la suppression de votre compte. Mentionnez votre nom "
            "complet et votre email (ou numéro WhatsApp) pour faciliter l'identification. "
            "L'administrateur procède à la suppression dans un délai maximum de **30 jours** "
            "(généralement quelques heures), et vous recevez une confirmation.\n\n"
            "**Attention** : la suppression est **irréversible**. Une fois terminée, il "
            "faudra refaire toute la procédure de cooptation pour revenir."
        ),
        related_links=[("Charte de la communauté", "/charte/")],
    ),
    # --- Profil ---
    FAQEntry(
        slug="photo-profil",
        category="Profil",
        question="Comment ajouter ou modifier ma photo de profil ?",
        answer_md=(
            "Connectez-vous et allez à **Mon profil** (votre prénom dans la barre de "
            "navigation, ou via le menu hamburger ☰ sur mobile). Cliquez sur *« Modifier »* "
            "sur la photo (ou l'avatar avec vos initiales), puis *« Choisir une photo »* et "
            "sélectionnez un fichier de votre téléphone ou ordinateur.\n\n"
            "Formats acceptés : **JPG, PNG, WebP**. Taille maximale : **5 Mo**. La photo est "
            "automatiquement recadrée et publiée. Choisissez une photo nette de votre visage — "
            "elle apparaîtra dans l'annuaire et sur votre profil."
        ),
        related_links=[("Mon profil", "/profil/")],
    ),
    FAQEntry(
        slug="modifier-infos",
        category="Profil",
        question="Comment modifier ma ville, ma profession, ou mon surnom ?",
        answer_md=(
            "Connectez-vous, allez à **Mon profil**, puis cliquez sur *« Modifier »*. Vous "
            "pouvez changer à tout moment :\n\n"
            "- Surnom (votre surnom du quartier ou de l'école)\n"
            "- Ville actuelle et pays\n"
            "- Profession (libre, en quelques mots)\n"
            "- Photo\n\n"
            "Les modifications sont enregistrées immédiatement."
        ),
        related_links=[("Modifier mon profil", "/profil/edit/")],
    ),
    FAQEntry(
        slug="champs-verrouilles",
        category="Profil",
        question="Pourquoi mon nom et mes années au CEG sont-ils verrouillés ?",
        answer_md=(
            "Votre **nom**, vos **années au CEG (1980-1985)** et vos **classes** font partie "
            "de votre identité d'ancien — ils sont fixés à l'inscription pour éviter les "
            "modifications accidentelles qui pourraient casser les recherches dans l'annuaire.\n\n"
            "Les **classes** sont facultatives — beaucoup d'anciens ne se souviennent plus des "
            "sections, et c'est normal de laisser le champ vide. Pour les corriger ou les "
            "ajouter plus tard, contactez l'administrateur via WhatsApp."
        ),
        related_links=[("Mon profil", "/profil/")],
    ),
    # --- Confidentialité ---
    FAQEntry(
        slug="confidentialite",
        category="Confidentialité",
        question="Qui voit mon email et mon numéro WhatsApp ?",
        answer_md=(
            "Vous décidez. Dans **Mon profil → Modifier**, trois cases contrôlent ce qui est "
            "visible dans l'annuaire et sur votre profil public :\n\n"
            "- **Afficher mon email** — *décoché* par défaut ;\n"
            "- **Afficher mon numéro WhatsApp** — *décoché* par défaut ;\n"
            "- **Afficher ma ville** — *coché* par défaut.\n\n"
            "Si une case est décochée, l'information n'apparaît pas dans l'annuaire ni sur "
            "votre profil public — seuls les administrateurs y ont accès. Quand "
            "*Afficher mon numéro WhatsApp* est coché, votre numéro apparaît sous la forme "
            "`+227...` avec un lien cliquable qui ouvre WhatsApp."
        ),
        related_links=[
            ("Modifier mon profil", "/profil/edit/"),
            ("Charte de la communauté", "/charte/"),
        ],
    ),
    # --- Annuaire ---
    FAQEntry(
        slug="chercher-camarade",
        category="Annuaire",
        question="Comment chercher un·e camarade dans l'annuaire ?",
        answer_md=(
            "Cliquez sur **Annuaire** dans le menu et tapez un nom (ou un morceau de nom) "
            "dans la barre de recherche. La recherche est :\n\n"
            "- **insensible aux accents** — taper « malam » trouvera aussi « Mâlâm » ;\n"
            "- **multi-mots** — tapez `1983 niamey` pour trouver les camarades de la "
            "promotion 1983 qui sont à Niamey ;\n"
            "- **tolérante aux fautes de frappe** — si « Naimey » ne trouve rien d'évident, "
            "le système propose les meilleurs candidats par similarité.\n\n"
            "Les résultats se mettent à jour automatiquement."
        ),
        related_links=[("Aller à l'annuaire", "/annuaire/")],
    ),
    FAQEntry(
        slug="filtres-annuaire",
        category="Annuaire",
        question="Comment filtrer par promotion, ville, ou profession ?",
        answer_md=(
            "Sur la page **Annuaire**, à côté de la barre de recherche, vous avez trois "
            "filtres :\n\n"
            "- **Année** — pour ne voir que les camarades de votre promotion ;\n"
            "- **Ville** — utile si vous cherchez quelqu'un dans la même ville que vous ;\n"
            "- **Profession**.\n\n"
            "Vous pouvez combiner les filtres avec la recherche libre. Par exemple : "
            "filtrer *Année = 1983* puis taper « médecin » dans la recherche."
        ),
        related_links=[("Aller à l'annuaire", "/annuaire/")],
    ),
    # --- Souvenirs ---
    FAQEntry(
        slug="proposer-photo",
        category="Souvenirs",
        question="Comment proposer une photo historique pour le Mur des souvenirs ?",
        answer_md=(
            "Le **Mur des souvenirs** est curé par les administrateurs — vous ne pouvez pas "
            "publier directement. Si vous avez une photo historique du CEG 1 Birni à "
            "partager, **envoyez-la à l'administrateur via WhatsApp**, en précisant si "
            "possible :\n\n"
            "- l'année approximative ;\n"
            "- le contexte (sortie de classe, fête, etc.) ;\n"
            "- les noms des personnes que vous reconnaissez.\n\n"
            "Elle pourra être ajoutée au Mur après vérification."
        ),
        related_links=[("Voir le Mur des souvenirs", "/souvenirs/")],
    ),
    # --- In Memoriam ---
    FAQEntry(
        slug="nomination-memoriam",
        category="In Memoriam",
        question="Comment proposer une nomination In Memoriam ?",
        answer_md=(
            "Allez à la page **In Memoriam 🕊️** dans le menu, puis cliquez sur "
            "*« Nominer un·e ancien·ne »*. Renseignez le nom, les années au CEG, un souvenir "
            "personnel, et un point de contact pour la famille (si possible).\n\n"
            "Un administrateur examinera votre nomination et engagera la procédure d'accord "
            "familial avant de créer la fiche officielle. Cela peut prendre plusieurs "
            "semaines.\n\n"
            "**Important** : la plateforme ne publie *jamais* une fiche In Memoriam sans "
            "l'accord écrit de la famille proche. C'est une question de respect et de "
            "protection de la mémoire."
        ),
        related_links=[("Aller à In Memoriam", "/memoriam/")],
    ),
    # --- Cooptation ---
    FAQEntry(
        slug="parrainage-recu",
        category="Cooptation",
        question="On me demande de parrainer un·e candidat·e — que dois-je faire ?",
        answer_md=(
            "Quand un·e candidat·e cite votre email comme parrain, vous recevez un message "
            "*« [Les Retrouvailles] {Nom} sollicite votre parrainage »*. Pour répondre :\n\n"
            "1. Connectez-vous à la plateforme.\n"
            "2. Allez dans **Cooptations à valider** dans le menu (un badge avec le nombre "
            "de demandes en attente s'affiche).\n"
            "3. Cliquez sur la demande pour voir les informations du candidat.\n"
            "4. Vérifiez : est-ce bien un·e ancien·ne du CEG 1 Birni ? Connaissez-vous ses "
            "années / sa famille ?\n"
            "5. Cliquez sur *« Accorder le parrainage »* ou *« Refuser »* (avec un mot "
            "d'explication facultatif)."
        ),
        related_links=[("Cooptations à valider", "/cooptations-a-valider/")],
    ),
    FAQEntry(
        slug="delai-parrainage",
        category="Cooptation",
        question="Combien de temps ai-je pour répondre à une demande de parrainage ?",
        answer_md=(
            "Vous avez **14 jours** pour répondre. Au-delà, la candidature suit un processus "
            "alternatif (questionnaire automatique).\n\n"
            "Vous pouvez recevoir un **rappel par email à J+7** si vous n'avez pas encore "
            "répondu."
        ),
        related_links=[("Cooptations à valider", "/cooptations-a-valider/")],
    ),
    # --- Dépannage ---
    FAQEntry(
        slug="email-non-recu",
        category="Dépannage",
        question="Je n'ai pas reçu mon email d'activation",
        answer_md=(
            "1. Vérifiez votre dossier **spam / courrier indésirable**.\n"
            "2. Vérifiez que l'email saisi à l'inscription est correct (pas de faute de "
            "frappe).\n"
            "3. Si toujours rien après 24 heures, contactez l'administrateur via "
            "WhatsApp — il pourra vous renvoyer un nouveau lien d'activation, "
            "soit par email, soit directement par WhatsApp."
        ),
        related_links=[],
    ),
    FAQEntry(
        slug="photo-bloque",
        category="Dépannage",
        question="Ma photo de profil ne se charge pas",
        answer_md=(
            "Vérifiez :\n\n"
            "- **Format** : JPG, PNG ou WebP. Pas de HEIC/HEIF d'iPhone — convertissez "
            "d'abord en JPG via une application photo standard.\n"
            "- **Taille** : moins de **5 Mo**. Si votre photo dépasse, réduisez-la dans "
            "l'application photo de votre téléphone (option *« Réduire »* ou *« Compresser »*).\n"
            "- **Connexion internet** : assurez-vous d'avoir un signal stable pendant l'envoi.\n\n"
            "Si le problème persiste, contactez l'administrateur via WhatsApp en précisant "
            "le modèle de votre téléphone."
        ),
        related_links=[("Mon profil", "/profil/")],
    ),
    FAQEntry(
        slug="signaler-bug",
        category="Dépannage",
        question="Comment signaler un bug ou poser une question ?",
        answer_md=(
            "Envoyez un message WhatsApp à l'administrateur avec :\n\n"
            "- Une **description** de ce que vous faisiez quand le problème est survenu ;\n"
            "- Une **capture d'écran** si possible ;\n"
            "- Le **modèle de votre téléphone** (Android ? iPhone ? Quel modèle / version ?).\n\n"
            "L'administrateur est à votre disposition. C'est une plateforme construite **pour** "
            "la communauté et **avec** la communauté — vos retours nous aident à l'améliorer."
        ),
        related_links=[],
    ),
]
