import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../garments.dart';
import '../models.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets/clothing_form.dart';
import '../widgets/ui.dart';

class AddClothingPage extends ConsumerStatefulWidget {
  const AddClothingPage({super.key});

  @override
  ConsumerState<AddClothingPage> createState() => _AddClothingPageState();
}

class _AddStep {
  const _AddStep.pick() : name = 'pick', bytes = null, item = null, analysis = null, analysisError = null, label = null;
  const _AddStep.preview(this.bytes) : name = 'preview', item = null, analysis = null, analysisError = null, label = null;
  const _AddStep.working(this.bytes, this.label) : name = 'working', item = null, analysis = null, analysisError = null;
  const _AddStep.review(this.bytes, this.item, this.analysis, this.analysisError) : name = 'review', label = null;

  final String name;
  final Uint8List? bytes;
  final ClothingItem? item;
  final ClothingAnalysis? analysis;
  final String? analysisError;
  final String? label;
}

class _AddClothingPageState extends ConsumerState<AddClothingPage> {
  final _picker = ImagePicker();
  _AddStep _step = const _AddStep.pick();
  String? _error;
  var _saving = false;

  Future<void> _pick(ImageSource source) async {
    try {
      final file = await _picker.pickImage(source: source, imageQuality: 85);
      if (file == null) return;
      final bytes = await file.readAsBytes();
      setState(() {
        _error = null;
        _step = _AddStep.preview(bytes);
      });
    } catch (error) {
      setState(() => _error = error.toString());
    }
  }

  Future<void> _analyze() async {
    final bytes = _step.bytes;
    if (bytes == null) return;
    setState(() {
      _error = null;
      _step = _AddStep.working(bytes, 'Uploading photo…');
    });
    try {
      final item = await ref.read(apiProvider).upload(bytes);
      if (!mounted) return;
      setState(() => _step = _AddStep.working(bytes, 'Analyzing clothing…'));
      try {
        final analysis = await ref.read(apiProvider).analyze(item.id);
        if (!mounted) return;
        setState(() => _step = _AddStep.review(bytes, item, analysis, null));
      } catch (_) {
        if (!mounted) return;
        setState(
          () => _step = _AddStep.review(bytes, item, null, 'We couldn’t analyze this photo. Fill in the details yourself.'),
        );
      }
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _step = _AddStep.preview(bytes);
      });
    }
  }

  ClothingFields _initial(ClothingAnalysis? analysis) {
    final color = analysis?.primaryColor;
    final category = analysis?.category ?? 'other';
    final noun = category == 'other' ? 'piece' : (categoryLabels[category] ?? category).toLowerCase();
    return ClothingFields(
      name: color == null ? 'New piece' : '${capitalize(color)} $noun',
      category: clothingCategories.contains(category) ? category : 'other',
      subcategory: analysis?.subcategory,
      color: color,
      secondaryColor: analysis?.secondaryColor,
      pattern: analysis?.pattern,
      brand: analysis?.brand,
      sleeveType: analysis?.sleeveType,
    );
  }

  Future<void> _confirm(ClothingFields values) async {
    final item = _step.item;
    if (item == null) return;
    setState(() => _saving = true);
    try {
      await ref.read(apiProvider).updateClothing(item.id, values);
      ref.invalidate(wardrobeProvider);
      if (mounted) context.go('/wardrobe');
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString();
        _saving = false;
      });
    }
  }

  Future<void> _discard() async {
    final item = _step.item;
    if (item != null) {
      try {
        await ref.read(apiProvider).deleteClothing(item.id);
      } catch (_) {}
    }
    if (!mounted) return;
    setState(() => _step = const _AddStep.pick());
  }

  @override
  Widget build(BuildContext context) {
    final step = _step;
    return Scaffold(
      body: PageFrame(
        child: ListView(
          children: [
            const PageHeader(showBack: true, title: 'Add clothing', subtitle: 'One piece per photo works best.'),
            if (step.name == 'pick') ...[
              _PickOption(
                icon: Icons.photo_camera_outlined,
                title: 'Take a photo',
                text: 'Lay the item flat on a plain surface',
                onTap: () => _pick(ImageSource.camera),
              ),
              const SizedBox(height: 12),
              _PickOption(
                icon: Icons.photo_library_outlined,
                title: 'Choose from library',
                text: 'JPG, PNG or HEIC up to 12 MB',
                onTap: () => _pick(ImageSource.gallery),
              ),
            ],
            if (step.bytes != null)
              ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    Image.memory(step.bytes!, height: 280, width: double.infinity, fit: BoxFit.cover),
                    if (step.name == 'working')
                      Container(
                        height: 280,
                        color: Colors.black38,
                        alignment: Alignment.center,
                        child: Text(step.label ?? 'Working…', style: const TextStyle(color: Colors.white)),
                      ),
                  ],
                ),
              ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: danger)),
            ],
            if (step.name == 'preview') ...[
              const SizedBox(height: 16),
              PrimaryButton(label: 'Analyze clothing', icon: Icons.auto_awesome, onPressed: _analyze),
              const SizedBox(height: 8),
              SecondaryButton(label: 'Choose another photo', onPressed: () => setState(() => _step = const _AddStep.pick())),
            ],
            if (step.name == 'review') ...[
              const SizedBox(height: 16),
              AppCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Expanded(child: Text('Detected clothing', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 18))),
                        if (step.analysis != null)
                          Text('${(step.analysis!.confidence * 100).round()}% sure', style: const TextStyle(color: muted)),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      step.analysisError ?? 'These are suggestions — review and correct anything before saving.',
                      style: const TextStyle(color: muted),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              ClothingForm(
                initial: _initial(step.analysis),
                submitLabel: 'Confirm and add',
                submitting: _saving,
                suggested: {
                  if (step.analysis?.category != null) 'category',
                  if (step.analysis?.primaryColor != null) 'color',
                  if (step.analysis?.pattern != null) 'pattern',
                  if (step.analysis?.sleeveType != null) 'sleeve_type',
                },
                onSubmit: _confirm,
                secondary: SecondaryButton(label: 'Discard', onPressed: _discard),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _PickOption extends StatelessWidget {
  const _PickOption({required this.icon, required this.title, required this.text, required this.onTap});

  final IconData icon;
  final String title;
  final String text;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(24),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(
            children: [
              Icon(icon, size: 28),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16)),
                    const SizedBox(height: 4),
                    Text(text, style: const TextStyle(color: muted)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
