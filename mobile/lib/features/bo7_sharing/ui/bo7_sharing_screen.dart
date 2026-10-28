// Owner: BO7 (@bo7-owner) — entry screen of the BO7 tab (route /bo7_sharing in app/router.dart).
// Four tabs like the web demo: Défis (M15), Communauté (M15 posts), Studio (M10 cards, M7 shops, BO9 avatar)
// and Garde-robe (M1). Design: the DressMe Figma prototype (core/design/dressme_design.dart).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/design/dressme_design.dart';
import '../logic/bo7_providers.dart';
import 'challenges_tab.dart';
import 'community_tab.dart';
import 'studio_tab.dart';
import 'wardrobe_tab.dart';
import 'widgets.dart';

class FeedScreen extends StatelessWidget {
  const FeedScreen({super.key});

  @override
  Widget build(BuildContext context) => Theme(data: dressMeTheme(), child: const Bo7Shell());
}

class _Tab {
  const _Tab(this.label, this.icon);
  final String label;
  final IconData icon;
}

const _tabs = [
  _Tab('Défis', Icons.emoji_events_outlined),
  _Tab('Communauté', Icons.forum_outlined),
  _Tab('Studio', Icons.ios_share_rounded),
  _Tab('Garde-robe', Icons.checkroom_outlined),
];

class Bo7Shell extends ConsumerWidget {
  const Bo7Shell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tab = ref.watch(bo7TabProvider);
    final user = ref.watch(currentUserProvider);
    return Scaffold(
      backgroundColor: DmColors.page,
      appBar: AppBar(
        backgroundColor: DmColors.canvas,
        titleSpacing: 20,
        title: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text('DressMe', style: DmText.display.copyWith(fontSize: 28, fontStyle: FontStyle.italic)),
            const SizedBox(width: 8),
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text('PARTAGE · BO7', style: DmText.eyebrow.copyWith(fontSize: 9)),
            ),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 14),
            child: InkWell(
              borderRadius: BorderRadius.circular(DmRadius.pill),
              onTap: () => _switchUser(context, ref),
              child: Padding(
                padding: const EdgeInsets.all(4),
                child: Row(
                  children: [
                    Text(user, style: DmText.caption.copyWith(fontSize: 11, color: DmColors.mutedDark)),
                    const SizedBox(width: 6),
                    UserAvatar(user, radius: 15),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        bottom: false,
        child: IndexedStack(
          index: tab,
          children: const [ChallengesTab(), CommunityTab(), StudioTab(), WardrobeTab()],
        ),
      ),
      bottomNavigationBar: _BottomBar(
        index: tab,
        onTap: (i) => ref.read(bo7TabProvider.notifier).state = i,
      ),
    );
  }

  /// Play as a friend: the demo has usr_042, amen and yasmine with a wardrobe; any other name works too.
  Future<void> _switchUser(BuildContext context, WidgetRef ref) async {
    final ctrl = TextEditingController(text: ref.read(currentUserProvider));
    final name = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: DmColors.page,
        title: const Text('Profil', style: DmText.title),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Change d\'utilisateur pour jouer comme une amie.', style: DmText.body),
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              children: [
                for (final u in ['usr_042', 'amen', 'yasmine', 'sarra'])
                  ActionChip(label: Text(u), onPressed: () => Navigator.pop(ctx, u)),
              ],
            ),
            const SizedBox(height: 10),
            TextField(controller: ctrl, decoration: const InputDecoration(hintText: 'Nom d\'utilisateur')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
          FilledButton(onPressed: () => Navigator.pop(ctx, ctrl.text.trim()), child: const Text('Valider')),
        ],
      ),
    );
    if (name != null && name.isNotEmpty) ref.read(currentUserProvider.notifier).state = name;
  }
}

/// Dark rounded bottom bar with a gold indicator under the active tab (Figma prototype).
class _BottomBar extends StatelessWidget {
  const _BottomBar({required this.index, required this.onTap});

  final int index;
  final ValueChanged<int> onTap;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        padding: const EdgeInsets.symmetric(vertical: 6),
        decoration: BoxDecoration(
          color: DmColors.inkDeep,
          borderRadius: BorderRadius.circular(DmRadius.panel),
          boxShadow: const [BoxShadow(color: Color(0x55000000), blurRadius: 24, offset: Offset(0, 10))],
        ),
        child: Row(
          children: [
            for (final (i, t) in _tabs.indexed)
              Expanded(
                child: InkWell(
                  borderRadius: BorderRadius.circular(DmRadius.card),
                  onTap: () => onTap(i),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(t.icon, size: 21, color: i == index ? Colors.white : Colors.white54),
                        const SizedBox(height: 3),
                        Text(
                          t.label,
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: i == index ? FontWeight.w700 : FontWeight.w500,
                            color: i == index ? Colors.white : Colors.white54,
                          ),
                        ),
                        const SizedBox(height: 4),
                        AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          width: i == index ? 22 : 0,
                          height: 3,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(3),
                            gradient: const LinearGradient(colors: [DmColors.gold, DmColors.bronze]),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
