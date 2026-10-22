// Owner: BO6 — English display of the French codes M14 keeps: occasions read in the chat and the
// stylists' specialities (they are matched against each other, so the API keeps them as they are).
const _wordsEn = {
  'mariage': 'wedding',
  'fiançailles': 'engagement',
  'henna': 'henna',
  'entretien': 'job interview',
  'soutenance': 'graduation',
  'travail': 'work',
  'soirée': 'evening',
  'aïd': 'Eid',
  'traditionnel': 'traditional',
  'bureau': 'office',
  'minimaliste': 'minimalist',
  'homme': 'menswear',
  'costume': 'suits',
  'baskets': 'sneakers',
  'robe': 'dresses',
};

/// "mariage" -> "wedding"; unknown words are shown as they are.
String wordEn(String word) => _wordsEn[word] ?? word;
