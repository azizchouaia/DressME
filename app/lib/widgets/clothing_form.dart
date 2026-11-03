import 'package:flutter/material.dart';

import '../garments.dart';
import '../models.dart';
import '../theme.dart';
import 'ui.dart';

class ClothingForm extends StatefulWidget {
  const ClothingForm({
    super.key,
    required this.initial,
    required this.submitLabel,
    required this.onSubmit,
    this.submitting = false,
    this.suggested = const {},
    this.secondary,
  });

  final ClothingFields initial;
  final String submitLabel;
  final ValueChanged<ClothingFields> onSubmit;
  final bool submitting;
  final Set<String> suggested;
  final Widget? secondary;

  @override
  State<ClothingForm> createState() => _ClothingFormState();
}

class _ClothingFormState extends State<ClothingForm> {
  late ClothingFields _values;

  @override
  void initState() {
    super.initState();
    _values = widget.initial;
  }

  String? _hint(String key) => widget.suggested.contains(key) ? 'Suggested by AI — check it' : null;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextFormField(
          initialValue: _values.name,
          decoration: const InputDecoration(labelText: 'Name'),
          maxLength: 120,
          onChanged: (value) => _values = _values.copyWith(name: value),
        ),
        const SizedBox(height: 12),
        _dropdown(
          label: 'Category',
          value: _values.category,
          hint: _hint('category'),
          options: [for (final category in clothingCategories) (category, categoryLabels[category] ?? category)],
          onChanged: (value) => setState(() => _values = _values.copyWith(category: value)),
        ),
        const SizedBox(height: 12),
        _dropdown(
          label: 'Color',
          value: _values.color ?? '',
          hint: _hint('color'),
          options: [('', 'Not set'), for (final color in colorOptions) (color, capitalize(color))],
          onChanged: (value) => setState(() {
            _values = value.trim().isEmpty ? _values.copyWith(clearColor: true) : _values.copyWith(color: value);
          }),
        ),
        const SizedBox(height: 12),
        _dropdown(
          label: 'Pattern',
          value: _values.pattern ?? '',
          hint: _hint('pattern'),
          options: const [
            ('', 'Not set'),
            ('plain', 'Plain'),
            ('striped', 'Striped'),
            ('checked', 'Checked'),
            ('graphic', 'Graphic'),
            ('floral', 'Floral'),
            ('other', 'Other'),
          ],
          onChanged: (value) => setState(() {
            _values = value.isEmpty ? _values.copyWith(clearPattern: true) : _values.copyWith(pattern: value);
          }),
        ),
        const SizedBox(height: 12),
        _dropdown(
          label: 'Sleeve',
          value: _values.sleeveType ?? '',
          hint: _hint('sleeve_type'),
          options: const [
            ('', 'Not set'),
            ('short', 'Short'),
            ('long', 'Long'),
            ('sleeveless', 'Sleeveless'),
            ('three-quarter', 'Three-quarter'),
          ],
          onChanged: (value) => setState(() {
            _values = value.isEmpty ? _values.copyWith(clearSleeveType: true) : _values.copyWith(sleeveType: value);
          }),
        ),
        const SizedBox(height: 12),
        TextFormField(
          initialValue: _values.brand ?? '',
          decoration: const InputDecoration(labelText: 'Brand', hintText: 'Optional'),
          onChanged: (value) => _values = value.trim().isEmpty ? _values.copyWith(clearBrand: true) : _values.copyWith(brand: value.trim()),
        ),
        const SizedBox(height: 12),
        TextFormField(
          initialValue: _values.size ?? '',
          decoration: const InputDecoration(labelText: 'Size', hintText: 'Optional'),
          onChanged: (value) => _values = value.trim().isEmpty ? _values.copyWith(clearSize: true) : _values.copyWith(size: value.trim()),
        ),
        const SizedBox(height: 12),
        TextFormField(
          initialValue: _values.material ?? '',
          decoration: const InputDecoration(labelText: 'Material', hintText: 'Optional'),
          onChanged: (value) =>
              _values = value.trim().isEmpty ? _values.copyWith(clearMaterial: true) : _values.copyWith(material: value.trim()),
        ),
        const SizedBox(height: 16),
        ?widget.secondary,
        if (widget.secondary != null) const SizedBox(height: 8),
        PrimaryButton(
          label: widget.submitLabel,
          busy: widget.submitting,
          onPressed: _values.name.trim().isEmpty
              ? null
              : () => widget.onSubmit(_values.copyWith(name: _values.name.trim())),
        ),
      ],
    );
  }

  Widget _dropdown({
    required String label,
    required String value,
    required String? hint,
    required List<(String, String)> options,
    required ValueChanged<String> onChanged,
  }) {
    return DropdownButtonFormField<String>(
      initialValue: options.any((option) => option.$1 == value) ? value : options.first.$1,
      decoration: InputDecoration(labelText: label, helperText: hint),
      items: [for (final option in options) DropdownMenuItem(value: option.$1, child: Text(option.$2))],
      onChanged: (next) {
        if (next != null) onChanged(next);
      },
    );
  }
}

class MutedNote extends StatelessWidget {
  const MutedNote(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(text, style: const TextStyle(color: muted, fontSize: 13));
  }
}
