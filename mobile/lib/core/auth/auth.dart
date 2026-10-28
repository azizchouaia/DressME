// Sign-in state for the whole app: the signed-in user + token, kept on the device between launches.
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/dm_api.dart';

class AppUser {
  const AppUser({required this.id, required this.name, required this.email, this.city, this.gender});

  final String id;
  final String name;
  final String email;
  final String? city;
  final String? gender;

  bool get isDemo => id == 'usr_demo';

  factory AppUser.fromJson(Json j) => AppUser(
        id: j['user_id'] as String,
        name: (j['name'] as String?) ?? '',
        email: (j['email'] as String?) ?? '',
        city: j['city'] as String?,
        gender: j['gender'] as String?,
      );
}

/// One instance for the app (the router listens to it to send signed-out people to /welcome).
class AuthController extends ChangeNotifier {
  static const _tokenKey = 'dm_token';

  AppUser? user;
  String? token;
  bool restored = false;

  final Dio _dio = Dio(BaseOptions(baseUrl: apiBaseUrl(), connectTimeout: const Duration(seconds: 8)));

  bool get signedIn => user != null;

  @override
  void notifyListeners() {
    DemoUsers.signedIn = user?.id; // every BO screen asks the modules about this user
    DemoUsers.token = token;
    super.notifyListeners();
  }

  /// At launch: reuse the saved token if the server still accepts it.
  Future<void> restore() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final saved = prefs.getString(_tokenKey);
      if (saved != null) {
        final r = await _dio.get<Map<String, dynamic>>('/auth/me', options: Options(headers: {'Authorization': 'Bearer $saved'}));
        token = saved;
        user = AppUser.fromJson(r.data!);
      }
    } catch (_) {
      token = null; // expired, or server down: ask to sign in again
      user = null;
    }
    restored = true;
    notifyListeners();
  }

  Future<void> login(String email, String password) =>
      _signIn('/auth/login', {'email': email.trim(), 'password': password});

  Future<void> register({required String name, required String email, required String password, String? city, String? gender}) =>
      _signIn('/auth/register', {'name': name.trim(), 'email': email.trim(), 'password': password, 'city': city, 'gender': gender});

  Future<void> _signIn(String path, Map<String, dynamic> body) async {
    final r = await _dio.post<Map<String, dynamic>>(path, data: body);
    token = r.data!['token'] as String;
    user = AppUser.fromJson((r.data!['user'] as Map).cast<String, dynamic>());
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token!);
    notifyListeners();
  }

  Future<void> updateProfile({String? name, String? city, String? gender}) async {
    final r = await _dio.patch<Map<String, dynamic>>('/auth/me',
        data: {'name': name, 'city': city, 'gender': gender}, options: Options(headers: {'Authorization': 'Bearer $token'}));
    user = AppUser.fromJson(r.data!);
    notifyListeners();
  }

  Future<void> logout() async {
    user = null;
    token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    notifyListeners();
  }
}

final authController = AuthController();
final authProvider = ChangeNotifierProvider<AuthController>((ref) => authController);
