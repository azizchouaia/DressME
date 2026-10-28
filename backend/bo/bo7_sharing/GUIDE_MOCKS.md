# Guide BO7 · remplacer les mocks par le vrai travail de l'équipe

Ce guide explique quoi faire quand un·e collègue livre son module (M2, M3, M5, M6, M11, M12 ou M14), pour que
les tâches du BO7 utilisent son vrai travail à la place du mock.

**L'idée :** tu n'as normalement **rien à réécrire**. Pour chaque module, BO7 lui demande d'abord la réponse. S'il
n'est pas prêt, BO7 répond avec son propre mock (`integrations.py`). Dès que le module répond dans le bon format,
BO7 prend sa réponse tout seul.

Le format que BO7 attend de chaque module est dans **[INTEGRATION.md](INTEGRATION.md)** (à envoyer aux collègues).

---

## 1. Voir où tu en es

Lance le serveur, puis ouvre :

```
http://localhost:8000/bo7/social/integrations
```

Pour chaque module, tu vois `"source": "mock"` (pas encore prêt) ou le nom du module (`"M06"`, `"M03"`…) quand
c'est son vrai travail qui répond. En haut : `"real": 2, "total": 8` = 2 modules réels sur 8.

Dans l'app, sous chaque carte, une ligne dit la même chose : « M6 : simulé (mock) » ou « M6 : M06 ».

## 2. Quand un·e collègue livre son module

1. **Récupère son code** dans ton projet (merge de sa branche, ou copie de son dossier `backend/modules/mXX_...`).
   Ne modifie pas son dossier (règle 4) : s'il manque quelque chose, c'est à lui / elle de l'ajouter.

2. **Vérifie où est son vrai code.** Le modèle de l'équipe a deux fichiers par module :
   - `mock.py` : la fausse réponse de la semaine 1 (`{"todo": ...}`) ;
   - `service.py` : le vrai code.

   Le serveur choisit l'un ou l'autre avec **`USE_MOCKS`** (dans `infra/.env`, `True` par défaut) :
   - si ton / ta collègue a écrit son vrai code dans **`service.py`** → mets `USE_MOCKS=false` dans `infra/.env`
     et relance le serveur ;
   - s'il / elle a mis son vrai code directement dans **`mock.py`** → rien à changer.

   ⚠️ `USE_MOCKS` vaut pour **tous** les modules. Avec `false`, un module dont `service.py` n'est pas encore écrit
   lève une erreur : ce n'est pas grave pour BO7, qui reprend alors son propre mock pour ce module.

3. **Recharge** `/bo7/social/integrations` : la ligne du module doit passer de `mock` à `M0X`.

4. **Teste la tâche dans l'app** (voir le tableau plus bas) et regarde la ligne « source » sous la carte.

5. **Lance les tests :**
   ```
   cd backend
   python -m pytest -q bo/bo7_sharing modules/m10_share_cards modules/m15_challenges
   ```

## 3. Si la ligne reste sur « mock »

C'est que la réponse du module n'a pas le format attendu. BO7 garde son mock pour ne pas casser l'app.

1. Regarde ce que le module répond vraiment : ouvre `http://localhost:8000/docs`, trouve sa route (par exemple
   `POST /m06/verdict`), clique « Try it out » avec le même `payload` que dans INTEGRATION.md.
2. Compare avec le format attendu dans INTEGRATION.md. Deux cas :
   - **il manque une clé** (par exemple `verdict`) → demande à ton / ta collègue de l'ajouter (c'est son module) ;
   - **les noms sont différents** (par exemple `decision` au lieu de `verdict`) → adapte **une seule fonction**
     dans `integrations.py` (tableau ci-dessous) pour lire ses noms, ou mettez-vous d'accord sur un nom.
3. Relance les tests.

## 4. Où est chaque branchement

| Module (équipe) | Tâche BO7 | Fonction dans `integrations.py` | Clés que BO7 lit | Où tester dans l'app |
|---|---|---|---|---|
| M2 (BO1/BO2) | Recréer le look d'une amie | `match_pieces` | `items` | Communauté → « Recréer » sous un look |
| M2 (BO1/BO2) | Export du tableau (Mon look) | `complete_board` | `added` | Studio → « Mon look » avec un seul haut |
| M3 (BO1/BO2) | Bilan du mois, Je donne | `wear_stats` | `wears` (+ `days_logged`, `outfits`) | Studio → Bilan du mois / Je donne |
| M5 (BO4) | Suivre des profils proches | `style_profile` | `vector` (+ `tags`) | Communauté → « Profils qui te ressemblent » |
| M6 (BO5) | « Je l'achète ? » | `smartbuy_verdict` | `verdict`, `score` (+ `similar`, `new_outfits`) | Studio → Je l'achète ? |
| M11 (BO3) | Voyage | `trip_plan` | `days`, `packing` | Studio → Voyage |
| M12 (BO4) | Mon style | `style_timeline` | `months` | Studio → Mon style |
| M14 (BO6) | Mode styliste | `stylists`, `clients` | `stylists` / `clients` | Studio → Mode styliste |
| M1 (BO3) | Doublons pour Je donne | `duplicates` | `groups` (déjà réel) | Studio → Je donne |
| M7 (BO6) | Marques et boutiques tunisiennes | `m07_local.py` | déjà réel | Communauté → « N pièces » |

Chaque fonction a la même forme : elle appelle le module avec `_answer(...)` et donne en dernier argument le mock
(`def mock(): ...`). **Ne supprime pas les mocks** : ils servent de secours si un module tombe en panne, et
aux tests.

## 5. Cas particuliers

- **Recréer depuis une photo** : l'analyse de la photo est une version simple faite par BO7 (couleurs du haut, du bas
  et des pieds de l'image), dans `social.py` → `_photo_targets`. Quand M1 sait analyser une photo de look (type et
  couleur de chaque vêtement), remplace cette fonction par un appel à M1 qui renvoie la même liste
  `[{"category", "color_hex", "label"}]`.
- **Utilisateurs de démo** : le mock de M5 invente les goûts de `usr_042`, `amen`, `yasmine`, `sarra`, `ines`,
  `karim` (`MOCK_TASTES`). Avec le vrai M5, ces goûts viennent de l'onboarding : `MOCK_TASTES` ne sert plus.
- **Module lancé à part** (son propre serveur, autre port) : aujourd'hui BO7 appelle les modules dans le même
  serveur. Si un module tourne à part, il faudra ajouter un appel HTTP dans `_owner()` (`integrations.py`).

## 6. Checklist rapide

- [ ] J'ai récupéré le code du module sans le modifier
- [ ] `USE_MOCKS=false` si son vrai code est dans `service.py`
- [ ] `/bo7/social/integrations` montre le module en réel
- [ ] La tâche marche dans l'app (ligne « source » = le module)
- [ ] Les tests passent
- [ ] Commit (et push quand je le décide)
