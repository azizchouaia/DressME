const clothingCategories = [
  't-shirt',
  'shirt',
  'pants',
  'jeans',
  'jacket',
  'dress',
  'shoes',
  'accessory',
  'other',
];

const avatarPresets = ['slim', 'average', 'broad'];

class User {
  const User({required this.id, required this.email, required this.displayName, required this.createdAt});

  final String id;
  final String email;
  final String displayName;
  final String createdAt;

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'].toString(),
      email: json['email'] as String,
      displayName: json['display_name'] as String,
      createdAt: json['created_at'].toString(),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'email': email,
    'display_name': displayName,
    'created_at': createdAt,
  };
}

class AuthSession {
  const AuthSession({required this.token, required this.user});

  final String token;
  final User user;

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    return AuthSession(token: json['access_token'] as String, user: User.fromJson(_map(json['user'])));
  }

  Map<String, dynamic> toJson() => {'access_token': token, 'user': user.toJson()};
}

class ClothingAnalysis {
  const ClothingAnalysis({
    required this.category,
    required this.subcategory,
    required this.primaryColor,
    required this.secondaryColor,
    required this.pattern,
    required this.sleeveType,
    required this.brand,
    required this.confidence,
  });

  final String? category;
  final String? subcategory;
  final String? primaryColor;
  final String? secondaryColor;
  final String? pattern;
  final String? sleeveType;
  final String? brand;
  final double confidence;

  factory ClothingAnalysis.fromJson(Map<String, dynamic> json) {
    return ClothingAnalysis(
      category: json['category'] as String?,
      subcategory: json['subcategory'] as String?,
      primaryColor: json['primary_color'] as String?,
      secondaryColor: json['secondary_color'] as String?,
      pattern: json['pattern'] as String?,
      sleeveType: json['sleeve_type'] as String?,
      brand: json['brand'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
    );
  }
}

class ClothingFields {
  const ClothingFields({
    required this.name,
    required this.category,
    this.subcategory,
    this.color,
    this.secondaryColor,
    this.pattern,
    this.brand,
    this.size,
    this.material,
    this.sleeveType,
  });

  final String name;
  final String category;
  final String? subcategory;
  final String? color;
  final String? secondaryColor;
  final String? pattern;
  final String? brand;
  final String? size;
  final String? material;
  final String? sleeveType;

  ClothingFields copyWith({
    String? name,
    String? category,
    String? subcategory,
    String? color,
    String? secondaryColor,
    String? pattern,
    String? brand,
    String? size,
    String? material,
    String? sleeveType,
    bool clearSubcategory = false,
    bool clearColor = false,
    bool clearSecondaryColor = false,
    bool clearPattern = false,
    bool clearBrand = false,
    bool clearSize = false,
    bool clearMaterial = false,
    bool clearSleeveType = false,
  }) {
    return ClothingFields(
      name: name ?? this.name,
      category: category ?? this.category,
      subcategory: clearSubcategory ? null : (subcategory ?? this.subcategory),
      color: clearColor ? null : (color ?? this.color),
      secondaryColor: clearSecondaryColor ? null : (secondaryColor ?? this.secondaryColor),
      pattern: clearPattern ? null : (pattern ?? this.pattern),
      brand: clearBrand ? null : (brand ?? this.brand),
      size: clearSize ? null : (size ?? this.size),
      material: clearMaterial ? null : (material ?? this.material),
      sleeveType: clearSleeveType ? null : (sleeveType ?? this.sleeveType),
    );
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'category': category,
    'subcategory': subcategory,
    'color': color,
    'secondary_color': secondaryColor,
    'pattern': pattern,
    'brand': brand,
    'size': size,
    'material': material,
    'sleeve_type': sleeveType,
  };
}

class ClothingItem extends ClothingFields {
  const ClothingItem({
    required this.id,
    required super.name,
    required super.category,
    super.subcategory,
    super.color,
    super.secondaryColor,
    super.pattern,
    super.brand,
    super.size,
    super.material,
    super.sleeveType,
    required this.imageUrl,
    required this.thumbnailUrl,
    required this.glbUrl,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String? imageUrl;
  final String? thumbnailUrl;
  final String? glbUrl;
  final String status;
  final String createdAt;
  final String updatedAt;

  factory ClothingItem.fromJson(Map<String, dynamic> json) {
    return ClothingItem(
      id: json['id'].toString(),
      name: json['name'] as String? ?? 'Untitled',
      category: json['category'] as String? ?? 'other',
      subcategory: json['subcategory'] as String?,
      color: json['color'] as String?,
      secondaryColor: json['secondary_color'] as String?,
      pattern: json['pattern'] as String?,
      brand: json['brand'] as String?,
      size: json['size'] as String?,
      material: json['material'] as String?,
      sleeveType: json['sleeve_type'] as String?,
      imageUrl: json['image_url'] as String?,
      thumbnailUrl: json['thumbnail_url'] as String?,
      glbUrl: json['glb_url'] as String?,
      status: json['status'] as String? ?? 'uploaded',
      createdAt: json['created_at'].toString(),
      updatedAt: json['updated_at'].toString(),
    );
  }

  ClothingItem copyItem({String? glbUrl, String? status, String? category, bool clearGlb = false}) {
    return ClothingItem(
      id: id,
      name: name,
      category: category ?? this.category,
      subcategory: subcategory,
      color: color,
      secondaryColor: secondaryColor,
      pattern: pattern,
      brand: brand,
      size: size,
      material: material,
      sleeveType: sleeveType,
      imageUrl: imageUrl,
      thumbnailUrl: thumbnailUrl,
      glbUrl: clearGlb ? null : (glbUrl ?? this.glbUrl),
      status: status ?? this.status,
      createdAt: createdAt,
      updatedAt: updatedAt,
    );
  }
}

class Garment3DStatus {
  const Garment3DStatus({
    required this.itemId,
    required this.status,
    required this.glbUrl,
    required this.category,
    required this.message,
  });

  final String itemId;
  final String status;
  final String? glbUrl;
  final String? category;
  final String message;

  factory Garment3DStatus.fromJson(Map<String, dynamic> json) {
    return Garment3DStatus(
      itemId: json['item_id'].toString(),
      status: json['status'] as String,
      glbUrl: json['glb_url'] as String?,
      category: json['category'] as String?,
      message: json['message'] as String? ?? '',
    );
  }
}

class Outfit {
  const Outfit({
    required this.id,
    required this.name,
    required this.shirtId,
    required this.pantsId,
    required this.jacketId,
    required this.shoesId,
    required this.accessoryIds,
  });

  final String id;
  final String name;
  final String? shirtId;
  final String? pantsId;
  final String? jacketId;
  final String? shoesId;
  final List<String> accessoryIds;

  factory Outfit.fromJson(Map<String, dynamic> json) {
    return Outfit(
      id: json['id'].toString(),
      name: json['name'] as String? ?? 'Outfit',
      shirtId: json['shirt_id']?.toString(),
      pantsId: json['pants_id']?.toString(),
      jacketId: json['jacket_id']?.toString(),
      shoesId: json['shoes_id']?.toString(),
      accessoryIds: [
        for (final id in (json['accessory_ids'] as List?) ?? const []) id.toString(),
      ],
    );
  }
}

class BodyProfile {
  const BodyProfile({
    required this.avatarPreset,
    required this.source,
    required this.heightCm,
    required this.weightKg,
    required this.chestCm,
    required this.waistCm,
    required this.hipsCm,
    required this.shoulderWidthCm,
    required this.armLengthCm,
    required this.legLengthCm,
  });

  final String avatarPreset;
  final String source;
  final double? heightCm;
  final double? weightKg;
  final double? chestCm;
  final double? waistCm;
  final double? hipsCm;
  final double? shoulderWidthCm;
  final double? armLengthCm;
  final double? legLengthCm;

  factory BodyProfile.fromJson(Map<String, dynamic> json) {
    double? number(String key) => (json[key] as num?)?.toDouble();
    return BodyProfile(
      avatarPreset: json['avatar_preset'] as String? ?? 'average',
      source: json['source'] as String? ?? 'manual',
      heightCm: number('height_cm'),
      weightKg: number('weight_kg'),
      chestCm: number('chest_cm'),
      waistCm: number('waist_cm'),
      hipsCm: number('hips_cm'),
      shoulderWidthCm: number('shoulder_width_cm'),
      armLengthCm: number('arm_length_cm'),
      legLengthCm: number('leg_length_cm'),
    );
  }

  Map<String, dynamic> toJson() => {
    'avatar_preset': avatarPreset,
    'height_cm': heightCm,
    'weight_kg': weightKg,
    'chest_cm': chestCm,
    'waist_cm': waistCm,
    'hips_cm': hipsCm,
    'shoulder_width_cm': shoulderWidthCm,
    'arm_length_cm': armLengthCm,
    'leg_length_cm': legLengthCm,
  };

  double? measurement(String key) => switch (key) {
    'height_cm' => heightCm,
    'weight_kg' => weightKg,
    'chest_cm' => chestCm,
    'waist_cm' => waistCm,
    'hips_cm' => hipsCm,
    'shoulder_width_cm' => shoulderWidthCm,
    'arm_length_cm' => armLengthCm,
    'leg_length_cm' => legLengthCm,
    _ => null,
  };

  BodyProfile withMeasurement(String key, double? value) {
    return BodyProfile(
      avatarPreset: avatarPreset,
      source: source,
      heightCm: key == 'height_cm' ? value : heightCm,
      weightKg: key == 'weight_kg' ? value : weightKg,
      chestCm: key == 'chest_cm' ? value : chestCm,
      waistCm: key == 'waist_cm' ? value : waistCm,
      hipsCm: key == 'hips_cm' ? value : hipsCm,
      shoulderWidthCm: key == 'shoulder_width_cm' ? value : shoulderWidthCm,
      armLengthCm: key == 'arm_length_cm' ? value : armLengthCm,
      legLengthCm: key == 'leg_length_cm' ? value : legLengthCm,
    );
  }

  BodyProfile withPreset(String preset) {
    return BodyProfile(
      avatarPreset: preset,
      source: source,
      heightCm: heightCm,
      weightKg: weightKg,
      chestCm: chestCm,
      waistCm: waistCm,
      hipsCm: hipsCm,
      shoulderWidthCm: shoulderWidthCm,
      armLengthCm: armLengthCm,
      legLengthCm: legLengthCm,
    );
  }
}

class AvatarConfig {
  const AvatarConfig({
    required this.baseModelUrl,
    required this.preset,
    required this.scaleX,
    required this.scaleY,
    required this.scaleZ,
    this.fromPhoto = false,
    this.photoModelUrl,
    this.parameters = const {},
  });

  static const fallback = AvatarConfig(
    baseModelUrl: '/models/avatar/base_avatar.glb',
    preset: 'average',
    scaleX: 1,
    scaleY: 1,
    scaleZ: 1,
  );

  final String baseModelUrl;
  final String preset;
  final double scaleX;
  final double scaleY;
  final double scaleZ;
  final bool fromPhoto;
  final String? photoModelUrl;
  final Map<String, double> parameters;

  factory AvatarConfig.fromJson(Map<String, dynamic> json) {
    final scale = _map(json['scale']);
    return AvatarConfig(
      baseModelUrl: json['base_model_url'] as String? ?? fallback.baseModelUrl,
      preset: json['preset'] as String? ?? 'average',
      scaleX: (scale['x'] as num?)?.toDouble() ?? 1,
      scaleY: (scale['y'] as num?)?.toDouble() ?? 1,
      scaleZ: (scale['z'] as num?)?.toDouble() ?? 1,
      fromPhoto: json['from_photo'] == true,
      photoModelUrl: json['photo_model_url'] as String?,
      parameters: {
        for (final entry in _map(json['parameters']).entries)
          if (entry.value is num) entry.key: (entry.value as num).toDouble(),
      },
    );
  }
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return value.map((key, item) => MapEntry(key.toString(), item));
  return {};
}
