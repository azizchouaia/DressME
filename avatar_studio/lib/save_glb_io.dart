import 'dart:io';
import 'dart:typed_data';

Future<String> saveGlb(Uint8List bytes) async {
  final file = File('${Directory.systemTemp.path}${Platform.pathSeparator}avatar.glb');
  await file.writeAsBytes(bytes, flush: true);
  return file.path;
}
