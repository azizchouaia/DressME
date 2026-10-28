// Welcome (sign in / create account) and Profile (my account, sign out).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/api/dm_api.dart';
import '../core/auth/auth.dart';
import '../core/design/dressme_design.dart';
import '../core/widgets/dm_widgets.dart';

class WelcomeScreen extends ConsumerStatefulWidget {
  const WelcomeScreen({super.key});

  @override
  ConsumerState<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends ConsumerState<WelcomeScreen> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _city = TextEditingController(text: 'Tunis');
  bool _signUp = false;
  bool _busy = false;
  bool _hide = true;
  String? _gender;
  String? _error;

  @override
  void dispose() {
    for (final c in [_name, _email, _password, _city]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _submit({bool demo = false}) async {
    if (!demo && !(_form.currentState?.validate() ?? false)) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final auth = ref.read(authProvider);
    try {
      if (demo) {
        await auth.login('demo@dressme.tn', 'demo1234');
      } else if (_signUp) {
        await auth.register(name: _name.text, email: _email.text, password: _password.text, city: _city.text.trim(), gender: _gender);
      } else {
        await auth.login(_email.text, _password.text);
      }
      if (mounted) context.go('/');
    } catch (e) {
      setState(() => _error = apiError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  InputDecoration _field(String label, IconData icon, {Widget? suffix}) => InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, size: 20, color: DmColors.bronze),
        suffixIcon: suffix,
        filled: true,
        fillColor: DmColors.page,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(DmRadius.card), borderSide: BorderSide.none),
        enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(DmRadius.card), borderSide: const BorderSide(color: DmColors.border)),
        focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(DmRadius.card), borderSide: const BorderSide(color: DmColors.gold, width: 1.6)),
      );

  Widget _toggle() => Container(
        height: 46,
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(color: DmColors.sand, borderRadius: BorderRadius.circular(DmRadius.pill)),
        child: Stack(children: [
          AnimatedAlign(
            duration: const Duration(milliseconds: 320),
            curve: Curves.easeOutCubic,
            alignment: _signUp ? Alignment.centerRight : Alignment.centerLeft,
            child: FractionallySizedBox(
              widthFactor: .5,
              child: Container(
                decoration: BoxDecoration(
                  color: DmColors.inkDeep,
                  borderRadius: BorderRadius.circular(DmRadius.pill),
                  boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 8, offset: Offset(0, 3))],
                ),
              ),
            ),
          ),
          Row(children: [
            for (final (up, label) in const [(false, 'Sign in'), (true, 'Create account')])
              Expanded(
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTap: () => setState(() {
                    _signUp = up;
                    _error = null;
                  }),
                  child: Center(
                    child: AnimatedDefaultTextStyle(
                      duration: const Duration(milliseconds: 220),
                      style: DmText.body.copyWith(
                          fontWeight: FontWeight.w700, color: _signUp == up ? Colors.white : DmColors.mutedDark),
                      child: Text(label),
                    ),
                  ),
                ),
              ),
          ]),
        ]),
      );

  Widget _genderCard(String value, String label, IconData icon) {
    final on = _gender == value;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _gender = value),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            color: on ? DmColors.inkDeep : DmColors.page,
            borderRadius: BorderRadius.circular(DmRadius.card),
            border: Border.all(color: on ? DmColors.inkDeep : DmColors.border),
          ),
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            Icon(icon, size: 18, color: on ? DmColors.goldLight : DmColors.bronze),
            const SizedBox(width: 8),
            Text(label, style: DmText.body.copyWith(fontWeight: FontWeight.w600, color: on ? Colors.white : DmColors.text)),
          ]),
        ),
      ),
    );
  }

  Widget _formCard() => Container(
        padding: const EdgeInsets.fromLTRB(24, 26, 24, 22),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(DmRadius.hero),
          boxShadow: const [BoxShadow(color: Color(0x55000000), blurRadius: 40, offset: Offset(0, 18))],
        ),
        child: Form(
          key: _form,
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 250),
              child: Column(
                key: ValueKey(_signUp),
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(_signUp ? 'JOIN DRESSME' : 'WELCOME BACK', style: DmText.eyebrow),
                  const SizedBox(height: 4),
                  Text(_signUp ? 'Create your wardrobe' : 'Open your wardrobe', style: DmText.title),
                ],
              ),
            ),
            const SizedBox(height: 18),
            _toggle(),
            const SizedBox(height: 18),
            AnimatedSize(
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeOutCubic,
              alignment: Alignment.topCenter,
              child: _signUp
                  ? Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: TextFormField(
                        controller: _name,
                        textCapitalization: TextCapitalization.words,
                        decoration: _field('Your name', Icons.person_outline_rounded),
                        validator: (v) => (v ?? '').trim().isEmpty ? 'Tell us your name' : null,
                      ),
                    )
                  : const SizedBox(width: double.infinity),
            ),
            TextFormField(
              controller: _email,
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.email],
              decoration: _field('Email', Icons.mail_outline_rounded),
              validator: (v) => RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch((v ?? '').trim()) ? null : 'Enter a valid email',
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _password,
              obscureText: _hide,
              autofillHints: const [AutofillHints.password],
              decoration: _field('Password', Icons.lock_outline_rounded,
                  suffix: IconButton(
                    icon: Icon(_hide ? Icons.visibility_outlined : Icons.visibility_off_outlined, size: 20),
                    onPressed: () => setState(() => _hide = !_hide),
                  )),
              validator: (v) => (v ?? '').length < 6 ? 'At least 6 characters' : null,
              onFieldSubmitted: (_) => _submit(),
            ),
            AnimatedSize(
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeOutCubic,
              alignment: Alignment.topCenter,
              child: _signUp
                  ? Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                      const SizedBox(height: 12),
                      TextFormField(controller: _city, decoration: _field('City', Icons.location_on_outlined)),
                      const SizedBox(height: 14),
                      Text('I SHOP FOR', style: DmText.eyebrow),
                      const SizedBox(height: 8),
                      Row(children: [
                        _genderCard('female', 'Woman', Icons.woman_rounded),
                        const SizedBox(width: 10),
                        _genderCard('male', 'Man', Icons.man_rounded),
                      ]),
                    ])
                  : const SizedBox(width: double.infinity),
            ),
            if (_error != null) ...[
              const SizedBox(height: 14),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: DmColors.warningBg, borderRadius: BorderRadius.circular(DmRadius.small)),
                child: Row(children: [
                  const Icon(Icons.error_outline_rounded, size: 18, color: DmColors.warning),
                  const SizedBox(width: 8),
                  Expanded(child: Text(_error!, style: DmText.caption.copyWith(color: DmColors.warning))),
                ]),
              ),
            ],
            const SizedBox(height: 20),
            SizedBox(
              height: 52,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: DmColors.inkDeep,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(DmRadius.card)),
                ),
                onPressed: _busy ? null : _submit,
                child: _busy
                    ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white))
                    : Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                        Text(_signUp ? 'Create my account' : 'Sign in',
                            style: DmText.body.copyWith(color: Colors.white, fontWeight: FontWeight.w700)),
                        const SizedBox(width: 8),
                        const Icon(Icons.arrow_forward_rounded, size: 18),
                      ]),
              ),
            ),
            const SizedBox(height: 16),
            Row(children: [
              const Expanded(child: Divider(color: DmColors.border)),
              Padding(padding: const EdgeInsets.symmetric(horizontal: 10), child: Text('or', style: DmText.caption)),
              const Expanded(child: Divider(color: DmColors.border)),
            ]),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                minimumSize: const Size.fromHeight(48),
                foregroundColor: DmColors.bronzeDark,
                side: const BorderSide(color: DmColors.gold),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(DmRadius.card)),
              ),
              onPressed: _busy ? null : () => _submit(demo: true),
              icon: const Icon(Icons.auto_awesome_outlined, size: 18),
              label: const Text('Try the demo account'),
            ),
          ]),
        ),
      );

  Widget _brand({required bool wide}) => Column(
        crossAxisAlignment: wide ? CrossAxisAlignment.start : CrossAxisAlignment.center,
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 58,
            height: 58,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const LinearGradient(colors: [DmColors.goldLight, DmColors.gold]),
              boxShadow: [BoxShadow(color: DmColors.gold.withValues(alpha: .45), blurRadius: 24)],
            ),
            child: const Icon(Icons.checkroom_rounded, color: DmColors.inkDeep, size: 30),
          ),
          const SizedBox(height: 18),
          Text('DressMe',
              textAlign: wide ? TextAlign.start : TextAlign.center,
              style: DmText.display.copyWith(color: Colors.white, fontSize: wide ? 64 : 46, height: 1)),
          const SizedBox(height: 10),
          Text('Your wardrobe, smarter.\nWear more of what you own.',
              textAlign: wide ? TextAlign.start : TextAlign.center,
              style: DmText.body.copyWith(color: DmColors.goldLight, fontSize: wide ? 18 : 15, height: 1.45)),
          if (wide) ...[
            const SizedBox(height: 34),
            for (final (icon, title, sub) in const [
              (Icons.photo_camera_outlined, 'Digitise your closet', 'One photo: cut out, classified, put away.'),
              (Icons.auto_awesome_outlined, 'Outfits made for you', 'From your own pieces, the weather and your day.'),
              (Icons.shopping_bag_outlined, 'Buy smarter', 'Know if a new piece fits your wardrobe before you pay.'),
            ])
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Container(
                    padding: const EdgeInsets.all(9),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: .06),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: DmColors.gold.withValues(alpha: .35)),
                    ),
                    child: Icon(icon, size: 20, color: DmColors.goldLight),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(title, style: DmText.body.copyWith(color: Colors.white, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 2),
                      Text(sub, style: DmText.caption.copyWith(color: Colors.white60)),
                    ]),
                  ),
                ]),
              ),
          ],
        ],
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DmColors.inkDeep,
      body: Stack(children: [
        // soft gold glows behind everything
        const Positioned(top: -160, right: -120, child: _Glow(size: 460, alpha: .22)),
        const Positioned(bottom: -200, left: -140, child: _Glow(size: 520, alpha: .14)),
        SafeArea(
          child: LayoutBuilder(builder: (context, box) {
            final wide = box.maxWidth >= 900;
            final card = ConstrainedBox(constraints: const BoxConstraints(maxWidth: 440), child: _formCard());
            return Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 28),
                child: TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: 1),
                  duration: const Duration(milliseconds: 700),
                  curve: Curves.easeOutCubic,
                  builder: (_, t, child) =>
                      Opacity(opacity: t, child: Transform.translate(offset: Offset(0, 24 * (1 - t)), child: child)),
                  child: wide
                      ? ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 1080),
                          child: Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
                            Expanded(child: Padding(padding: const EdgeInsets.only(right: 56), child: _brand(wide: true))),
                            card,
                          ]),
                        )
                      : Column(children: [_brand(wide: false), const SizedBox(height: 28), card]),
                ),
              ),
            );
          }),
        ),
      ]),
    );
  }
}

class _Glow extends StatelessWidget {
  const _Glow({required this.size, required this.alpha});

  final double size;
  final double alpha;

  @override
  Widget build(BuildContext context) => IgnorePointer(
        child: Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(colors: [DmColors.gold.withValues(alpha: alpha), DmColors.gold.withValues(alpha: 0)]),
          ),
        ),
      );
}

class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  late final AuthController _auth = ref.read(authProvider);
  late final _name = TextEditingController(text: _auth.user?.name);
  late final _city = TextEditingController(text: _auth.user?.city);
  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _city.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final u = ref.watch(authProvider).user;
    if (u == null) return const SizedBox.shrink();
    return Scaffold(
      body: ListView(padding: EdgeInsets.zero, children: [
        DmHero(
          eyebrow: u.isDemo ? 'Demo account' : 'My account',
          title: u.name.isEmpty ? 'Hello' : u.name,
          child: Text(u.email, style: DmText.body.copyWith(color: DmColors.goldLight)),
        ),
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                DmCard(
                  big: true,
                  padding: const EdgeInsets.all(18),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    const DmSectionHeader(eyebrow: 'Profile', title: 'About me'),
                    const SizedBox(height: 12),
                    TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name')),
                    const SizedBox(height: 10),
                    TextField(controller: _city, decoration: const InputDecoration(labelText: 'City')),
                    const SizedBox(height: 14),
                    DmButton(_saving ? 'Saving…' : 'Save', onPressed: _saving
                        ? null
                        : () async {
                            setState(() => _saving = true);
                            try {
                              await _auth.updateProfile(name: _name.text.trim(), city: _city.text.trim());
                              if (context.mounted) dmToast(context, 'Saved');
                            } catch (e) {
                              if (context.mounted) dmToast(context, apiError(e));
                            } finally {
                              if (mounted) setState(() => _saving = false);
                            }
                          }),
                  ]),
                ),
                const SizedBox(height: 12),
                DmCard(
                  child: Text('Your user id: ${u.id}\nEvery module (wardrobe, outfits, smart buy, shops…) now works for this account.',
                      style: DmText.caption),
                ),
                const SizedBox(height: 16),
                DmButton('Sign out', kind: DmButtonKind.outline, icon: Icons.logout_rounded, onPressed: () async {
                  await _auth.logout();
                  if (context.mounted) context.go('/welcome');
                }),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}
