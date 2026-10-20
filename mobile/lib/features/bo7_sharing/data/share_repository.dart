// Owner: BO7 · M10 — calls the backend through core/api_client.dart
import 'dart:typed_data';

import 'package:dio/dio.dart';

import 'bo7_api.dart';
import 'share_models.dart';

class ShareRepository {
  ShareRepository(this._api);

  final Bo7Api _api;

  Future<ShareCard> createCard(ShareCardRequest request) async {
    final res = await _api.dio.post<Map<String, dynamic>>('/m10/cards', data: request.toJson());
    return ShareCard.fromJson(res.data!);
  }

  /// Full URL of the PNG, usable by Image.network.
  String imageUrl(String imagePath) => _api.absolute(imagePath);

  /// PNG bytes, to share the image itself (not only the link).
  Future<Uint8List> imageBytes(String imagePath) async {
    final res = await _api.dio.get<List<int>>(
      _api.absolute(imagePath),
      options: Options(responseType: ResponseType.bytes),
    );
    return Uint8List.fromList(res.data!);
  }

  Future<ShareMetrics> metrics({String? userId}) async {
    final res = await _api.dio.get<Map<String, dynamic>>(
      '/m10/metrics',
      queryParameters: {if (userId != null) 'user_id': userId},
    );
    return ShareMetrics.fromJson(res.data!);
  }
}
