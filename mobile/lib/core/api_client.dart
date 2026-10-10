import 'package:dio/dio.dart';

class ApiClient {
  ApiClient({String baseUrl = 'http://10.0.2.2:8000'})
      : dio = Dio(BaseOptions(baseUrl: baseUrl));

  final Dio dio;
}
