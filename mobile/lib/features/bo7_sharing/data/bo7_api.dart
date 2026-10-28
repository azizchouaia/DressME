// Owner: BO7 — HTTP access to M10 (/m10), M15 (/m15) and the BO7 routes (/bo7) through core/api_client.dart.
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/dm_api.dart' as dm;
import '../../../core/api_client.dart';

/// Address of the DressMe API.
/// - `--dart-define=API_URL=http://192.168.1.10:8000` wins (real phone on the same Wi-Fi);
/// - inside the DressMe app: the same backend as every other BO (localhost:8000 on the web);
/// - when the app is served by the API itself (http://localhost:8000/bo7/app/): that address.
String apiBaseUrl() {
  const override = String.fromEnvironment('API_URL');
  if (override.isNotEmpty) return override;
  if (kIsWeb && Uri.base.path.startsWith('/bo7/')) return Uri.base.origin;
  return dm.apiBaseUrl();
}

class Bo7Api {
  Bo7Api([ApiClient? client]) : client = client ?? ApiClient(baseUrl: apiBaseUrl());

  final ApiClient client;

  Dio get dio => client.dio;

  /// Turns a path returned by the API (e.g. `/m10/cards/x/image`) into a full URL.
  String absolute(String pathOrUrl) {
    if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://') || pathOrUrl.startsWith('data:')) {
      return pathOrUrl;
    }
    final base = dio.options.baseUrl.replaceAll(RegExp(r'/+$'), '');
    return '$base${pathOrUrl.startsWith('/') ? '' : '/'}$pathOrUrl';
  }
}

/// One client for BO7. Override in tests with `bo7ApiProvider.overrideWithValue(...)`.
final bo7ApiProvider = Provider<Bo7Api>((ref) => Bo7Api());
