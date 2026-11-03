/// Origin of the FastAPI server. Override for a device or emulator:
/// `flutter run --dart-define=API_URL=http://10.0.2.2:8765`
const String apiOrigin = String.fromEnvironment(
  'API_URL',
  defaultValue: 'http://127.0.0.1:8765',
);

String resolveUrl(String url) {
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  final origin = apiOrigin.endsWith('/') ? apiOrigin.substring(0, apiOrigin.length - 1) : apiOrigin;
  return url.startsWith('/') ? '$origin$url' : '$origin/$url';
}
