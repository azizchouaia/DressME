// Owner: BO7 — "Partager un look sur mon avatar 3D" (BO7 selected idea 4, M9 + M10).
// The avatar comes from BO9: M9's rendered image when M9 is real, else a picture of BO9's 3D viewer (web),
// else an image the user picks. M10 draws a "tryon" card: the avatar on the left, the outfit pieces (M1) next
// to it, with the referral link. BO9's avatar is not dressed yet (no garment on the body in their viewer).
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/design/dressme_design.dart';
import '../data/bo7_models.dart';
import '../data/bo7_repository.dart';
import '../logic/bo7_providers.dart';
import 'avatar/avatar_view.dart';
import 'widgets.dart';

class AvatarShareScreen extends ConsumerStatefulWidget {
  const AvatarShareScreen({super.key, required this.pieces, this.language = 'fr', this.qr = false, this.shop});

  final List<Garment> pieces;
  final String language;
  final bool qr;
  final String? shop;

  @override
  ConsumerState<AvatarShareScreen> createState() => _AvatarShareScreenState();
}

class _AvatarShareScreenState extends ConsumerState<AvatarShareScreen> {
  final _viewer = AvatarViewController();
  final _title = TextEditingController(text: 'Mon look sur mon avatar');
  String? _avatar; // data URI (viewer picture / imported image) or URL (M9)
  String _source = '';
  bool _busy = false;

  Future<void> _capture() async {
    final png = await _viewer.capture();
    if (!mounted) return;
    if (png == null) {
      showSnack(context, 'Aucun avatar à photographier : le viewer BO9 n\'affiche pas de corps.');
      return;
    }
    setState(() {
      _avatar = png;
      _source = 'Photo du viewer 3D BO9';
    });
  }

  Future<void> _import() async {
    final file = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 1400);
    if (file == null) return;
    final bytes = await file.readAsBytes();
    if (!mounted) return;
    setState(() {
      _avatar = 'data:${file.mimeType ?? 'image/png'};base64,${base64Encode(bytes)}';
      _source = 'Image importée';
    });
  }

  Future<void> _create() async {
    setState(() => _busy = true);
    // the card always shows the avatar: if no picture was taken yet, it is taken now from BO9's viewer
    if (_avatar == null && avatarViewerSupported) {
      final png = await _viewer.capture();
      if (png != null && mounted) {
        setState(() {
          _avatar = png;
          _source = 'Photo du viewer 3D BO9';
        });
      }
    }
    try {
      final card = await ref.read(bo7RepositoryProvider).createCard(
            userId: ref.read(currentUserProvider),
            kind: 'tryon',
            pieces: widget.pieces,
            title: _title.text.trim().isEmpty ? 'Mon look sur mon avatar' : _title.text.trim(),
            subtitle: widget.shop != null ? 'Stylé avec ${widget.shop}' : 'Sans selfie · DressMe',
            language: widget.language,
            qr: widget.qr,
            avatarImage: _avatar,
          );
      if (mounted) Navigator.of(context).pop(card);
    } on Bo7Exception catch (e) {
      if (mounted) showSnack(context, e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// BO9's avatar wears my pieces: the server reshapes its shirt / shorts and puts the pieces' photos on them.
  String _dressed(String base) {
    Garment? first(Set<String> cats) {
      for (final g in widget.pieces) {
        if (cats.contains(g.category)) return g;
      }
      return null;
    }

    final one = first({'dress', 'traditional'});
    final top = first({'top', 'outerwear'}) ?? one;
    final bottom = first({'bottom'}) ?? one;
    String hex(Garment g) => g.colorHex.replaceAll('#', '');
    final sep = base.contains('?') ? '&' : '?';
    final params = [
      'user=${Uri.encodeQueryComponent(ref.read(currentUserProvider))}',
      if (top != null) ...['top=${top.id}', 'topc=${hex(top)}'],
      if (bottom != null && bottom != top) ...['bottom=${bottom.id}', 'bottomc=${hex(bottom)}'],
    ];
    return params.isEmpty ? base : '$base$sep${params.join('&')}';
  }

  Widget _preview(Bo7Repository repo) {
    final a = _avatar;
    if (a == null) {
      return const Center(child: Icon(Icons.accessibility_new_rounded, size: 70, color: DmColors.borderStrong));
    }
    if (a.startsWith('data:')) return Image.memory(base64Decode(a.split(',').last), fit: BoxFit.contain);
    return Image.network(repo.url(a), fit: BoxFit.contain);
  }

  @override
  Widget build(BuildContext context) {
    final repo = ref.read(bo7RepositoryProvider);
    final status = ref.watch(avatarStatusProvider);
    final m9 = status.valueOrNull?.m9Image;
    if (_avatar == null && m9 != null) {
      _avatar = m9; // M9 (BO9) rendered the avatar: use it directly
      _source = 'Rendu M9 (BO9)';
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Sur mon avatar')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
        children: [
          const Bo7Hero(
            eyebrow: 'Avatar 3D · BO9 (M9) + M10',
            title: 'Mon look sur mon avatar',
            subtitle: 'Un avatar sans visage qui porte tes pièces (leur photo et leur forme) : '
                'tu partages ton look sans selfie. Prends la photo de ton avatar, puis crée la carte.',
          ),
          const SizedBox(height: 14),
          AsyncBody<AvatarStatus>(
            value: status,
            compact: true,
            onRetry: () => ref.invalidate(avatarStatusProvider),
            builder: (s) => Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (avatarViewerSupported && s.viewer)
                  Center(
                    child: SizedBox(
                      width: 420,
                      height: 620,
                      child: AvatarView(url: repo.url(_dressed(s.viewerUrl)), controller: _viewer),
                    ),
                  )
                else
                  SizedBox(height: 160, child: AvatarView(url: repo.url(_dressed(s.viewerUrl)), controller: _viewer)),
                if (s.bodies.isEmpty) ...[
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration:
                        BoxDecoration(color: DmColors.warningBg, borderRadius: BorderRadius.circular(DmRadius.card)),
                    child: const Text(
                      'Le viewer BO9 n\'a pas encore de corps : les fichiers SMPL-X (licence) ne sont pas dans Git. '
                      'BO9 les génère avec ai/smplx_export.py (voir avatar_studio/README.md). '
                      'En attendant, importe une image de ton avatar, ou la carte affichera une silhouette.',
                      style: DmText.body,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (avatarViewerSupported)
                FilledButton.icon(
                  onPressed: _capture,
                  icon: const Icon(Icons.photo_camera_outlined, size: 18),
                  label: const Text('Prendre la photo de l\'avatar'),
                ),
              OutlinedButton.icon(
                onPressed: _import,
                icon: const Icon(Icons.upload_outlined, size: 18),
                label: const Text('Importer une image de l\'avatar'),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Bo7Panel(
            title: 'Aperçu',
            subtitle: _avatar == null ? 'Pas encore d\'avatar : la carte affichera une silhouette.' : _source,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 150,
                  height: 230,
                  decoration: BoxDecoration(color: DmColors.canvas, borderRadius: BorderRadius.circular(DmRadius.card)),
                  padding: const EdgeInsets.all(8),
                  child: _preview(repo),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (final g in widget.pieces)
                        Container(
                          width: 78,
                          height: 96,
                          padding: const EdgeInsets.all(4),
                          decoration: BoxDecoration(
                            color: DmColors.surface,
                            borderRadius: BorderRadius.circular(DmRadius.small),
                            border: Border.all(color: DmColors.border),
                          ),
                          child: GarmentImage(g),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          TextField(controller: _title, decoration: const InputDecoration(hintText: 'Titre de la carte')),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: _busy ? null : _create,
            icon: const Icon(Icons.auto_awesome, size: 18),
            label: Text(_busy ? 'Dessin de la carte…' : 'Créer la carte avatar'),
          ),
        ],
      ),
    );
  }
}
