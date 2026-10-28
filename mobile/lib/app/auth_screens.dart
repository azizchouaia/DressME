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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: DmColors.inkDeep,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                const SizedBox(height: 12),
                Text('DressMe', textAlign: TextAlign.center, style: DmText.display.copyWith(color: Colors.white, fontSize: 44)),
                const SizedBox(height: 6),
                Text('Your wardrobe, smarter. Wear more of what you own.',
                    textAlign: TextAlign.center, style: DmText.body.copyWith(color: DmColors.goldLight)),
                const SizedBox(height: 28),
                DmCard(
                  big: true,
                  padding: const EdgeInsets.all(20),
                  child: Form(
                    key: _form,
                    child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                      Row(children: [
                        Expanded(child: DmChoiceChip(label: 'Sign in', selected: !_signUp, onTap: () => setState(() => _signUp = false))),
                        const SizedBox(width: 8),
                        Expanded(child: DmChoiceChip(label: 'Create account', selected: _signUp, onTap: () => setState(() => _signUp = true))),
                      ]),
                      const SizedBox(height: 16),
                      if (_signUp) ...[
                        TextFormField(
                          controller: _name,
                          textCapitalization: TextCapitalization.words,
                          decoration: const InputDecoration(labelText: 'Your name'),
                          validator: (v) => (v ?? '').trim().isEmpty ? 'Tell us your name' : null,
                        ),
                        const SizedBox(height: 10),
                      ],
                      TextFormField(
                        controller: _email,
                        keyboardType: TextInputType.emailAddress,
                        autofillHints: const [AutofillHints.email],
                        decoration: const InputDecoration(labelText: 'Email'),
                        validator: (v) => RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch((v ?? '').trim()) ? null : 'Enter a valid email',
                      ),
                      const SizedBox(height: 10),
                      TextFormField(
                        controller: _password,
                        obscureText: _hide,
                        autofillHints: const [AutofillHints.password],
                        decoration: InputDecoration(
                          labelText: 'Password',
                          suffixIcon: IconButton(
                            icon: Icon(_hide ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                            onPressed: () => setState(() => _hide = !_hide),
                          ),
                        ),
                        validator: (v) => (v ?? '').length < 6 ? 'At least 6 characters' : null,
                        onFieldSubmitted: (_) => _submit(),
                      ),
                      if (_signUp) ...[
                        const SizedBox(height: 10),
                        TextFormField(controller: _city, decoration: const InputDecoration(labelText: 'City')),
                        const SizedBox(height: 12),
                        Wrap(spacing: 6, children: [
                          for (final (v, label) in const [('female', 'Woman'), ('male', 'Man'), ('other', 'Prefer not to say')])
                            DmChoiceChip(label: label, selected: _gender == v, onTap: () => setState(() => _gender = v)),
                        ]),
                      ],
                      if (_error != null) ...[
                        const SizedBox(height: 12),
                        Text(_error!, style: DmText.body.copyWith(color: DmColors.warning)),
                      ],
                      const SizedBox(height: 18),
                      DmButton(
                        _busy ? 'Please wait…' : (_signUp ? 'Create my account' : 'Sign in'),
                        kind: DmButtonKind.gold,
                        onPressed: _busy ? null : _submit,
                      ),
                    ]),
                  ),
                ),
                const SizedBox(height: 14),
                TextButton(
                  onPressed: _busy ? null : () => _submit(demo: true),
                  child: Text('Try the demo account', style: DmText.body.copyWith(color: DmColors.goldLight, fontWeight: FontWeight.w600)),
                ),
              ]),
            ),
          ),
        ),
      ),
    );
  }
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
