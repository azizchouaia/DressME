// Owner: BO7 — HTTP access to the shared modules M10 (/m10) and M15 (/m15) through core/api_client.dart.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';

class Bo7Api {
  Bo7Api([ApiClient? client])
      : client = client ??
            ApiClient(baseUrl: const String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:8000'));

  final ApiClient client;

  Dio get dio => client.dio;

  /// Turns a path returned by the API (e.g. `/m10/cards/x/image`) into a full URL.
  String absolute(String pathOrUrl) {
    if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) return pathOrUrl;
    final base = dio.options.baseUrl.replaceAll(RegExp(r'/+$'), '');
    return '$base$pathOrUrl';
  }
}

/// One client for BO7. Override in tests with `bo7ApiProvider.overrideWithValue(...)`.
final bo7ApiProvider = Provider<Bo7Api>((ref) => Bo7Api());
