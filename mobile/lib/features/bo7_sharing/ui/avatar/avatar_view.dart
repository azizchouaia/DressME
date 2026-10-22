// Owner: BO7 — the BO9 avatar viewer inside the app. On the web it is the real 3D viewer of BO9
// (avatar_studio/web/viewer, served by the API on /bo7/avatar/viewer/) and its picture can be taken;
// on Android / iOS a message is shown and the user imports a picture of the avatar instead.
export 'avatar_view_stub.dart' if (dart.library.js_interop) 'avatar_view_web.dart';
