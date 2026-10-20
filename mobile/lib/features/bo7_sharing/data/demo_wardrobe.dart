// Owner: BO7 · M15 — demo wardrobe, same ids as backend/modules/m15_challenges/tests/fixtures/wardrobe.json.
// Used until M1 (wardrobe digitiser, BO3) exposes GET /wardrobe/items.
import 'challenge_models.dart';

const demoWardrobe = <WardrobeItem>[
  WardrobeItem(id: 'itm_t1', name: 'White t-shirt', category: 'top', colorHex: '#F1EFE9'),
  WardrobeItem(id: 'itm_t2', name: 'Black t-shirt', category: 'top', colorHex: '#2B2830'),
  WardrobeItem(id: 'itm_t3', name: 'Linen shirt', category: 'top', colorHex: '#E3CFAE', localBrand: 'Sidi Linen Co.'),
  WardrobeItem(id: 'itm_t4', name: 'Navy shirt', category: 'top', colorHex: '#3D4C6E'),
  WardrobeItem(id: 'itm_t5', name: 'Grey sweater', category: 'top', colorHex: '#9C99A0'),
  WardrobeItem(id: 'itm_t6', name: 'Sage sweater', category: 'top', colorHex: '#A8C3A0'),
  WardrobeItem(id: 'itm_o1', name: 'Denim jacket', category: 'outerwear', colorHex: '#7F98B8'),
  WardrobeItem(id: 'itm_b1', name: 'Straight jeans', category: 'bottom', colorHex: '#8FA7C4'),
  WardrobeItem(id: 'itm_b2', name: 'Black trousers', category: 'bottom', colorHex: '#2B2830'),
  WardrobeItem(id: 'itm_b3', name: 'Beige chinos', category: 'bottom', colorHex: '#D9C3A0'),
  WardrobeItem(id: 'itm_b4', name: 'White jeans', category: 'bottom', colorHex: '#F4F2EE'),
  WardrobeItem(id: 'itm_d1', name: 'Black dress', category: 'dress', colorHex: '#26232B'),
  WardrobeItem(id: 'itm_tr1', name: 'Jebba', category: 'traditional', colorHex: '#F3EFE6', localBrand: 'Medina artisans'),
  WardrobeItem(id: 'itm_s1', name: 'White sneakers', category: 'shoes', colorHex: '#F1EFE9'),
  WardrobeItem(id: 'itm_s2', name: 'Black boots', category: 'shoes', colorHex: '#2B2830'),
  WardrobeItem(id: 'itm_s3', name: 'Brown loafers', category: 'shoes', colorHex: '#8A6446'),
  WardrobeItem(id: 'itm_s4', name: 'Balgha slippers', category: 'shoes', colorHex: '#E6D3B0', localBrand: 'Medina artisans'),
  WardrobeItem(id: 'itm_s5', name: 'Grey trainers', category: 'shoes', colorHex: '#B5B2B8'),
  WardrobeItem(id: 'itm_a1', name: 'Sage tote', category: 'accessory', colorHex: '#A8C3A0', localBrand: 'Atelier Medina'),
];
