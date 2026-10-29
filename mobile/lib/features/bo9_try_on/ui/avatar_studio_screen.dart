// Owner: BO9 (Nadhir) — "My 3D avatar": Nadhir's SMPL-X avatar studio (avatar_studio/), as he built it:
// Build slider (thin -> heavy), body details, Female / Male / Auto with photos. The viewer is his Three.js
// page, served by the API at /viewer (bodies from /presets).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/dm_api.dart';
import '../../../core/auth/auth.dart';
import '../../../core/design/dressme_design.dart';
import 'studio/avatar_frame.dart';

class AvatarStudioScreen extends ConsumerStatefulWidget {
  const AvatarStudioScreen({super.key});

  @override
  ConsumerState<AvatarStudioScreen> createState() => _AvatarStudioScreenState();
}

class _AvatarStudioScreenState extends ConsumerState<AvatarStudioScreen> {
  String? sex;

  @override
  Widget build(BuildContext context) {
    final gender = ref.watch(authProvider).user?.gender;
    final s = sex ?? (gender == 'male' ? 'male' : 'female');
    final url = '${apiBaseUrl()}/viewer/index.html?mesh=/presets/${s}_average.glb';
    return Scaffold(
      backgroundColor: const Color(0xFFF6F4F0), // Nadhir's studio background
      body: Column(children: [
        Container(
          width: double.infinity,
          color: DmColors.inkDeep,
          padding: const EdgeInsets.fromLTRB(20, 16, 12, 14),
          child: SafeArea(
            bottom: false,
            child: Row(children: [
              const Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('BO9 · AVATAR STUDIO', style: TextStyle(color: DmColors.gold, fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 2)),
                  SizedBox(height: 2),
                  Text('My 3D avatar', style: TextStyle(color: Colors.white, fontFamily: DmFonts.serif, fontSize: 26)),
                  Text('Build, body details, photos: your SMPL-X body to try clothes on.',
                      style: TextStyle(color: DmColors.goldLight, fontSize: 13)),
                ]),
              ),
              SegmentedButton<String>(
                style: SegmentedButton.styleFrom(
                  backgroundColor: Colors.white10,
                  foregroundColor: Colors.white,
                  selectedBackgroundColor: DmColors.gold,
                  selectedForegroundColor: DmColors.inkDeep,
                ),
                showSelectedIcon: false,
                segments: const [
                  ButtonSegment(value: 'female', label: Text('Female')),
                  ButtonSegment(value: 'male', label: Text('Male')),
                ],
                selected: {s},
                onSelectionChanged: (v) => setState(() => sex = v.first),
              ),
            ]),
          ),
        ),
        Expanded(child: AvatarFrame(url: url)),
      ]),
    );
  }
}
