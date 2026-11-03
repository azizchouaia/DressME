import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../garments.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets/avatar_stage.dart';
import '../widgets/clothing_form.dart';
import '../widgets/ui.dart';
import '../widgets/viewer_scene.dart';

class ClothingDetailPage extends ConsumerStatefulWidget {
  const ClothingDetailPage({super.key, required this.id});

  final String id;

  @override
  ConsumerState<ClothingDetailPage> createState() => _ClothingDetailPageState();
}

class _ClothingDetailPageState extends ConsumerState<ClothingDetailPage> {
  ClothingItem? _item;
  Object? _error;
  var _loading = true;
  var _saving = false;
  var _deleting = false;
  var _building = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final item = await ref.read(apiProvider).clothing(widget.id);
      if (!mounted) return;
      setState(() {
        _item = item;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error;
        _loading = false;
      });
    }
  }

  Future<void> _save(ClothingFields values) async {
    final item = _item;
    if (item == null) return;
    setState(() {
      _saving = true;
      _message = null;
    });
    try {
      final updated = await ref.read(apiProvider).updateClothing(item.id, values);
      ref.read(wardrobeProvider.notifier).replace(updated);
      if (!mounted) return;
      setState(() {
        _item = updated;
        _message = 'Changes saved';
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

  Future<void> _buildPreview() async {
    final item = _item;
    if (item == null) return;
    setState(() {
      _building = true;
      _message = 'Running on this computer’s GPU. The first time also downloads the model.';
    });
    try {
      final result = await ref.read(apiProvider).process3d(item.id);
      final updated = item.copyItem(glbUrl: result.glbUrl, status: result.status, category: result.category);
      ref.read(wardrobeProvider.notifier).replace(updated);
      if (!mounted) return;
      setState(() {
        _item = updated;
        _message = result.message;
        _building = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _message = error.toString();
        _building = false;
      });
    }
  }

  Future<void> _remove() async {
    final item = _item;
    if (item == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove this item?'),
        content: Text('Remove “${item.name}” from your wardrobe?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => _deleting = true);
    try {
      await ref.read(apiProvider).deleteClothing(item.id);
      ref.read(wardrobeProvider.notifier).removeLocal(item.id);
      if (mounted) context.go('/wardrobe');
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _message = error.toString();
        _deleting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final item = _item;
    if (_loading && item == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_error != null || item == null) {
      return Scaffold(body: StatusMessage(message: _error?.toString() ?? 'Item not found', onRetry: _load));
    }
    final photoModel = item.glbUrl != null && !isAvatarGarment(item.glbUrl);
    return Scaffold(
      body: PageFrame(
        child: ListView(
          children: [
            PageHeader(showBack: true, title: item.name),
            SizedBox(
              height: 320,
              child: ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: photoModel
                    ? AvatarStage(scene: ViewerScene.mesh(item.glbUrl))
                    : Center(child: ClothingThumb(item: item, size: 220)),
              ),
            ),
            const SizedBox(height: 12),
            Text(
              isAvatarGarment(item.glbUrl)
                  ? 'Ready to wear on your avatar'
                  : item.glbUrl != null
                  ? 'Saved. Avatar wears this automatically in its slot.'
                  : 'No 3D model yet — this piece shows in your wardrobe but not on the avatar.',
              style: const TextStyle(color: inkSoft),
            ),
            if (photoModel) ...[
              const SizedBox(height: 12),
              PrimaryButton(label: 'Try it on', onPressed: () => context.go('/avatar?wear=${item.id}')),
            ],
            if (item.imageUrl != null && !isAvatarGarment(item.glbUrl)) ...[
              const SizedBox(height: 8),
              SecondaryButton(
                label: photoModel ? 'Rebuild 3D preview' : 'Create 3D preview',
                busy: _building,
                onPressed: _buildPreview,
              ),
            ],
            const SizedBox(height: 16),
            ClothingForm(
              key: ValueKey('${item.updatedAt}-${item.category}-${item.glbUrl}'),
              initial: item,
              submitLabel: 'Save changes',
              submitting: _saving,
              onSubmit: _save,
            ),
            if (_message != null) ...[
              const SizedBox(height: 12),
              Text(_message!, textAlign: TextAlign.center, style: const TextStyle(color: muted)),
            ],
            const SizedBox(height: 12),
            TextButton(
              onPressed: _deleting ? null : _remove,
              child: Text(_deleting ? 'Deleting…' : 'Delete item', style: const TextStyle(color: danger)),
            ),
          ],
        ),
      ),
    );
  }
}
