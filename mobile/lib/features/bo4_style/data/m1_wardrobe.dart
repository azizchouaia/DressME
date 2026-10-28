// Owner: BO3/BO4 (Amine) — M1 wardrobe API, same calls as Amine's web app (backend/modules/m01_wardrobe/ui/app.js).
import '../../../core/api/dm_api.dart';

const duplicateThreshold = 0.85; // config.yaml thresholds.duplicate
const confidenceThreshold = 0.85; // config.yaml thresholds.confidence

/// Closet sections, like Amine's wardrobe: accessories (left shelves), clothes (rails), shoes (right shelves).
const shelfOf = {
  'top': 'clothes', 'bottom': 'clothes', 'dress': 'clothes', 'outerwear': 'clothes', 'traditional': 'clothes',
  'shoes': 'shoes', 'accessory': 'accessories',
};
const upperRail = {'top', 'outerwear'}; // the other clothes hang on the lower rail

const categories = {
  'top': 'Tops', 'bottom': 'Bottoms', 'dress': 'Dresses', 'outerwear': 'Jackets & coats',
  'traditional': 'Traditional', 'shoes': 'Shoes', 'accessory': 'Accessories',
};
const categoryOne = {
  'top': 'Top', 'bottom': 'Bottom', 'dress': 'Dress', 'outerwear': 'Jacket & coat',
  'traditional': 'Traditional', 'shoes': 'Shoes', 'accessory': 'Accessory',
};
const seasons = {'spring': 'Spring', 'summer': 'Summer', 'autumn': 'Autumn', 'winter': 'Winter'};
const sizeSystems = {
  'letter': 'Letters (S, M, L…)', 'eu': 'EU', 'fr': 'FR', 'us': 'US', 'uk': 'UK', 'it': 'IT',
  'waist': 'Jeans (W/L)', 'shoe_eu': 'Shoe EU', 'shoe_us': 'Shoe US', 'one_size': 'One size', 'other': 'Other',
};
const conditions = {'new': 'New', 'good': 'Good', 'worn': 'Worn', 'needs_repair': 'Needs repair'};
const docKinds = {'auto': 'Detect automatically', 'receipt': 'Receipt', 'price_tag': 'Price tag', 'care_label': 'Care label'};
const donationPlaces = {'association': 'A local association', 'friend': 'Someone close', 'other': 'Other'};
const cities = ['Tunis', 'Ariana', 'Ben Arous', 'Manouba', 'Nabeul', 'Bizerte', 'Béja', 'Jendouba', 'Sousse', 'Monastir',
  'Mahdia', 'Sfax', 'Kairouan', 'Kasserine', 'Gafsa', 'Gabès', 'Médenine', 'Other'];

String pieceTitle(Json it) => cap('${it['subcategory'] ?? categoryOne[it['category']] ?? it['category'] ?? 'piece'}');
String shelf(Json it) => (it['shelf'] as String?) ?? shelfOf[it['category']] ?? 'clothes';

/// Cutout first (transparent), else the raw photo.
String? pieceImage(Json it) {
  bool ok(Object? s) => s is String && (s.startsWith('/') || s.startsWith('http'));
  if (ok(it['image_cutout'])) return it['image_cutout'] as String;
  return ok(it['image_raw']) ? it['image_raw'] as String : null;
}

String composition(Object? list) => jsonList(list).map((m) => '${m['percent']} % ${m['material']}').join(', ');

/// "55 % linen, 45 % cotton" -> [{material, percent}]
List<Json> parseComposition(String text) {
  final out = <Json>[];
  for (final m in RegExp(r'(\d+(?:[.,]\d+)?)\s*%\s*([^,;/\n\d]+)').allMatches(text)) {
    out.add({'material': m[2]!.trim().toLowerCase(), 'percent': double.parse(m[1]!.replaceAll(',', '.'))});
  }
  if (out.isEmpty) {
    for (final m in RegExp(r'([^,;/\n\d%]+?)\s*(\d+(?:[.,]\d+)?)\s*%').allMatches(text)) {
      out.add({'material': m[1]!.trim().toLowerCase(), 'percent': double.parse(m[2]!.replaceAll(',', '.'))});
    }
  }
  return out;
}

class M1 {
  M1(this.api, this.user);

  final DmApi api;
  final String user;

  String get _q => 'user_id=${Uri.encodeQueryComponent(user)}';
  String _item(String id) => '/m01/items/${Uri.encodeComponent(id)}';

  Future<Json> items({String? category, String? season, String? status}) => api.post('/m01/items', {
        'user_id': user,
        if (category != null) 'category': category,
        if (season != null) 'season': season,
        if (status != null) 'status': status,
      });
  Future<Json> item(String id) => api.get(_item(id), query: {'user_id': user});
  Future<Set<String>> duplicateIds() async {
    try {
      final g = (await api.post('/m01/duplicates', {'user_id': user}))['groups'] as List? ?? const [];
      return {for (final grp in g) for (final id in (grp as List)) '$id'};
    } catch (_) {
      return {};
    }
  }

  Future<List<Json>> similar(String id, {int k = 6, double? threshold}) async =>
      jsonList((await api.post('/m01/similar', {'user_id': user, 'item_id': id, 'k': k, if (threshold != null) 'threshold': threshold}))['neighbours']);
  Future<Json> classify(String dataUrl) => api.post('/m01/classify', {'user_id': user, 'image': dataUrl, 'mode': 'add_to_wardrobe'});
  Future<Json> confirm(String id) => api.post('${_item(id)}/confirm?$_q');
  Future<Json> delete(String id) => api.delete(_item(id), query: {'user_id': user});
  Future<Json> update(String id, Json changes) => api.patch('${_item(id)}?$_q', changes);
  Future<Json> donationIdeas(String id, String? city) => api.post('${_item(id)}/donation-suggestions?$_q', {'city': city});
  Future<Json> donate(String id, String? place) => api.post('${_item(id)}/donate?$_q', {'place': place});
  Future<Json> extract(String dataUrl, String kind, String itemId) =>
      api.post('/m01/documents/extract', {'user_id': user, 'image': dataUrl, 'kind': kind, 'item_id': itemId});
}
