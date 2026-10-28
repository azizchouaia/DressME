// Shared API access for every BO screen: one backend (uvicorn api.main:app), one base URL.
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// `--dart-define=API_URL=http://192.168.1.10:8000` for a real phone; otherwise
/// localhost on the web and 10.0.2.2 (the host machine) on the Android emulator.
String apiBaseUrl() {
  const override = String.fromEnvironment('API_URL');
  if (override.isNotEmpty) return override;
  return kIsWeb ? 'http://localhost:8000' : 'http://10.0.2.2:8000';
}

/// Who the modules are asked about: the signed-in user. The demo account maps to each module's demo data.
abstract final class DemoUsers {
  static String? signedIn; // set by AuthController (core/auth/auth.dart)
  static String? token;

  static String get wardrobe => signedIn ?? 'usr_demo'; // M1 / M6 / M7 / M13 / M18
  static String get outfits => signedIn == null || signedIn == 'usr_demo' ? 'demo_f' : signedIn!; // M2 / M3 / M4 / M17
}

typedef Json = Map<String, dynamic>;

class DmApi {
  DmApi([String? baseUrl])
      : base = baseUrl ?? apiBaseUrl(),
        _dio = Dio(BaseOptions(
          baseUrl: baseUrl ?? apiBaseUrl(),
          connectTimeout: const Duration(seconds: 8),
          receiveTimeout: const Duration(seconds: 180), // LLM / 3D calls can be slow
        )) {
    _dio.interceptors.add(InterceptorsWrapper(onRequest: (o, h) {
      final t = DemoUsers.token;
      if (t != null) o.headers['Authorization'] = 'Bearer $t';
      h.next(o);
    }));
  }

  final String base;
  final Dio _dio;

  Future<Json> get(String path, {Map<String, dynamic>? query}) async {
    final r = await _dio.get<dynamic>(path, queryParameters: query);
    return _json(r.data);
  }

  Future<Json> post(String path, [Object? body]) async {
    final r = await _dio.post<dynamic>(path, data: body ?? const <String, dynamic>{});
    return _json(r.data);
  }

  /// Module endpoints answer {"result": {...}, "mocked": bool}; this returns the inner result.
  Future<Json> call(String path, {String? userId, Json payload = const {}}) async {
    final j = await post(path, {'user_id': userId, 'payload': payload});
    final res = j['result'];
    return res is Map ? {...res.cast<String, dynamic>(), '_mocked': j['mocked'] == true} : j;
  }

  /// Absolute URL for a media path returned by the API ("/m01/media/...").
  String media(String? path) {
    if (path == null || path.isEmpty) return '';
    return path.startsWith('http') ? path : '$base$path';
  }

  static Json _json(Object? data) {
    if (data is Map) return data.cast<String, dynamic>();
    return {'value': data};
  }
}

/// A readable message from any API error (server down, 4xx/5xx detail).
String apiError(Object e) {
  if (e is DioException) {
    if (e.type == DioExceptionType.connectionError || e.type == DioExceptionType.connectionTimeout) {
      return 'The server is not answering. Start it: cd backend → python -m uvicorn api.main:app --port 8000';
    }
    final d = e.response?.data;
    if (d is Map && d['detail'] != null) return '${e.response?.statusCode}: ${d['detail']}';
    return '${e.response?.statusCode ?? ''} ${e.message ?? e.type.name}'.trim();
  }
  return '$e';
}

final dmApiProvider = Provider<DmApi>((ref) => DmApi());

List<Json> jsonList(Object? v) => [for (final e in (v as List? ?? const [])) if (e is Map) e.cast<String, dynamic>()];
String cap(String s) => s.isEmpty ? s : '${s[0].toUpperCase()}${s.substring(1)}';
String pct(Object? v) => v is num ? '${(v * 100).round()} %' : '–';
