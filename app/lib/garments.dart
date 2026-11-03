import 'models.dart';

const categoryLabels = {
  't-shirt': 'T-Shirt',
  'shirt': 'Shirt',
  'pants': 'Pants',
  'jeans': 'Jeans',
  'jacket': 'Jacket',
  'dress': 'Dress',
  'shoes': 'Shoes',
  'accessory': 'Accessory',
  'other': 'Other',
};

const categoryFilters = [
  ('all', 'All'),
  ('t-shirt', 'T-Shirts'),
  ('shirt', 'Shirts'),
  ('pants', 'Pants'),
  ('jeans', 'Jeans'),
  ('jacket', 'Jackets'),
  ('dress', 'Dresses'),
  ('shoes', 'Shoes'),
  ('accessory', 'Accessories'),
  ('other', 'Other'),
];

const outfitSlots = [
  ('top', 'Top', 'shirt_id'),
  ('bottom', 'Bottom', 'pants_id'),
  ('outerwear', 'Outerwear', 'jacket_id'),
  ('shoes', 'Shoes', 'shoes_id'),
];

const _categorySlot = {
  't-shirt': 'top',
  'shirt': 'top',
  'dress': 'top',
  'pants': 'bottom',
  'jeans': 'bottom',
  'jacket': 'outerwear',
  'shoes': 'shoes',
};

const colorSwatches = {
  'black': 0xFF1D1D1F,
  'white': 0xFFF4F2ED,
  'gray': 0xFF8E8E8E,
  'navy': 0xFF22304F,
  'blue': 0xFF3D5A80,
  'light blue': 0xFF9BBBE0,
  'red': 0xFFB4282D,
  'burgundy': 0xFF6E1E2D,
  'pink': 0xFFE6A0B4,
  'orange': 0xFFE17828,
  'yellow': 0xFFE6C83C,
  'beige': 0xFFC8B593,
  'brown': 0xFF6E4B32,
  'green': 0xFF3C8246,
  'olive': 0xFF6B6A45,
  'purple': 0xFF6E468C,
};

const colorOptions = [
  'black',
  'white',
  'gray',
  'navy',
  'blue',
  'light blue',
  'red',
  'burgundy',
  'pink',
  'orange',
  'yellow',
  'beige',
  'brown',
  'green',
  'olive',
  'purple',
];

int swatchFor(String? color) => colorSwatches[color?.toLowerCase()] ?? 0xFFD9D4CC;

String capitalize(String value) {
  if (value.isEmpty) return value;
  return value[0].toUpperCase() + value.substring(1);
}

String describeItem(ClothingItem item) {
  final parts = [categoryLabels[item.category] ?? item.category];
  if (item.color != null && item.color!.isNotEmpty) parts.add(capitalize(item.color!));
  return parts.join(' · ');
}

bool isAvatarGarment(String? url) => url != null && url.contains('/models/');

String? wearSlot(ClothingItem item) {
  final mapped = _categorySlot[item.category];
  if (mapped != null) return mapped;
  if (item.glbUrl == null) return null;
  final text = '${item.name} ${item.subcategory ?? ''}'.toLowerCase();
  if (RegExp('shoe|sneaker|boot|heel').hasMatch(text)) return 'shoes';
  if (RegExp('pant|jean|short|trouser|skirt').hasMatch(text)) return 'bottom';
  if (RegExp('jacket|coat|hoodie|blazer|cardigan|outer').hasMatch(text)) return 'outerwear';
  if (RegExp('dress|shirt|tee|top|blouse|sweater').hasMatch(text)) return 'top';
  return 'top';
}

typedef SlotSelection = Map<String, String?>;

SlotSelection emptySelection() => {'top': null, 'bottom': null, 'outerwear': null, 'shoes': null};

SlotSelection selectionFromOutfit(Outfit outfit) => {
  'top': outfit.shirtId,
  'bottom': outfit.pantsId,
  'outerwear': outfit.jacketId,
  'shoes': outfit.shoesId,
};

Map<String, String?> outfitFieldsFromSelection(SlotSelection selection) => {
  'shirt_id': selection['top'],
  'pants_id': selection['bottom'],
  'jacket_id': selection['outerwear'],
  'shoes_id': selection['shoes'],
};

String? slotField(Outfit outfit, String field) => switch (field) {
  'shirt_id' => outfit.shirtId,
  'pants_id' => outfit.pantsId,
  'jacket_id' => outfit.jacketId,
  'shoes_id' => outfit.shoesId,
  _ => null,
};

SlotSelection autoWearSelection(List<ClothingItem> items) {
  final newestFirst = [...items]..sort((a, b) {
    final left = b.updatedAt.isNotEmpty ? b.updatedAt : b.createdAt;
    final right = a.updatedAt.isNotEmpty ? a.updatedAt : a.createdAt;
    return left.compareTo(right);
  });
  final selection = emptySelection();
  for (final slot in const ['top', 'bottom', 'outerwear', 'shoes']) {
    final ready = newestFirst.where((item) => item.glbUrl != null && wearSlot(item) == slot);
    final photo = ready.cast<ClothingItem?>().firstWhere(
      (item) => !isAvatarGarment(item?.glbUrl),
      orElse: () => null,
    );
    selection[slot] = (photo ?? (ready.isEmpty ? null : ready.first))?.id;
  }
  return selection;
}

Map<String, String?> garmentUrlsFor(SlotSelection selection, Map<String, ClothingItem> byId) {
  return {
    for (final entry in selection.entries) entry.key: entry.value == null ? null : byId[entry.value]?.glbUrl,
  };
}
