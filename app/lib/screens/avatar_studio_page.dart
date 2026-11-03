import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../garments.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets/avatar_stage.dart';
import '../widgets/ui.dart';
import '../widgets/viewer_scene.dart';

class AvatarStudioPage extends ConsumerStatefulWidget {
  const AvatarStudioPage({super.key});

  @override
  ConsumerState<AvatarStudioPage> createState() => _AvatarStudioPageState();
}

class _AvatarStudioPageState extends ConsumerState<AvatarStudioPage> {
  var _activeSlot = 'top';
  var _saving = false;
  String? _notice;
  String? _noticeKind;
  String? _loadedOutfitId;
  String? _appliedWear;
  var _autoWore = false;
  Timer? _noticeTimer;

  @override
  void dispose() {
    _noticeTimer?.cancel();
    super.dispose();
  }

  void _notify(String kind, String text) {
    _noticeTimer?.cancel();
    setState(() {
      _noticeKind = kind;
      _notice = text;
    });
    _noticeTimer = Timer(const Duration(milliseconds: 2600), () {
      if (mounted) setState(() => _notice = null);
    });
  }

  void _syncFromRoute() {
    final params = GoRouterState.of(context).uri.queryParameters;
    final outfitId = params['outfit'];
    final wearId = params['wear'];
    final editor = ref.read(outfitEditorProvider);
    final items = ref.read(wardrobeProvider).value;

    if (outfitId != null && editor.outfit?.id != outfitId && _loadedOutfitId != outfitId) {
      _loadedOutfitId = outfitId;
      () async {
        try {
          final outfit = await ref.read(apiProvider).outfit(outfitId);
          ref.read(outfitEditorProvider.notifier).loadOutfit(outfit);
        } catch (_) {
          if (mounted) _notify('error', 'That outfit could not be loaded.');
        }
      }();
    }

    if (outfitId == null && editor.outfit == null && !editor.dirty && items != null && items.isNotEmpty && !_autoWore) {
      _autoWore = true;
      ref.read(outfitEditorProvider.notifier).startNew(autoWearSelection(items));
    }

    if (wearId != null && items != null && _appliedWear != wearId) {
      ClothingItem? item;
      for (final candidate in items) {
        if (candidate.id == wearId) item = candidate;
      }
      final slot = item == null || item.glbUrl == null ? null : wearSlot(item);
      if (item != null && slot != null) {
        _appliedWear = wearId;
        final next = autoWearSelection(items);
        next[slot] = item.id;
        ref.read(outfitEditorProvider.notifier).applySelection(next);
        setState(() => _activeSlot = slot);
        context.go('/avatar');
      }
    }
  }

  Future<void> _saveChanges() async {
    final editor = ref.read(outfitEditorProvider);
    if (editor.outfit == null) {
      await _nameOutfit();
      return;
    }
    final fields = outfitFieldsFromSelection(editor.selection);
    final changed = <String, dynamic>{};
    for (final entry in fields.entries) {
      if (entry.value != slotField(editor.outfit!, entry.key)) changed[entry.key] = entry.value;
    }
    setState(() => _saving = true);
    try {
      final saved = await ref.read(apiProvider).updateOutfit(editor.outfit!.id, changed);
      ref.read(outfitEditorProvider.notifier).markSaved(saved);
      ref.invalidate(outfitsProvider);
      if (mounted) _notify('ok', 'Outfit updated');
    } catch (error) {
      if (mounted) _notify('error', error.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _nameOutfit() async {
    final name = TextEditingController();
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (context) {
        return Padding(
          padding: EdgeInsets.fromLTRB(20, 20, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Name this outfit', style: TextStyle(fontFamily: 'Georgia', fontSize: 28)),
              const SizedBox(height: 12),
              TextField(
                controller: name,
                autofocus: true,
                decoration: const InputDecoration(labelText: 'Outfit name', hintText: 'e.g. Friday dinner'),
              ),
              const SizedBox(height: 12),
              PrimaryButton(
                label: 'Save outfit',
                onPressed: () => Navigator.pop(context, name.text.trim().isNotEmpty),
              ),
            ],
          ),
        );
      },
    );
    final trimmed = name.text.trim();
    name.dispose();
    if (saved != true || trimmed.isEmpty) return;
    await _create(trimmed);
  }

  Future<void> _create(String name) async {
    final editor = ref.read(outfitEditorProvider);
    setState(() => _saving = true);
    try {
      final created = await ref.read(apiProvider).createOutfit({
        'name': name,
        ...outfitFieldsFromSelection(editor.selection),
        'accessory_ids': <String>[],
      });
      ref.read(outfitEditorProvider.notifier).markSaved(created);
      ref.invalidate(outfitsProvider);
      if (!mounted) return;
      context.go('/avatar?outfit=${created.id}');
      _notify('ok', '“${created.name}” saved');
    } catch (error) {
      if (mounted) _notify('error', error.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final editor = ref.watch(outfitEditorProvider);
    final wardrobe = ref.watch(wardrobeProvider);
    final avatar = ref.watch(avatarProvider).value ?? AvatarConfig.fallback;
    final items = wardrobe.value ?? const <ClothingItem>[];
    final byId = {for (final item in items) item.id: item};
    final grouped = <String, List<ClothingItem>>{'top': [], 'bottom': [], 'outerwear': [], 'shoes': []};
    for (final item in items) {
      final slot = wearSlot(item);
      if (slot != null) grouped[slot]!.add(item);
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _syncFromRoute();
    });

    final slotItems = grouped[_activeSlot] ?? const <ClothingItem>[];
    final wearable = slotItems.where((item) => item.glbUrl != null).toList();
    final without3d = slotItems.length - wearable.length;

    return Column(
      children: [
        Expanded(
          flex: 5,
          child: Stack(
            children: [
              Positioned.fill(
                child: AvatarStage(
                  scene: ViewerScene.avatar(
                    avatarUrl: avatar.baseModelUrl,
                    scaleX: avatar.scaleX,
                    scaleY: avatar.scaleY,
                    scaleZ: avatar.scaleZ,
                    shape: avatar.parameters,
                    garments: garmentUrlsFor(editor.selection, byId),
                  ),
                ),
              ),
              if (_notice != null)
                Positioned(
                  left: 16,
                  right: 16,
                  top: 12,
                  child: Material(
                    color: _noticeKind == 'error' ? danger : ink,
                    borderRadius: BorderRadius.circular(12),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(_notice!, style: const TextStyle(color: paper)),
                    ),
                  ),
                ),
            ],
          ),
        ),
        Expanded(
          flex: 4,
          child: PageFrame(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(editor.outfit == null ? 'New outfit' : 'Editing outfit', style: const TextStyle(color: muted, fontSize: 12)),
                Text(
                  editor.outfit?.name ?? 'Dress your avatar',
                  style: const TextStyle(fontFamily: 'Georgia', fontSize: 26, height: 1.1),
                ),
                if (avatar.fromPhoto) ...[
                  const SizedBox(height: 6),
                  const Text(
                    'This avatar was built from your photo. Wardrobe clothes are fitted to the standard body, so they stay off this mesh.',
                    style: TextStyle(color: muted, fontSize: 13),
                  ),
                ],
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    if (editor.outfit != null)
                      OutlinedButton(
                        onPressed: () {
                          context.go('/avatar');
                          ref.read(outfitEditorProvider.notifier).startNew(editor.selection);
                        },
                        child: const Text('New'),
                      ),
                    OutlinedButton(
                      onPressed: items.isEmpty
                          ? null
                          : () {
                              final next = autoWearSelection(items);
                              final notifier = ref.read(outfitEditorProvider.notifier);
                              if (editor.outfit == null) {
                                notifier.startNew(next);
                              } else {
                                notifier.applySelection(next);
                              }
                              _notify('ok', 'Newest saved piece is on each slot');
                            },
                      child: const Text('Wear saved'),
                    ),
                    FilledButton(
                      onPressed: _saving || (editor.outfit != null && !editor.dirty) ? null : _saveChanges,
                      child: Text(_saving ? 'Saving…' : editor.outfit == null ? 'Save outfit' : editor.dirty ? 'Save' : 'Saved'),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                ChoiceChips(
                  options: [for (final slot in outfitSlots) (slot.$1, slot.$2)],
                  value: _activeSlot,
                  onChanged: (value) => setState(() => _activeSlot = value),
                ),
                const SizedBox(height: 10),
                if (wardrobe.hasError && items.isEmpty)
                  StatusMessage(message: wardrobe.error.toString(), onRetry: () => ref.read(wardrobeProvider.notifier).reload())
                else
                  SizedBox(
                    height: 118,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        _SlotChoice(
                          label: 'None',
                          selected: editor.selection[_activeSlot] == null,
                          onTap: () => ref.read(outfitEditorProvider.notifier).setSlot(_activeSlot, null),
                          child: const Icon(Icons.do_not_disturb_alt_outlined),
                        ),
                        for (final item in wearable)
                          _SlotChoice(
                            label: item.name,
                            selected: editor.selection[_activeSlot] == item.id,
                            onTap: () => ref.read(outfitEditorProvider.notifier).setSlot(_activeSlot, item.id),
                            child: ClothingThumb(item: item, size: 72),
                          ),
                      ],
                    ),
                  ),
                if (wearable.isEmpty) const Text('No 3D-ready items for this slot yet.', style: TextStyle(color: muted, fontSize: 13)),
                if (without3d > 0)
                  Text(
                    '$without3d ${without3d == 1 ? 'item is' : 'items are'} waiting for a 3D model.',
                    style: const TextStyle(color: muted, fontSize: 13),
                  ),
                if (editor.outfit != null) ...[
                  const Spacer(),
                  SecondaryButton(label: 'Save as a new outfit', onPressed: _nameOutfit),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _SlotChoice extends StatelessWidget {
  const _SlotChoice({required this.label, required this.selected, required this.onTap, required this.child});

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          width: 84,
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: selected ? ink : line, width: selected ? 2 : 1),
          ),
          child: Column(
            children: [
              SizedBox(height: 72, width: 72, child: Center(child: child)),
              const SizedBox(height: 4),
              Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11)),
            ],
          ),
        ),
      ),
    );
  }
}
