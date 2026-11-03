import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state.dart';
import '../theme.dart';
import '../widgets/avatar_stage.dart';
import '../widgets/ui.dart';
import '../widgets/viewer_scene.dart';

const _previewGarments = {
  'top': '/models/garments/black_tshirt.glb',
  'bottom': '/models/garments/blue_jeans.glb',
  'outerwear': '/models/garments/black_jacket.glb',
  'shoes': '/models/garments/white_sneakers.glb',
};

class WelcomePage extends ConsumerStatefulWidget {
  const WelcomePage({super.key});

  @override
  ConsumerState<WelcomePage> createState() => _WelcomePageState();
}

class _WelcomePageState extends ConsumerState<WelcomePage> {
  var _loading = false;
  String? _error;

  Future<void> _demo() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final session = await ref.read(apiProvider).demo();
      await ref.read(authProvider.notifier).setSession(session);
      if (mounted) context.go('/avatar');
    } catch (error) {
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: PageFrame(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.all(Radius.circular(24)),
                  child: AvatarStage(
                    scene: ViewerScene.avatar(
                      avatarUrl: '/models/avatar/base_avatar.glb',
                      scaleX: 1,
                      scaleY: 1,
                      scaleZ: 1,
                      garments: _previewGarments,
                      interactive: false,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              const Text('SMART WARDROBE', style: TextStyle(letterSpacing: 1.4, color: muted, fontSize: 12)),
              const SizedBox(height: 8),
              const Text(
                'Your real clothes, on your own avatar.',
                style: TextStyle(fontFamily: 'Georgia', fontSize: 36, height: 1.05, fontWeight: FontWeight.w500),
              ),
              const SizedBox(height: 10),
              const Text(
                'Photograph what you own, build outfits, and see them on a 3D model before you get dressed.',
                style: TextStyle(color: inkSoft, fontSize: 16),
              ),
              const SizedBox(height: 18),
              PrimaryButton(label: 'Create account', onPressed: () => context.go('/register')),
              const SizedBox(height: 8),
              SecondaryButton(label: 'I already have an account', onPressed: () => context.go('/login')),
              const SizedBox(height: 4),
              TextButton(onPressed: _loading ? null : _demo, child: Text(_loading ? 'Opening demo…' : 'Explore the demo wardrobe')),
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: const TextStyle(color: danger)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
