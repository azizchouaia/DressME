// Owner: BO7 · M10 — reusable bottom sheet. Any feature can call:
//   showShareCardSheet(context, ShareCardRequest(...))          → creates the card, then shows it
//   showExistingCardSheet(context, imageUrl: ..., shareUrl: ...) → card already created by the backend
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/share_models.dart';
import '../logic/share_provider.dart';

Future<void> showShareCardSheet(BuildContext context, ShareCardRequest request) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => _CreateAndShare(request: request),
  );
}

Future<void> showExistingCardSheet(
  BuildContext context, {
  required String imageUrl,
  required String shareUrl,
  String caption = '',
  String altText = 'DressMe card',
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => SharePreview(
      imagePath: imageUrl,
      shareUrl: shareUrl,
      caption: caption,
      altText: altText,
    ),
  );
}

class _CreateAndShare extends ConsumerStatefulWidget {
  const _CreateAndShare({required this.request});
  final ShareCardRequest request;

  @override
  ConsumerState<_CreateAndShare> createState() => _CreateAndShareState();
}

class _CreateAndShareState extends ConsumerState<_CreateAndShare> {
  @override
  void initState() {
    super.initState();
    Future.microtask(
      () => ref.read(shareCardControllerProvider.notifier).create(widget.request),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(shareCardControllerProvider);
    return state.when(
      loading: () => const _SheetMessage(icon: null, text: 'Creating your card…'),
      error: (e, _) => _SheetMessage(
        icon: Icons.cloud_off,
        text: 'The card could not be created. Check that the DressMe server is running, then try again.',
        action: TextButton(
          onPressed: () => ref.read(shareCardControllerProvider.notifier).create(widget.request),
          child: const Text('Try again'),
        ),
      ),
      data: (card) => card == null
          ? const _SheetMessage(icon: null, text: 'Creating your card…')
          : SharePreview(
              imagePath: card.imageUrl,
              shareUrl: card.shareUrl,
              caption: card.caption,
              altText: card.altText,
              aspectRatio: card.aspectRatio,
            ),
    );
  }
}

class SharePreview extends ConsumerStatefulWidget {
  const SharePreview({
    super.key,
    required this.imagePath,
    required this.shareUrl,
    required this.caption,
    required this.altText,
    this.aspectRatio = 9 / 16,
  });

  final String imagePath;
  final String shareUrl;
  final String caption;
  final String altText;
  final double aspectRatio;

  @override
  ConsumerState<SharePreview> createState() => _SharePreviewState();
}

class _SharePreviewState extends ConsumerState<SharePreview> {
  late final TextEditingController _caption = TextEditingController(text: widget.caption);
  bool _busy = false;

  @override
  void dispose() {
    _caption.dispose();
    super.dispose();
  }

  /// No native share sheet package in the shared pubspec (share_plus would need a PR on pubspec.yaml):
  /// the caption + referral link are copied, the user pastes them in WhatsApp / Instagram with the card.
  Future<void> _shareImage() async {
    setState(() => _busy = true);
    try {
      await Clipboard.setData(ClipboardData(text: '${_caption.text}\n${widget.shareUrl}'));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Caption and link copied: paste them with the card in WhatsApp or Instagram')),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _copyLink() async {
    await Clipboard.setData(ClipboardData(text: widget.shareUrl));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Link copied')));
  }

  @override
  Widget build(BuildContext context) {
    final url = ref.read(shareRepositoryProvider).imageUrl(widget.imagePath);
    final maxH = MediaQuery.sizeOf(context).height * 0.5;
    return SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ConstrainedBox(
              constraints: BoxConstraints(maxHeight: maxH),
              child: AspectRatio(
                aspectRatio: widget.aspectRatio,
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(16),
                  child: Image.network(
                    url,
                    fit: BoxFit.contain,
                    semanticLabel: widget.altText,
                    loadingBuilder: (c, child, p) =>
                        p == null ? child : const Center(child: CircularProgressIndicator()),
                    errorBuilder: (_, __, ___) =>
                        const Center(child: Text('Preview unavailable')),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _caption,
              maxLines: 3,
              minLines: 1,
              decoration: const InputDecoration(labelText: 'Caption', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 8),
            Text(widget.shareUrl, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _busy ? null : _shareImage,
              icon: _busy
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.ios_share),
              label: const Text('Share to Instagram, WhatsApp…'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _copyLink,
              icon: const Icon(Icons.link),
              label: const Text('Copy link'),
            ),
          ],
        ),
      ),
    );
  }
}

class _SheetMessage extends StatelessWidget {
  const _SheetMessage({required this.icon, required this.text, this.action});
  final IconData? icon;
  final String text;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 8, 24, 40),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          icon == null ? const CircularProgressIndicator() : Icon(icon, size: 40),
          const SizedBox(height: 16),
          Text(text, textAlign: TextAlign.center),
          if (action != null) action!,
        ],
      ),
    );
  }
}
