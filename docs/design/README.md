# Design DressMe

Référence visuelle commune de l'application : un prototype cliquable (fait avec Figma Make) et sa
traduction en Flutter. Chaque BO s'en sert pour que tous les écrans aient le même style.

```
docs/design/
├── README.md        ce guide
└── prototype/       prototype React + Tailwind (5 écrans, données fictives)

mobile/lib/core/design/
└── dressme_design.dart   couleurs, rayons, textes, thème Flutter et 2 widgets communs
```

## 1. Voir le prototype

Il faut Node.js (18 ou plus).

```bash
cd docs/design/prototype
npm install        # une seule fois
npm run dev        # puis ouvrir http://localhost:5173
```

Les photos (Unsplash) et les chiffres sont fictifs : le prototype montre **l'apparence et les
interactions**, pas les données. Dans l'application, les données viennent des modules (M1…M18).
Le fichier `vite.config.ts` a été simplifié : les plugins propres à Figma Make ne marchent pas en dehors
de Figma et ont été retirés.

## 2. Quel écran pour quel BO

| Écran du prototype | Fichier | Partie | BO / module |
|---|---|---|---|
| Today | `HomeScreen.tsx` | Tenue du jour, météo, occasion, Remix, « Pourquoi cette tenue ? » | BO2 (M2) |
| | | Sélection locale (cartes boutique · ville · prix · %) | BO6 (M7) |
| | | Photo d'une pièce → tenues | M1 |
| Garde-robe | `WardrobeScreen.tsx` | Grille, catégories, fiche pièce, porté × fois | BO3 (M1, M3) |
| | | Capsule, désencombrer, score durable | BO3 (M16, M17) |
| | | « Ce qui manque à ta garde-robe » | BO5 / M7 |
| Studio | `RecommendationsScreen.tsx` | Board à compléter par l'IA, avatar | BO1 (M2), BO9 (M9) |
| Assistant | `AssistantScreen.tsx` | Chat, cartes de réponse, mémoire | BO8 (M8, orchestrateur) |
| Profil → Mon style | `ProfileScreen.tsx` | Curseurs de style, empreinte, insights | BO4 (M5, M12) |
| Profil → Smart Buy | | Verdict d'achat, score, anti-doublon | BO5 (M6) |
| Profil → Local | | Marques tunisiennes, filtre ville, % style | BO6 (M7) |
| Profil → Plus | | Valise de voyage, communauté, stats | M11, BO7 (M10) |

## 3. Les règles du style

**Ambiance** : beige clair, encre presque noire, accent doré ; titres en serif, texte en sans-serif ;
grandes zones sombres en haut des écrans ; cartes blanches arrondies avec une fine bordure.

### Couleurs

| Rôle | Hex | Flutter (`DmColors.`) | Exemple dans le prototype |
|---|---|---|---|
| Encre (fonds sombres, boutons principaux, chip choisie) | `#211D19` | `ink` | En-têtes, « Je la porte » |
| Encre profonde | `#171512` | `inkDeep` | Haut de Today, fond du Studio |
| Texte principal | `#1A1714` | `text` | |
| Fond d'écran | `#F6F3EE` | `page` | |
| Fond de l'application | `#FAF9F7` | `canvas` | |
| Cartes | `#FFFFFF` | `surface` | |
| Sable (chips, petits blocs) | `#F4F0EA` / `#F0E8DD` | `sand` / `sandDark` | Pièces d'une tenue, badges |
| Or (accent) | `#C9A77B` | `gold` | « Remix », chip active sur fond sombre |
| Or clair (texte sur fond sombre) | `#E3C9A7` | `goldLight` | « Matières légères » |
| Bronze (petits titres) | `#9A744B` | `bronze` | « SÉLECTION LOCALE » |
| Lien | `#8D6842` | `bronzeDark` | « Ouvrir Studio » |
| Barres de progression, puces | `#B78C5B` | `bar` | Score Smart Buy |
| Bordures | `#E5DED4` / `#DED5C9` | `border` / `borderStrong` | |
| Texte secondaire | `#81776D` / `#675F57` | `muted` / `mutedDark` | Boutique · ville |
| Succès | `#EAF5EE` / `#4C9366` / `#214C31` | `successBg` / `success` / `successDark` | Verdict « Recommandé » |
| Attention | `#FFF6E9` / `#9A6733` | `warningBg` / `warning` | Anti-doublon |
| Durable | `#EFF7F1` / `#5E9671` | `ecoBg` / `eco` | Score durable |

### Typographie

| Usage | Police | Taille | Flutter (`DmText.`) |
|---|---|---|---|
| Grand titre d'écran | DM Serif Display | 34 | `display` |
| Titre de section | DM Serif Display | 24 | `title` |
| Titre de carte | DM Serif Display | 19 | `cardTitle` |
| Petit titre au-dessus (MAJUSCULES, espacé) | DM Sans gras | 10 | `eyebrow` |
| Texte | DM Sans | 12 | `body` |
| Nom d'un article | DM Sans demi-gras | 12 | `itemName` |
| Légende (boutique · ville) | DM Sans | 10 | `caption` |
| Prix | DM Sans gras | 11 | `price` |
| Bouton | DM Sans demi-gras | 13 | `button` |

### Formes

| Élément | Rayon | Flutter (`DmRadius.`) |
|---|---|---|
| Petits blocs, champs dans une carte | 12 | `small` |
| Cartes produit, boutons | 16 | `card` |
| Grandes sections | 24 | `panel` |
| Carte principale, feuilles du bas | 28 | `hero` |
| Chips, tags | complètement arrondi | `pill` |

### Composants qui reviennent partout

- **En-tête de section** : petit titre bronze en majuscules + titre serif (`DmSectionHeader`).
- **Chips de filtre** : arrondies ; choisie = fond encre et texte blanc, sinon fond blanc et bordure.
- **Carte produit** : photo en haut, nom, « boutique · ville », prix en gras, % de correspondance en
  bronze (voir « Sélection locale » et « Local »).
- **Tag** : petite pastille (« 92 % style », « porté 8× ») (`DmPill`).
- **Boutons** : principal = encre, plein, rayon 16 ; secondaire = or ; tertiaire = bordure.
- **Feuille du bas** (détail, mémoire, essayage) : fond beige, coins hauts arrondis à 28.
- **Toast** : pastille encre en bas de l'écran.

## 4. Utiliser le design dans Flutter

```dart
import 'package:dressme/core/design/dressme_design.dart';

@override
Widget build(BuildContext context) {
  return Theme(
    data: dressMeTheme(), // tout l'écran prend le style du prototype
    child: Scaffold(
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const DmSectionHeader(eyebrow: 'Sélection locale', title: 'Choisi pour toi en Tunisie'),
          const SizedBox(height: 12),
          Text('Manuella · Tunis', style: DmText.caption),
          Text('69,3 TND', style: DmText.price),
          const DmPill('87 % proche'),
          FilledButton(onPressed: () {}, child: const Text('Voir la fiche')),
        ],
      ),
    ),
  );
}
```

- `Theme(data: dressMeTheme())` s'applique **à ton écran seulement** : les autres écrans ne changent pas.
- Utilise les constantes `DmColors`, `DmText`, `DmRadius` plutôt que des couleurs écrites à la main :
  si le design change, il suffit de modifier `dressme_design.dart`.

## 5. Ce qui reste à décider en équipe

- **Polices** : DM Sans et DM Serif Display ne sont pas encore incluses dans l'application. En attendant,
  Flutter utilise la police du système avec les mêmes tailles. Pour les ajouter, il faut modifier
  `mobile/pubspec.yaml` (fichier partagé, M6).
- **Thème global** : `mobile/lib/app/theme.dart` garde l'ancien thème violet. Pour appliquer le design à
  toute l'application d'un coup, il suffit d'y utiliser `dressMeTheme()`. C'est une décision d'équipe.
- `mobile/lib/core/` est partagé : toute modification de `dressme_design.dart` passe par une PR.

## Kit commun (à utiliser par tous les BO)

| Quoi | Où | Comment |
|---|---|---|
| Thème de toute l'app | `mobile/lib/app/theme.dart` | `appTheme = dressMeTheme()` : rien à faire dans vos écrans |
| Polices | `mobile/assets/fonts/` (DM Sans, DM Serif Display, licence OFL) | déclarées dans `pubspec.yaml`, marchent hors ligne |
| Couleurs, rayons, textes | `mobile/lib/core/design/dressme_design.dart` | `DmColors.gold`, `DmRadius.card`, `DmText.title` |
| Widgets communs | `mobile/lib/core/widgets/dm_widgets.dart` | `DmHero`, `DmCard`, `DmChoiceChip`, `DmButton` (dark / gold / outline), `DmScoreBadge`, `DmReasons`, `DmEmptyState`, `dmToast` + `DmSectionHeader`, `DmPill` |
| Galerie | route `/design` | tous les éléments sur un écran, pour vérifier le rendu |
| Web, slides, schémas | `docs/design/tokens/dressme_tokens.css` + `.json` | mêmes valeurs en CSS (`--dm-gold`…) et JSON |

Règles : pas de couleur en dur dans un écran (toujours `DmColors`), pas de nouveau widget commun sans le mettre ici.
