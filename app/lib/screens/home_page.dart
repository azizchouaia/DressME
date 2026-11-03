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

class HomePage extends ConsumerWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(authProvider)?.user;
    final wardrobe = ref.watch(wardrobeProvider);
    final outfits = ref.watch(outfitsProvider);
    final avatar = ref.watch(avatarProvider).value ?? AvatarConfig.fallback;
    final today = outfits.value?.isNotEmpty == true ? outfits.value!.first : null;
    final items = wardrobe.value ?? const <ClothingItem>[];
    final byId = {for (final item in items) item.id: item};
    final now = DateTime.now();

    return PageFrame(
      child: ListView(
        children: [
          Text(_dateLabel(now), style: const TextStyle(color: muted, letterSpacing: 0.4)),
          const SizedBox(height: 6),
          Text(
            '${_greeting(now)}, ${user?.displayName ?? 'there'}',
            style: const TextStyle(fontFamily: 'Georgia', fontSize: 34, height: 1.05, fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: 18),
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    const Expanded(child: Text('Today’s outfit', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600))),
                    if (today != null) Text(today.name, style: const TextStyle(color: muted)),
                  ],
                ),
                const SizedBox(height: 12),
                SizedBox(
                  height: 280,
                  child: outfits.isLoading || wardrobe.isLoading
                      ? const Center(child: CircularProgressIndicator())
                      : today == null
                      ? const Center(child: Text('No outfits yet. Dress your avatar to create your first one.', textAlign: TextAlign.center))
                      : ClipRRect(
                          borderRadius: BorderRadius.circular(18),
                          child: AvatarStage(
                            scene: ViewerScene.avatar(
                              avatarUrl: avatar.baseModelUrl,
                              scaleX: avatar.scaleX,
                              scaleY: avatar.scaleY,
                              scaleZ: avatar.scaleZ,
                              shape: avatar.parameters,
                              garments: garmentUrlsFor(selectionFromOutfit(today), byId),
                              interactive: false,
                            ),
                          ),
                        ),
                ),
                const SizedBox(height: 12),
                PrimaryButton(
                  label: today == null ? 'Create an outfit' : 'View outfit',
                  onPressed: () => context.go(today == null ? '/avatar' : '/avatar?outfit=${today.id}'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    const Expanded(child: Text('Your wardrobe', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600))),
                    TextButton(
                      onPressed: () => context.go('/wardrobe'),
                      child: Text(wardrobe.isLoading ? '…' : '${items.length} ${items.length == 1 ? 'item' : 'items'}'),
                    ),
                  ],
                ),
                if (wardrobe.hasError)
                  Text(wardrobe.error.toString(), style: const TextStyle(color: danger))
                else
                  SizedBox(
                    height: 96,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: items.length.clamp(0, 8),
                      separatorBuilder: (_, _) => const SizedBox(width: 8),
                      itemBuilder: (context, index) {
                        final item = items[index];
                        return GestureDetector(
                          onTap: () => context.push('/wardrobe/${item.id}'),
                          child: ClothingThumb(item: item),
                        );
                      },
                    ),
                  ),
                const SizedBox(height: 12),
                SecondaryButton(label: 'Add clothing', icon: Icons.add, onPressed: () => context.push('/wardrobe/add')),
              ],
            ),
          ),
          const SizedBox(height: 14),
          const AppCard(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.auto_awesome, size: 22),
                SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('AI Stylist', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                      SizedBox(height: 4),
                      Text('“What should I wear today?”'),
                      SizedBox(height: 4),
                      Text('Outfit suggestions from your own wardrobe are coming soon.', style: TextStyle(color: muted, fontSize: 13)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

String _greeting(DateTime date) {
  if (date.hour < 12) return 'Good morning';
  if (date.hour < 18) return 'Good afternoon';
  return 'Good evening';
}

String _dateLabel(DateTime date) {
  const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  return '${weekdays[date.weekday - 1]}, ${months[date.month - 1]} ${date.day}';
}
