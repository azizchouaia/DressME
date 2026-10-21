// /design : every shared DressMe piece on one screen, to check the look on a phone.
import 'package:flutter/material.dart';

import '../widgets/dm_widgets.dart';
import 'dressme_design.dart';

class DesignGalleryScreen extends StatefulWidget {
  const DesignGalleryScreen({super.key});

  @override
  State<DesignGalleryScreen> createState() => _DesignGalleryScreenState();
}

class _DesignGalleryScreenState extends State<DesignGalleryScreen> {
  String occasion = 'Université';

  static const _swatches = <(String, Color)>[
    ('inkDeep', DmColors.inkDeep), ('ink', DmColors.ink), ('page', DmColors.page), ('sand', DmColors.sand),
    ('gold', DmColors.gold), ('bronze', DmColors.bronze), ('border', DmColors.border), ('muted', DmColors.muted),
    ('success', DmColors.success), ('warning', DmColors.warning),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: ListView(
        padding: EdgeInsets.zero,
        children: [
          DmHero(
            eyebrow: 'DressMe design',
            title: 'Le kit commun',
            child: Wrap(spacing: 8, runSpacing: 8, children: [
              for (final o in const ['Université', 'Travail', 'Sortie', 'Mariage'])
                DmChoiceChip(label: o, selected: occasion == o, onDark: true, onTap: () => setState(() => occasion = o)),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const DmSectionHeader(eyebrow: 'Couleurs', title: 'DmColors'),
              const SizedBox(height: 12),
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final (name, c) in _swatches)
                  Column(children: [
                    Container(width: 56, height: 40, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(DmRadius.small), border: Border.all(color: DmColors.border))),
                    const SizedBox(height: 4),
                    Text(name, style: DmText.caption),
                  ]),
              ]),
              const SizedBox(height: 24),
              const DmSectionHeader(eyebrow: 'Textes', title: 'DmText'),
              const SizedBox(height: 8),
              const Text('Bonjour, Camille', style: DmText.display),
              const Text('Choisi pour toi en Tunisie', style: DmText.title),
              const Text('Tu as déjà 2 chemises blanches proches de celle-ci.', style: DmText.body),
              const SizedBox(height: 24),
              const DmSectionHeader(eyebrow: 'Boutons', title: 'DmButton'),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(child: DmButton('Je la porte', onPressed: () => dmToast(context, 'Tenue ajoutée à ton journal'))),
                const SizedBox(width: 8),
                Expanded(child: DmButton('Remix', kind: DmButtonKind.gold, onPressed: () => dmToast(context, 'Nouvelle combinaison créée'))),
                const SizedBox(width: 8),
                DmButton('↓', kind: DmButtonKind.outline, onPressed: () {}),
              ]),
              const SizedBox(height: 24),
              DmCard(
                big: true,
                padding: const EdgeInsets.all(20),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    const Expanded(child: Text('Veste en jean', style: DmText.cardTitle)),
                    Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(color: DmColors.inkDeep, borderRadius: BorderRadius.circular(DmRadius.pill)),
                      child: const DmScoreBadge('IA 96%'),
                    ),
                  ]),
                  const SizedBox(height: 12),
                  const Wrap(spacing: 6, runSpacing: 6, children: [DmPill('6 nouvelles tenues'), DmPill('Comble un manque'), DmPill('149 TND', dark: true)]),
                  const SizedBox(height: 14),
                  const DmReasons(['Palette · Le beige et le marine s’accordent', 'Météo · Adaptée à 24 °C', 'Style · Proche de ton style casual']),
                ]),
              ),
              const SizedBox(height: 24),
              const DmCard(child: DmEmptyState(title: 'Ta garde-robe est vide', message: 'Prends une photo de ta première pièce.')),
              const SizedBox(height: 40),
            ]),
          ),
        ],
      ),
    );
  }
}
