import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'config.dart';
import 'models.dart';

const _sessionKey = 'smart-wardrobe-auth';

final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError('SharedPreferences must be overridden at startup');
});

final authProvider = NotifierProvider<AuthController, AuthSession?>(AuthController.new);

class AuthController extends Notifier<AuthSession?> {
  @override
  AuthSession? build() {
    final raw = ref.watch(sharedPreferencesProvider).getString(_sessionKey);
    if (raw == null || raw.isEmpty) return null;
    try {
      return AuthSession.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      return null;
    }
  }

  Future<void> setSession(AuthSession session) async {
    state = session;
    await ref.read(sharedPreferencesProvider).setString(_sessionKey, jsonEncode(session.toJson()));
  }

  Future<void> logout() async {
    state = null;
    await ref.read(sharedPreferencesProvider).remove(_sessionKey);
  }
}

final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(
    BaseOptions(
      baseUrl: '${apiOrigin.endsWith('/') ? apiOrigin.substring(0, apiOrigin.length - 1) : apiOrigin}/api/v1',
      connectTimeout: const Duration(seconds: 20),
      headers: {'Accept': 'application/json'},
    ),
  );
  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) {
        final token = ref.read(authProvider)?.token;
        if (token != null) options.headers['Authorization'] = 'Bearer $token';
        handler.next(options);
      },
      onError: (error, handler) {
        final hadToken = ref.read(authProvider)?.token != null;
        if (error.response?.statusCode == 401 && hadToken) {
          ref.read(authProvider.notifier).logout();
        }
        handler.next(error);
      },
    ),
  );
  return dio;
});

final apiProvider = Provider<WardrobeApi>((ref) => WardrobeApi(ref.watch(dioProvider)));

class ApiException implements Exception {
  ApiException(this.message, {this.status = 0});

  final String message;
  final int status;

  @override
  String toString() => message;
}

class WardrobeApi {
  WardrobeApi(this._dio);

  final Dio _dio;

  Future<AuthSession> register({
    required String email,
    required String password,
    required String displayName,
  }) {
    return _send(
      _dio.post(
        '/auth/register',
        data: {'email': email, 'password': password, 'display_name': displayName},
      ),
      AuthSession.fromJson,
    );
  }

  Future<AuthSession> login({required String email, required String password}) {
    return _send(_dio.post('/auth/login', data: {'email': email, 'password': password}), AuthSession.fromJson);
  }

  Future<AuthSession> demo() => _send(_dio.post('/auth/demo'), AuthSession.fromJson);

  Future<List<ClothingItem>> wardrobe({String? category}) {
    return _sendList(
      _dio.get('/wardrobe', queryParameters: category == null ? null : {'category': category}),
      ClothingItem.fromJson,
    );
  }

  Future<ClothingItem> clothing(String id) => _send(_dio.get('/wardrobe/$id'), ClothingItem.fromJson);

  Future<ClothingItem> upload(Uint8List bytes) {
    final form = FormData.fromMap({
      'image': MultipartFile.fromBytes(bytes, filename: 'photo.jpg'),
    });
    return _send(_dio.post('/wardrobe/upload', data: form), ClothingItem.fromJson);
  }

  Future<ClothingItem> updateClothing(String id, ClothingFields fields) {
    return _send(_dio.put('/wardrobe/$id', data: fields.toJson()), ClothingItem.fromJson);
  }

  Future<void> deleteClothing(String id) => _sendVoid(_dio.delete('/wardrobe/$id'));

  Future<ClothingAnalysis> analyze(String id) {
    return _send(_dio.post('/wardrobe/$id/analyze'), ClothingAnalysis.fromJson);
  }

  Future<Garment3DStatus> process3d(String id) {
    return _send(_dio.post('/garments/$id/process-3d'), Garment3DStatus.fromJson);
  }

  Future<List<Outfit>> outfits() => _sendList(_dio.get('/outfits'), Outfit.fromJson);

  Future<Outfit> outfit(String id) => _send(_dio.get('/outfits/$id'), Outfit.fromJson);

  Future<Outfit> createOutfit(Map<String, dynamic> body) => _send(_dio.post('/outfits', data: body), Outfit.fromJson);

  Future<Outfit> updateOutfit(String id, Map<String, dynamic> body) {
    return _send(_dio.put('/outfits/$id', data: body), Outfit.fromJson);
  }

  Future<void> deleteOutfit(String id) => _sendVoid(_dio.delete('/outfits/$id'));

  Future<BodyProfile> bodyProfile() => _send(_dio.get('/body-profile'), BodyProfile.fromJson);

  Future<BodyProfile> updateBody(BodyProfile profile) {
    return _send(_dio.put('/body-profile', data: profile.toJson()), BodyProfile.fromJson);
  }

  Future<AvatarConfig> avatar() => _send(_dio.get('/avatar'), AvatarConfig.fromJson);

  Future<AvatarConfig> avatarFromPhoto(Uint8List bytes) {
    final form = FormData.fromMap({
      'image': MultipartFile.fromBytes(bytes, filename: 'person.jpg'),
    });
    return _send(
      _dio.post(
        '/avatar/from-photo',
        data: form,
        options: Options(
          sendTimeout: const Duration(minutes: 2),
          receiveTimeout: const Duration(minutes: 8),
        ),
      ),
      AvatarConfig.fromJson,
    );
  }

  Future<AvatarConfig> clearPhotoAvatar() => _send(_dio.delete('/avatar/from-photo'), AvatarConfig.fromJson);

  Future<T> _send<T>(Future<Response<dynamic>> request, T Function(Map<String, dynamic>) parse) async {
    final data = await _data(request);
    return parse(_asMap(data));
  }

  Future<List<T>> _sendList<T>(Future<Response<dynamic>> request, T Function(Map<String, dynamic>) parse) async {
    final data = await _data(request);
    if (data is! List) throw ApiException('Unexpected response');
    return [for (final item in data) parse(_asMap(item))];
  }

  Future<void> _sendVoid(Future<Response<dynamic>> request) async {
    await _data(request);
  }

  Future<dynamic> _data(Future<Response<dynamic>> request) async {
    try {
      final response = await request;
      return response.data;
    } on DioException catch (error) {
      throw ApiException(_describe(error), status: error.response?.statusCode ?? 0);
    }
  }
}

Map<String, dynamic> _asMap(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return value.map((key, item) => MapEntry(key.toString(), item));
  throw ApiException('Unexpected response');
}

String _describe(DioException error) {
  if (error.type == DioExceptionType.connectionError || error.type == DioExceptionType.connectionTimeout) {
    return 'Cannot reach the server. Check that the backend is running.';
  }
  final payload = error.response?.data;
  if (payload is Map && payload['detail'] != null) {
    final detail = payload['detail'];
    if (detail is String) return detail;
    if (detail is List && detail.isNotEmpty && detail.first is Map) {
      final first = detail.first as Map;
      final message = first['msg']?.toString() ?? 'Invalid input';
      final loc = first['loc'];
      if (loc is List && loc.isNotEmpty) return '${loc.last}: $message';
      return message;
    }
  }
  final status = error.response?.statusCode ?? 0;
  if (status >= 500) return 'The server had a problem. Please try again.';
  if (status == 0) return 'Cannot reach the server. Check that the backend is running.';
  return 'Request failed ($status)';
}

final wardrobeProvider = AsyncNotifierProvider<WardrobeController, List<ClothingItem>>(WardrobeController.new);

class WardrobeController extends AsyncNotifier<List<ClothingItem>> {
  @override
  Future<List<ClothingItem>> build() => ref.read(apiProvider).wardrobe();

  Future<void> reload() async {
    state = await AsyncValue.guard(() => ref.read(apiProvider).wardrobe());
  }

  void replace(ClothingItem item) {
    final current = state.value;
    if (current == null) return;
    state = AsyncData([for (final existing in current) existing.id == item.id ? item : existing]);
  }

  void removeLocal(String id) {
    final current = state.value;
    if (current == null) return;
    state = AsyncData(current.where((item) => item.id != id).toList());
  }
}

final outfitsProvider = AsyncNotifierProvider<OutfitsController, List<Outfit>>(OutfitsController.new);

class OutfitsController extends AsyncNotifier<List<Outfit>> {
  @override
  Future<List<Outfit>> build() => ref.read(apiProvider).outfits();

  Future<void> reload() async {
    state = await AsyncValue.guard(() => ref.read(apiProvider).outfits());
  }

  void removeLocal(String id) {
    final current = state.value;
    if (current == null) return;
    state = AsyncData(current.where((outfit) => outfit.id != id).toList());
  }
}

final avatarProvider = AsyncNotifierProvider<AvatarController, AvatarConfig>(AvatarController.new);

class AvatarController extends AsyncNotifier<AvatarConfig> {
  @override
  Future<AvatarConfig> build() async {
    try {
      return await ref.read(apiProvider).avatar();
    } catch (_) {
      return AvatarConfig.fallback;
    }
  }
}

class OutfitEditorState {
  const OutfitEditorState({required this.selection, required this.outfit, required this.dirty});

  final Map<String, String?> selection;
  final Outfit? outfit;
  final bool dirty;
}

final outfitEditorProvider = NotifierProvider<OutfitEditor, OutfitEditorState>(OutfitEditor.new);

class OutfitEditor extends Notifier<OutfitEditorState> {
  @override
  OutfitEditorState build() => OutfitEditorState(selection: emptyEditorSelection(), outfit: null, dirty: false);

  void setSlot(String slot, String? itemId) {
    state = OutfitEditorState(
      selection: {...state.selection, slot: itemId},
      outfit: state.outfit,
      dirty: true,
    );
  }

  void applySelection(Map<String, String?> selection, {bool dirty = true}) {
    state = OutfitEditorState(selection: {...selection}, outfit: state.outfit, dirty: dirty);
  }

  void loadOutfit(Outfit outfit) {
    state = OutfitEditorState(selection: _selection(outfit), outfit: outfit, dirty: false);
  }

  void markSaved(Outfit outfit) {
    state = OutfitEditorState(selection: _selection(outfit), outfit: outfit, dirty: false);
  }

  void startNew([Map<String, String?>? selection]) {
    state = OutfitEditorState(selection: {...?selection} , outfit: null, dirty: false);
  }
}

Map<String, String?> emptyEditorSelection() => {'top': null, 'bottom': null, 'outerwear': null, 'shoes': null};

Map<String, String?> _selection(Outfit outfit) => {
  'top': outfit.shirtId,
  'bottom': outfit.pantsId,
  'outerwear': outfit.jacketId,
  'shoes': outfit.shoesId,
};
