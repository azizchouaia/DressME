import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets/avatar_stage.dart';
import '../widgets/ui.dart';
import '../widgets/viewer_scene.dart';

const _measurements = [
  ('height_cm', 'Height (cm)'),
  ('weight_kg', 'Weight (kg)'),
  ('chest_cm', 'Chest (cm)'),
  ('waist_cm', 'Waist (cm)'),
  ('hips_cm', 'Hips (cm)'),
  ('shoulder_width_cm', 'Shoulders (cm)'),
  ('arm_length_cm', 'Arm length (cm)'),
  ('leg_length_cm', 'Leg length (cm)'),
];

class ProfilePage extends ConsumerStatefulWidget {
  const ProfilePage({super.key});

  @override
  ConsumerState<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends ConsumerState<ProfilePage> {
  BodyProfile? _profile;
  Object? _error;
  var _loading = true;
  var _saving = false;
  var _creating = false;
  String? _message;
  final _controllers = <String, TextEditingController>{};
  final _picker = ImagePicker();

  @override
  void initState() {
    super.initState();
    for (final measurement in _measurements) {
      _controllers[measurement.$1] = TextEditingController();
    }
    _load();
  }

  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final profile = await ref.read(apiProvider).bodyProfile();
      if (!mounted) return;
      _apply(profile);
      setState(() => _loading = false);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error;
        _loading = false;
      });
    }
  }

  void _apply(BodyProfile profile) {
    _profile = profile;
    for (final measurement in _measurements) {
      final value = profile.measurement(measurement.$1);
      _controllers[measurement.$1]!.text = value == null ? '' : value.toString();
    }
  }

  Future<void> _save() async {
    final current = _profile;
    if (current == null) return;
    var draft = current;
    for (final measurement in _measurements) {
      final raw = _controllers[measurement.$1]!.text.trim();
      draft = draft.withMeasurement(measurement.$1, raw.isEmpty ? null : double.tryParse(raw));
    }
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      final saved = await ref.read(apiProvider).updateBody(draft);
      ref.invalidate(avatarProvider);
      if (!mounted) return;
      setState(() {
        _apply(saved);
        _message = 'Saved. Your avatar now uses these settings.';
        _saving = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _message = error.toString();
        _saving = false;
      });
    }
  }

  Future<void> _fromPhoto(ImageSource source) async {
    try {
      final file = await _picker.pickImage(source: source, imageQuality: 85, maxWidth: 1280);
      if (file == null) return;
      final bytes = await file.readAsBytes();
      setState(() {
        _creating = true;
        _message = 'Building a 3D body from this photo. The first run can take a few minutes.';
      });
      await ref.read(apiProvider).avatarFromPhoto(bytes);
      ref.invalidate(avatarProvider);
      if (!mounted) return;
      setState(() {
        _creating = false;
        _message = 'That photo is now your 3D avatar. Open Avatar to look at it. The first build can take a few minutes.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _creating = false;
        _message = error.toString();
      });
    }
  }

  Future<void> _useStandardBody() async {
    setState(() {
      _creating = true;
      _message = null;
    });
    try {
      await ref.read(apiProvider).clearPhotoAvatar();
      ref.invalidate(avatarProvider);
      if (!mounted) return;
      setState(() {
        _creating = false;
        _message = 'Removed the photo preview. Your measurements are unchanged.';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _creating = false;
        _message = error.toString();
      });
    }
  }

  Future<void> _signOut() async {
    await ref.read(authProvider.notifier).logout();
    ref.read(outfitEditorProvider.notifier).startNew();
    if (mounted) context.go('/welcome');
  }

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(authProvider)?.user;
    final profile = _profile;
    final avatar = ref.watch(avatarProvider).value;
    final fromPhoto = avatar?.fromPhoto ?? false;
    final photoUrl = avatar?.photoModelUrl;
    return PageFrame(
      child: ListView(
        children: [
          PageHeader(title: user?.displayName ?? 'Profile', subtitle: user?.email),
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text('Body profile', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                const SizedBox(height: 6),
                const Text(
                  'Height, build, and the measurements below reshape the human body. Clothes follow the same dimensions.',
                  style: TextStyle(color: muted, fontSize: 13),
                ),
                const SizedBox(height: 12),
                if (_error != null)
                  StatusMessage(message: _error.toString(), onRetry: _load)
                else if (_loading || profile == null)
                  const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()))
                else ...[
                  const Text('Photo preview', style: TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 6),
                  const Text(
                    'A full-body photo becomes your 3D avatar. Height still changes its size. Wardrobe clothes stay on the standard body.',
                    style: TextStyle(color: muted, fontSize: 13),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      OutlinedButton(
                        onPressed: _creating ? null : () => _fromPhoto(ImageSource.camera),
                        child: const Text('Take photo'),
                      ),
                      OutlinedButton(
                        onPressed: _creating ? null : () => _fromPhoto(ImageSource.gallery),
                        child: const Text('Choose photo'),
                      ),
                      if (fromPhoto)
                        OutlinedButton(
                          onPressed: _creating ? null : _useStandardBody,
                          child: const Text('Remove photo preview'),
                        ),
                    ],
                  ),
                  if (photoUrl != null) ...[
                    const SizedBox(height: 12),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(16),
                      child: SizedBox(
                        height: 220,
                        child: AvatarStage(scene: ViewerScene.mesh(photoUrl)),
                      ),
                    ),
                  ],
                  const SizedBox(height: 16),
                  const Text('Avatar build', style: TextStyle(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  ChoiceChips(
                    options: const [('slim', 'Slim'), ('average', 'Average'), ('broad', 'Broad')],
                    value: profile.avatarPreset,
                    onChanged: (value) => setState(() => _profile = profile.withPreset(value)),
                  ),
                  const SizedBox(height: 12),
                  for (final measurement in _measurements) ...[
                    TextField(
                      controller: _controllers[measurement.$1],
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: InputDecoration(labelText: measurement.$2),
                    ),
                    const SizedBox(height: 12),
                  ],
                  PrimaryButton(label: 'Save body profile', busy: _saving, onPressed: _save),
                  if (_message != null) ...[
                    const SizedBox(height: 8),
                    Text(_message!, textAlign: TextAlign.center, style: const TextStyle(color: muted, fontSize: 13)),
                  ],
                ],
              ],
            ),
          ),
          const SizedBox(height: 16),
          SecondaryButton(label: 'Sign out', onPressed: _signOut),
        ],
      ),
    );
  }
}
